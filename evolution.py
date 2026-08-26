"""
Six Nations — Evolution Chamber

Headless bot-vs-bot genetic algorithm tournament.  No UI / pygame required.

Usage:
    python evolution.py                          # default: 24 pop, 50 gens
    python evolution.py --population 32 --generations 100
    python evolution.py --resume                 # seed from bot_configs.json
    python evolution.py --resume --generations 20  # 20 more gens on top

Persists the top 4 evolved configs to bot_configs.json for the main game.
"""

import argparse
import copy
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Imports from the game engine (no pygame needed)
# ---------------------------------------------------------------------------

# Prevent pygame from trying to open a display window when imported
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from factions import create_nations
from map import MapGrid
from player import Player
from bot import (
    BotMemory,
    _eligible_nations,
    _enemy_set,
    _gather_actions,
    _turn_random,
    _execute,
    _adaptive_sovereign_adjustments,
)
import settings


# ---------------------------------------------------------------------------
# BotConfig — the genome
# ---------------------------------------------------------------------------

@dataclass
class BotConfig:
    """Evolvable genome for a bot player.

    The 7 intent-weight genes multiply the corresponding score categories
    in bot.py's scoring functions.  A value of 1.0 reproduces the original
    hardcoded behaviour; 0.0 disables that category entirely; >1.0
    amplifies it.

    w_random and w_deceptive control the probability of choosing those
    move types vs an intent move.  They CAN be 0.0 (pure intent bot).

    random_early_turns / deceptive_early_turns specify how many initial
    turns to bias toward random / deceptive.  Can be 0 for none.
    """

    # --- Intent weights (7 genes) ---
    w_kill_enemy:         float = 1.0   # 1. Killing enemy pieces
    w_advance_allied:     float = 1.0   # 2. Moving allied toward enemy
    w_protect_sovereign:  float = 1.0   # 3. Protecting allied sovereigns
    w_muster_promote:     float = 1.0   # 4. Mustering / promoting
    w_champion_support:   float = 1.0   # 5. Keeping champions supported
    w_endanger_enemy_sov: float = 1.0   # 6. Pushing enemy sovs to danger
    w_unsupport_enemy_ch: float = 1.0   # 7. Moving enemy champs off support

    # --- Move-type weights (2 genes) ---
    w_random:             float = 0.30  # 8. Weight for random moves
    w_deceptive:          float = 0.15  # 9. Weight for deceptive moves
    # (intent weight is implicitly 1.0 - w_random - w_deceptive, clamped >= 0)

    # --- Turn-phase behaviour ---
    random_early_turns:    int  = 8     # bias toward random for first N turns
    deceptive_early_turns: int  = 5     # bias toward deceptive for first N turns

    # --- Adaptive behaviour ---
    adaptive_turn:         int  = 25    # when to start using opponent intel

    # --- Runtime (not part of genome, not persisted) ---
    fitness:               float = 0.0

    def to_weights_dict(self):
        """Return the dict expected by bot.py scoring functions."""
        return {
            'kill_enemy':           self.w_kill_enemy,
            'advance_allied':       self.w_advance_allied,
            'protect_sovereign':    self.w_protect_sovereign,
            'muster_promote':       self.w_muster_promote,
            'champion_support':     self.w_champion_support,
            'endanger_enemy_sov':   self.w_endanger_enemy_sov,
            'unsupport_enemy_champ': self.w_unsupport_enemy_ch,
        }

    def intent_probability(self, turn_number):
        """Probability of choosing an intent move on this turn.

        Early turns bias toward random/deceptive; later turns shift
        toward intent.  If w_random and w_deceptive are both 0.0,
        returns 1.0 (pure intent).
        """
        total_non_intent = self.w_random + self.w_deceptive
        if total_non_intent <= 0:
            return 1.0  # pure intent bot

        # Early-game multiplier: amplify non-intent in early turns
        if turn_number <= max(self.random_early_turns,
                              self.deceptive_early_turns):
            early_boost = 1.5
        else:
            early_boost = 1.0

        # Late-game suppression: reduce non-intent as game progresses
        t = min(max(turn_number, 1), 80)
        late_factor = max(0.1, 1.0 - (t - 1) / 100.0)

        effective_non = total_non_intent * early_boost * late_factor
        intent_p = 1.0 / (1.0 + effective_non)
        return max(0.0, min(1.0, intent_p))

    def random_vs_deceptive_split(self):
        """Given that we chose non-intent, probability of random vs deceptive."""
        total = self.w_random + self.w_deceptive
        if total <= 0:
            return 0.5, 0.5  # shouldn't be called, but safe fallback
        return self.w_random / total, self.w_deceptive / total

    @staticmethod
    def random_config():
        """Create a fully random BotConfig."""
        return BotConfig(
            w_kill_enemy=random.uniform(0.2, 3.0),
            w_advance_allied=random.uniform(0.2, 3.0),
            w_protect_sovereign=random.uniform(0.2, 3.0),
            w_muster_promote=random.uniform(0.2, 3.0),
            w_champion_support=random.uniform(0.2, 3.0),
            w_endanger_enemy_sov=random.uniform(0.2, 3.0),
            w_unsupport_enemy_ch=random.uniform(0.2, 3.0),
            w_random=random.uniform(0.0, 0.6),
            w_deceptive=random.uniform(0.0, 0.4),
            random_early_turns=random.randint(0, 20),
            deceptive_early_turns=random.randint(0, 15),
            adaptive_turn=random.randint(10, 40),
        )


# ---------------------------------------------------------------------------
# EvolvableBot — bot player that uses BotConfig
# ---------------------------------------------------------------------------

class EvolvableBot:
    """A bot player driven by a BotConfig genome.

    Wraps Player + BotMemory and provides compute_action / execute_action
    matching the same pattern as bot.py's compute_bot_action / execute_bot_action.
    """

    def __init__(self, secret_nation, config: BotConfig, player_id='bot'):
        self.player = Player(secret_nation, is_bot=True, player_id=player_id)
        self.config = config
        self.memory = BotMemory(debug=False)
        self._weights = config.to_weights_dict()

    @property
    def secret_nation(self):
        return self.player.secret_nation

    def record_opponent_move(self, turn_number, nation, unit_type_str,
                             from_hex, to_hex, action_type, nation_names=None):
        """Record an opponent move in memory and update suspicion scores."""
        self.memory.record(turn_number, nation, unit_type_str,
                           from_hex, to_hex, action_type)
        # Simple suspicion: add points for moving a nation
        self.memory.add_score(nation.ring_index, 3, nation_names)

    def guess_opponent_faction(self, nation_list):
        """Return the suspected ring_index of the opponent's secret nation."""
        exclude = {self.player.secret_nation.ring_index}
        guess = self.memory.guess_faction(nation_list, exclude_ring_indices=exclude)
        return guess.ring_index if guess else None

    def compute_action(self, grid, global_cooldown_idx, nation_list, turn_number):
        """Select an action without executing it.  Returns action tuple or None."""
        suspected_ri = None
        if turn_number >= self.config.adaptive_turn:
            suspected_ri = self.guess_opponent_faction(nation_list)

        # Decide move type: intent, random, or deceptive
        intent_p = self.config.intent_probability(turn_number)

        roll = random.random()
        if roll < intent_p:
            move_type = 'intent'
        else:
            rand_frac, _ = self.config.random_vs_deceptive_split()
            if random.random() < rand_frac:
                move_type = 'random'
            else:
                move_type = 'deceptive'

        if move_type == 'intent':
            return self._compute_intent(grid, global_cooldown_idx, nation_list,
                                        turn_number, suspected_ri)
        elif move_type == 'random':
            return self._compute_random(grid, global_cooldown_idx, nation_list,
                                        turn_number, suspected_ri)
        else:  # deceptive
            return self._compute_deceptive(grid, global_cooldown_idx, nation_list,
                                           turn_number, suspected_ri)

    def _compute_intent(self, grid, gci, nation_list, turn, suspected_ri):
        """Strategic intent using config weights."""
        actions = _gather_actions(grid, self.player, gci, nation_list,
                                  suspected_human_ri=suspected_ri,
                                  turn_number=turn,
                                  weights=self._weights)
        if not actions:
            return None
        valid = [a for a in actions if a[0] > -1000]
        if valid:
            actions = valid
        best = max(a[0] for a in actions)
        threshold = (best * 0.85) if best > 0 else (best - 50)
        top_tier = [a for a in actions if a[0] >= threshold]
        chosen = random.choice(top_tier)
        return (*chosen, 'intent')

    def _compute_random(self, grid, gci, nation_list, turn, suspected_ri):
        """Purely random legal action."""
        eligible = _eligible_nations(self.player, gci, nation_list)
        if not eligible:
            return None

        allied_ring_set = {n.ring_index for n in nation_list
                           if not self.player.secret_nation.is_enemy(n)}
        bot_ri = self.player.secret_nation.ring_index

        pool = []
        for nation in eligible:
            for unit in grid.get_all_nation_units(nation):
                pool += [(0, 'move', unit, c) for c in grid.get_valid_moves(unit, mover_secret_nation=self.player.secret_nation)]
                for c in grid.get_valid_attacks(unit):
                    tq, tr = c
                    allied_sovs = [s for s in grid.sovereigns.get((tq, tr), [])
                                   if s.nation.ring_index in allied_ring_set
                                   and unit.nation.is_enemy(s.nation)]
                    if not allied_sovs:
                        pool.append((0, 'attack', unit, c))
            for coord in grid.get_recruit_hexes(nation):
                pool.append((0, 'recruit', nation, coord))
            for coord in grid.get_promote_hexes(nation):
                pool.append((0, 'promote', nation, coord))

        if not pool:
            return None

        # Apply adaptive adjustments even to random pool
        pool = _adaptive_sovereign_adjustments(
            grid, pool, bot_ri, suspected_ri, turn,
            nation_list=nation_list)
        valid = [a for a in pool if a[0] > -1000]
        if valid:
            pool = valid

        chosen = random.choice(pool)
        return (*chosen, 'random')

    def _compute_deceptive(self, grid, gci, nation_list, turn, suspected_ri):
        """Deceptive move: temporarily pretend to have a different secret nation.

        Uses intent scoring but with a fake secret nation, so the move
        *looks* like the bot is fighting for a different faction.
        """
        real_nation = self.player.secret_nation

        # Pick a random different nation as the fake
        candidates = [n for n in nation_list
                      if n.ring_index != real_nation.ring_index
                      and not n.is_ghost]
        if not candidates:
            # Fall back to intent if no valid fake nation
            return self._compute_intent(grid, gci, nation_list, turn, suspected_ri)

        fake_nation = random.choice(candidates)

        # Temporarily swap
        self.player.secret_nation = fake_nation
        fake_weights = self.config.to_weights_dict()

        actions = _gather_actions(grid, self.player, gci, nation_list,
                                  suspected_human_ri=suspected_ri,
                                  turn_number=turn,
                                  weights=fake_weights)

        # Restore real nation
        self.player.secret_nation = real_nation

        if not actions:
            return None
        valid = [a for a in actions if a[0] > -1000]
        if valid:
            actions = valid
        best = max(a[0] for a in actions)
        threshold = (best * 0.85) if best > 0 else (best - 50)
        top_tier = [a for a in actions if a[0] >= threshold]
        chosen = random.choice(top_tier)
        return (*chosen, 'deceptive')


# ---------------------------------------------------------------------------
# HeadlessGame — runs one full game without UI
# ---------------------------------------------------------------------------

# Result constants
RESULT_BOT1_WIN  = 'bot1_win'
RESULT_BOT2_WIN  = 'bot2_win'
RESULT_TIE       = 'tie'
RESULT_DRAW      = 'draw'       # turn limit reached, no winner

MAX_TURNS = 200


class HeadlessGame:
    """Run a complete bot-vs-bot game headlessly.

    Both bots track each other's moves via BotMemory and try to guess
    the opponent's secret nation.  Neither knows the other's secret colour.
    """

    def __init__(self, config1: BotConfig, config2: BotConfig,
                 max_turns: int = MAX_TURNS, seed=None):
        self.max_turns = max_turns

        if seed is not None:
            random.seed(seed)

        # Fresh independent nations for this game
        self.nations = create_nations()

        # Assign random secret nations (must be different)
        n1 = random.choice(self.nations)
        n2 = random.choice([n for n in self.nations if n.ring_index != n1.ring_index])

        self.bot1 = EvolvableBot(n1, config1, player_id='bot1')
        self.bot2 = EvolvableBot(n2, config2, player_id='bot2')

        self.grid = MapGrid()
        self.grid.generate_map()

        self.turn_number = 1
        self.global_cooldown_idx = None

    def play(self) -> str:
        """Play the full game.  Returns a RESULT_* constant."""
        bots = [self.bot1, self.bot2]
        current = 0

        for _ in range(self.max_turns):
            bot = bots[current]
            opponent = bots[1 - current]

            action = bot.compute_action(
                self.grid, self.global_cooldown_idx,
                self.nations, self.turn_number)

            if action is None:
                # No legal moves — skip turn
                current = 1 - current
                self.turn_number += 1
                continue

            # Execute the action
            moved_nation, action_type, desc = _execute(self.grid, action)

            if moved_nation is None:
                # Execution failed — skip turn
                current = 1 - current
                self.turn_number += 1
                continue

            # Update cooldowns
            bot.player.add_to_cooldown(moved_nation)
            self.global_cooldown_idx = moved_nation.ring_index

            # Record the move for the opponent's memory
            # Extract unit info from the action for recording
            _score, atype, *rest = action
            # Strip path label if present
            if rest and isinstance(rest[-1], str) and rest[-1] in ('intent', 'random', 'deceptive'):
                payload = rest[:-1]
            else:
                payload = rest

            unit_type_str = None
            from_hex = None
            to_hex = None
            if atype in ('move', 'attack') and len(payload) >= 2:
                unit = payload[0]
                coord = payload[1]
                from armies import Army
                from champions import Champion, Sovereign
                if isinstance(unit, Sovereign):
                    unit_type_str = 'sovereign'
                elif isinstance(unit, Champion):
                    unit_type_str = 'champion'
                elif isinstance(unit, Army):
                    unit_type_str = 'army'
                from_hex = unit.hex_location
                to_hex = coord
            elif atype in ('recruit', 'promote') and len(payload) >= 2:
                to_hex = payload[1]

            opponent.record_opponent_move(
                self.turn_number, moved_nation, unit_type_str,
                from_hex, to_hex, action_type or atype)

            # Check end conditions
            self.grid.check_ghost_nations(self.nations)
            b1_wins = self.grid.check_win_condition(self.bot1.player, self.nations)
            b2_wins = self.grid.check_win_condition(self.bot2.player, self.nations)
            b1_loses = self.grid.check_loss_condition(self.bot1.player)
            b2_loses = self.grid.check_loss_condition(self.bot2.player)

            if (b1_wins and b2_wins) or (b1_loses and b2_loses):
                return RESULT_TIE
            if b1_wins or b2_loses:
                return RESULT_BOT1_WIN
            if b2_wins or b1_loses:
                return RESULT_BOT2_WIN

            # Advance turn
            current = 1 - current
            self.turn_number += 1

        return RESULT_DRAW


# ---------------------------------------------------------------------------
# Tournament — round-robin within one generation
# ---------------------------------------------------------------------------

class Tournament:
    """Round-robin tournament for a population of BotConfigs."""

    def __init__(self, configs: list, games_per_pair: int = 2,
                 max_turns: int = MAX_TURNS):
        self.configs = configs
        self.games_per_pair = games_per_pair
        self.max_turns = max_turns

    def run(self) -> list:
        """Play all matchups and return configs with updated fitness scores.

        Fitness scoring: +3 win, +1 tie, +0 loss/draw.
        """
        n = len(self.configs)
        # Reset fitness
        for c in self.configs:
            c.fitness = 0.0

        total_matches = n * (n - 1) // 2 * self.games_per_pair
        played = 0

        for i in range(n):
            for j in range(i + 1, n):
                for g in range(self.games_per_pair):
                    seed = random.randint(0, 2**31)
                    game = HeadlessGame(
                        self.configs[i], self.configs[j],
                        max_turns=self.max_turns, seed=seed)
                    result = game.play()

                    if result == RESULT_BOT1_WIN:
                        self.configs[i].fitness += 3
                    elif result == RESULT_BOT2_WIN:
                        self.configs[j].fitness += 3
                    elif result == RESULT_TIE:
                        self.configs[i].fitness += 1
                        self.configs[j].fitness += 1
                    # DRAW: both get 0

                    played += 1

        return self.configs


# ---------------------------------------------------------------------------
# GeneticAlgorithm — evolution engine
# ---------------------------------------------------------------------------

# Gene ranges for clamping after mutation
_GENE_RANGES = {
    'w_kill_enemy':         (0.0, 5.0),
    'w_advance_allied':     (0.0, 5.0),
    'w_protect_sovereign':  (0.0, 5.0),
    'w_muster_promote':     (0.0, 5.0),
    'w_champion_support':   (0.0, 5.0),
    'w_endanger_enemy_sov': (0.0, 5.0),
    'w_unsupport_enemy_ch': (0.0, 5.0),
    'w_random':             (0.0, 1.0),
    'w_deceptive':          (0.0, 1.0),
    'random_early_turns':   (0, 30),
    'deceptive_early_turns': (0, 25),
    'adaptive_turn':        (5, 60),
}

# Fields that are integers
_INT_GENES = {'random_early_turns', 'deceptive_early_turns', 'adaptive_turn'}

# All gene field names
_GENE_NAMES = list(_GENE_RANGES.keys())


class GeneticAlgorithm:
    """Genetic algorithm engine for evolving BotConfigs."""

    def __init__(self, population_size=24, generations=50,
                 elite_count=4, mutation_rate=0.15,
                 mutation_reset_rate=0.05, games_per_pair=2,
                 max_turns=MAX_TURNS, seed_configs=None):
        self.population_size = population_size
        self.generations = generations
        self.elite_count = elite_count
        self.mutation_rate = mutation_rate
        self.mutation_reset_rate = mutation_reset_rate
        self.games_per_pair = games_per_pair
        self.max_turns = max_turns

        # Initialize population
        if seed_configs:
            # Resume: start with seed configs + fill with mutated variants + random
            self.population = []
            for sc in seed_configs[:self.elite_count]:
                self.population.append(copy.deepcopy(sc))
            # Fill remaining with mutated variants of seeds + random immigrants
            while len(self.population) < self.population_size:
                if random.random() < 0.6 and seed_configs:
                    # Mutated variant of a seed
                    parent = copy.deepcopy(random.choice(seed_configs))
                    self._mutate(parent, rate=0.30)  # higher mutation for diversity
                    self.population.append(parent)
                else:
                    self.population.append(BotConfig.random_config())
        else:
            self.population = [BotConfig.random_config()
                               for _ in range(self.population_size)]

    def evolve(self, progress_callback=None):
        """Run the full evolution.  Returns the final sorted population.

        progress_callback(gen, best_fitness, avg_fitness, best_config)
        is called after each generation if provided.
        """
        for gen in range(1, self.generations + 1):
            # Run tournament
            tournament = Tournament(self.population,
                                    games_per_pair=self.games_per_pair,
                                    max_turns=self.max_turns)
            tournament.run()

            # Sort by fitness (descending)
            self.population.sort(key=lambda c: c.fitness, reverse=True)

            best_fit = self.population[0].fitness
            avg_fit = sum(c.fitness for c in self.population) / len(self.population)

            if progress_callback:
                progress_callback(gen, best_fit, avg_fit, self.population[0])

            # Build next generation
            next_gen = []

            # Elitism: carry forward top N unchanged
            for c in self.population[:self.elite_count]:
                elite = copy.deepcopy(c)
                elite.fitness = 0.0
                next_gen.append(elite)

            # Check population diversity — if too converged, add immigrants
            diversity = self._population_diversity()
            immigrants_needed = 0
            if diversity < 0.15:
                immigrants_needed = min(4, self.population_size // 4)
            elif diversity < 0.30:
                immigrants_needed = 2

            for _ in range(immigrants_needed):
                next_gen.append(BotConfig.random_config())

            # Fill remaining slots via selection + crossover + mutation
            while len(next_gen) < self.population_size:
                parent_a = self._tournament_select()
                parent_b = self._tournament_select()
                child = self._crossover(parent_a, parent_b)
                self._mutate(child)
                next_gen.append(child)

            self.population = next_gen[:self.population_size]

        # Final tournament to get definitive rankings
        tournament = Tournament(self.population,
                                games_per_pair=self.games_per_pair,
                                max_turns=self.max_turns)
        tournament.run()
        self.population.sort(key=lambda c: c.fitness, reverse=True)

        return self.population

    def _tournament_select(self, k=3):
        """Tournament selection: pick k random, return the fittest."""
        candidates = random.sample(self.population,
                                   min(k, len(self.population)))
        return max(candidates, key=lambda c: c.fitness)

    @staticmethod
    def _crossover(parent_a: BotConfig, parent_b: BotConfig) -> BotConfig:
        """Uniform crossover: each gene randomly from parent A or B."""
        child = BotConfig()
        for gene in _GENE_NAMES:
            if random.random() < 0.5:
                setattr(child, gene, getattr(parent_a, gene))
            else:
                setattr(child, gene, getattr(parent_b, gene))
        child.fitness = 0.0
        return child

    def _mutate(self, config: BotConfig, rate=None):
        """Mutate genes with given probability."""
        mr = rate if rate is not None else self.mutation_rate
        for gene in _GENE_NAMES:
            if random.random() < mr:
                lo, hi = _GENE_RANGES[gene]
                if random.random() < self.mutation_reset_rate:
                    # Full random reset (escape local optima)
                    if gene in _INT_GENES:
                        setattr(config, gene, random.randint(int(lo), int(hi)))
                    else:
                        setattr(config, gene, random.uniform(lo, hi))
                else:
                    # Gaussian perturbation (+-20% of range)
                    current = getattr(config, gene)
                    spread = (hi - lo) * 0.20
                    new_val = current + random.gauss(0, spread)
                    new_val = max(lo, min(hi, new_val))
                    if gene in _INT_GENES:
                        new_val = int(round(new_val))
                    setattr(config, gene, new_val)

    def _population_diversity(self) -> float:
        """Measure population diversity as mean coefficient of variation across genes.

        Returns a value between 0.0 (all identical) and ~1.0+ (very diverse).
        """
        if len(self.population) < 2:
            return 1.0
        cvs = []
        for gene in _GENE_NAMES:
            vals = [float(getattr(c, gene)) for c in self.population]
            mean = sum(vals) / len(vals)
            if mean == 0:
                continue
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = math.sqrt(var)
            cvs.append(std / abs(mean))
        return sum(cvs) / len(cvs) if cvs else 0.0


# ---------------------------------------------------------------------------
# Persistence — save / load top configs
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'bot_configs.json')


def persist_top_configs(configs: list, filepath=DEFAULT_CONFIG_PATH,
                        generations=0, top_n=4):
    """Save the top N evolved configs to a JSON file."""
    top = configs[:top_n]
    data = {
        'version': 1,
        'evolved_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'generations': generations,
        'configs': [],
    }
    for c in top:
        d = {}
        for gene in _GENE_NAMES:
            val = getattr(c, gene)
            d[gene] = val
        d['fitness'] = c.fitness
        data['configs'].append(d)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n  Saved top {len(top)} configs to {filepath}")


def load_top_configs(filepath=DEFAULT_CONFIG_PATH) -> list:
    """Load persisted configs from JSON.  Returns list of BotConfig."""
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        data = json.load(f)

    configs = []
    for d in data.get('configs', []):
        c = BotConfig()
        for gene in _GENE_NAMES:
            if gene in d:
                val = d[gene]
                if gene in _INT_GENES:
                    val = int(val)
                setattr(c, gene, val)
        c.fitness = d.get('fitness', 0.0)
        configs.append(c)
    return configs


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _progress(gen, best_fit, avg_fit, best_config):
    """Print progress for each generation."""
    intent_w = [f"{getattr(best_config, g):.2f}" for g in _GENE_NAMES[:7]]
    rnd = f"{best_config.w_random:.2f}"
    dec = f"{best_config.w_deceptive:.2f}"
    print(f"  Gen {gen:3d} | best={best_fit:6.1f}  avg={avg_fit:5.1f} | "
          f"intent={','.join(intent_w)}  rnd={rnd}  dec={dec}")


def main():
    parser = argparse.ArgumentParser(
        description='Six Nations -- Bot Evolution Chamber')
    parser.add_argument('--population', type=int, default=24,
                        help='Population size per generation (default: 24)')
    parser.add_argument('--generations', type=int, default=50,
                        help='Number of generations to evolve (default: 50)')
    parser.add_argument('--games', type=int, default=2,
                        help='Games per matchup pair (default: 2)')
    parser.add_argument('--max-turns', type=int, default=MAX_TURNS,
                        help=f'Max turns per game (default: {MAX_TURNS})')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from existing bot_configs.json')
    parser.add_argument('--output', type=str, default=DEFAULT_CONFIG_PATH,
                        help='Output JSON filepath (default: bot_configs.json)')
    args = parser.parse_args()

    print("=" * 56)
    print("        SIX NATIONS -- EVOLUTION CHAMBER")
    print("=" * 56)
    print(f"  Population: {args.population}  |  Generations: {args.generations}")
    print(f"  Games/pair: {args.games}  |  Max turns: {args.max_turns}")

    seed_configs = None
    if args.resume:
        seed_configs = load_top_configs(args.output)
        if seed_configs:
            print(f"  Resuming from {len(seed_configs)} saved configs in {args.output}")
        else:
            print(f"  --resume: no existing configs found at {args.output}, starting fresh")

    print()

    ga = GeneticAlgorithm(
        population_size=args.population,
        generations=args.generations,
        games_per_pair=args.games,
        max_turns=args.max_turns,
        seed_configs=seed_configs,
    )

    t0 = time.time()
    interrupted = False
    try:
        final = ga.evolve(progress_callback=_progress)
    except KeyboardInterrupt:
        interrupted = True
        print("\n\n  !! Interrupted — saving best configs so far...")
        # Sort current population by fitness (may be from last completed gen)
        ga.population.sort(key=lambda c: c.fitness, reverse=True)
        final = ga.population

    elapsed = time.time() - t0

    if interrupted:
        print(f"  Partial evolution saved after {elapsed:.1f}s")
    else:
        print(f"\n  Evolution completed in {elapsed:.1f}s")

    # Determine total generations (including any previous runs)
    total_gens = args.generations
    if args.resume and os.path.exists(args.output):
        try:
            with open(args.output) as f:
                old_data = json.load(f)
            total_gens += old_data.get('generations', 0)
        except Exception:
            pass

    persist_top_configs(final, filepath=args.output,
                        generations=total_gens)

    # Print summary of top 4
    print("\n  -- TOP 4 EVOLVED CONFIGS --\n")
    for i, c in enumerate(final[:4]):
        print(f"  #{i+1}  fitness={c.fitness:.1f}")
        print(f"      kill_enemy={c.w_kill_enemy:.2f}  advance={c.w_advance_allied:.2f}  "
              f"protect_sov={c.w_protect_sovereign:.2f}")
        print(f"      muster={c.w_muster_promote:.2f}  champ_sup={c.w_champion_support:.2f}  "
              f"danger_sov={c.w_endanger_enemy_sov:.2f}  unsup_ch={c.w_unsupport_enemy_ch:.2f}")
        print(f"      random={c.w_random:.2f}  deceptive={c.w_deceptive:.2f}  "
              f"rnd_early={c.random_early_turns}  dec_early={c.deceptive_early_turns}  "
              f"adaptive_t={c.adaptive_turn}")
        print()


if __name__ == '__main__':
    main()

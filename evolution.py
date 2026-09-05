"""
Six Nations — Evolution Chamber

Headless bot-vs-bot genetic algorithm tournament.  No UI / pygame required.

Usage:
    python evolution.py                          # evolves and resumes from bot_configs.json if present
    python evolution.py --generations 20         # 20 more gens accumulating on top
    python evolution.py --freshstart             # wipes/ignores previous and starts fresh
    python evolution.py --freshstart --generations 25 --output arena.json

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
# Imports from the game engine
# ---------------------------------------------------------------------------

from factions import create_nations
from map import MapGrid
from player import Player
from bot import (
    BotMemory,
    _eligible_nations,
    _enemy_names,
    _gather_actions,
    _turn_random,
    _execute,
    _adaptive_sovereign_adjustments,
)
import settings


# ---------------------------------------------------------------------------
# BotGoals — bot's secret goal list (parallel to human prevail/defeat picks)
# ---------------------------------------------------------------------------

@dataclass
class BotGoals:
    """A bot's randomly-assigned secret goals for one game.

    prevail_goals: 3 color_name strings — nations the bot wants to survive
                   (it will try to ally with them).
    defeat_goals:  3 color_name strings — nations the bot wants to ghost
                   (it will try to declare war on them).
    """
    prevail_goals: list = field(default_factory=list)
    defeat_goals:  list = field(default_factory=list)

    @staticmethod
    def random(all_nations):
        """Assign 3 random prevail + 3 random defeat goals across all 6 nations.

        Rules:
        - Prevail goals: 3 random nations (ranked slots: 3, 2, 1 pts).
        - Defeat goals: the remaining 3 nations (ranked slots: 3, 2, 1 pts).
        - The two lists do not overlap and cover all 6 nations.
        """
        all_names = [n.color_name if hasattr(n, 'color_name') else n for n in all_nations]
        shuffled = list(all_names)
        random.shuffle(shuffled)
        return BotGoals(prevail_goals=shuffled[:3], defeat_goals=shuffled[3:])



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
    w_claim_territory:    float = 1.0   # 8. Capturing neutral or enemy territory

    # --- Move-type weights (2 genes) ---
    w_random:             float = 0.30  # 8. Weight for random moves
    w_deceptive:          float = 0.15  # 9. Weight for deceptive moves
    # (intent weight is implicitly 1.0 - w_random - w_deceptive, clamped >= 0)

    # --- Turn-phase behaviour ---
    random_early_turns:    int  = 8     # bias toward random for first N turns
    deceptive_early_turns: int  = 5     # bias toward deceptive for first N turns

    # --- Adaptive behaviour ---
    adaptive_turn:         int  = 25    # when to start using opponent intel

    # --- Evaluator weights (18 genes for position-mode lookahead) ---
    ev_ghost_enemy:        float = 500.0
    ev_own_sov_dead:       float = -10000.0
    ev_ally_sov_dead:      float = -50.0
    ev_enemy_killable:     float = 200.0
    ev_enemy_trapped:      float = 80.0
    ev_enemy_unsupported:  float = 40.0
    ev_own_sov_killable:   float = -300.0
    ev_own_sov_trapped:    float = -100.0
    ev_allied_army:        float = 15.0
    ev_allied_knight:      float = 20.0
    ev_allied_champion:    float = 25.0
    ev_enemy_army:         float = -10.0
    ev_enemy_knight:       float = -15.0
    ev_enemy_champion:     float = -20.0
    ev_allied_champ_sup:   float = 30.0
    ev_enemy_champ_unsup:  float = 20.0
    ev_adjacent_enemy_sov: float = 25.0
    ev_champion_approach:  float = 5.0
    ev_territory_control:  float = 2.0

    # --- Diplomatic genes (6 fine-grained targeted genes + 1 rank decay gene) ---
    w_dipl_defeat_vs_defeat:  float = 1.8   # wars between nations in defeat list
    w_dipl_prevail_alliance:  float = 1.5   # alliances among nations in prevail list
    w_dipl_prevail_vs_defeat: float = 2.0   # wars between prevail and defeat nations
    w_dipl_opp_prevail_war:   float = 1.2   # wars between suspected opp prevail nations
    w_dipl_opp_defeat_ally:   float = 1.0   # alliances between suspected opp defeat nations
    w_dipl_peace:             float = 0.5   # de-escalation / returning to neutral
    top3_spread:              float = 0.5   # decay factor for 2nd/3rd human-guess rank

    # --- Architectural Genes (evolved) ---
    lookahead_depth:       int   = 2     # 1 = 1-ply, 2 = 2-ply minimax, 3 = 3-ply
    lookahead_beam:        int   = 3     # 1 to 4 candidate moves per ply
    hybrid_ratio:          float = 0.5   # 0.0 = 100% move score, 1.0 = 100% pos eval
    lookahead_mode:        str   = 'position'  # 'position' or 'action'

    # --- Runtime (not part of genome, not persisted) ---
    fitness:               float = 0.0

    def to_weights_dict(self):
        """Return the dict expected by bot.py scoring functions."""
        return {
            'kill_enemy':               self.w_kill_enemy,
            'advance_allied':           self.w_advance_allied,
            'protect_sovereign':        self.w_protect_sovereign,
            'muster_promote':           self.w_muster_promote,
            'champion_support':         self.w_champion_support,
            'endanger_enemy_sov':       self.w_endanger_enemy_sov,
            'unsupport_enemy_champ':    self.w_unsupport_enemy_ch,
            'claim_territory':          self.w_claim_territory,
            'adaptive_turn':            self.adaptive_turn,
            # Targeted fine-grained diplomacy weights
            'w_dipl_defeat_vs_defeat':  self.w_dipl_defeat_vs_defeat,
            'w_dipl_prevail_alliance':  self.w_dipl_prevail_alliance,
            'w_dipl_prevail_vs_defeat': self.w_dipl_prevail_vs_defeat,
            'w_dipl_opp_prevail_war':   self.w_dipl_opp_prevail_war,
            'w_dipl_opp_defeat_ally':   self.w_dipl_opp_defeat_ally,
            'w_dipl_peace':             self.w_dipl_peace,
            'top3_spread':              self.top3_spread,
            # Legacy fallbacks
            'w_diplomacy_war':          self.w_dipl_prevail_vs_defeat,
            'w_diplomacy_ally':         self.w_dipl_prevail_alliance,
            'w_diplomacy_peace':        self.w_dipl_peace,
        }

    def to_evaluator_weights(self):
        """Return the dict expected by evaluator.evaluate_position()."""
        return {
            'ghost_enemy':       self.ev_ghost_enemy,
            'own_sov_dead':      self.ev_own_sov_dead,
            'ally_sov_dead':     self.ev_ally_sov_dead,
            'enemy_killable':    self.ev_enemy_killable,
            'enemy_trapped':     self.ev_enemy_trapped,
            'enemy_unsupported': self.ev_enemy_unsupported,
            'own_sov_killable':  self.ev_own_sov_killable,
            'own_sov_trapped':   self.ev_own_sov_trapped,
            'allied_army':       self.ev_allied_army,
            'allied_knight':     self.ev_allied_knight,
            'allied_champion':   self.ev_allied_champion,
            'enemy_army':        self.ev_enemy_army,
            'enemy_knight':      self.ev_enemy_knight,
            'enemy_champion':    self.ev_enemy_champion,
            'allied_champ_sup':  self.ev_allied_champ_sup,
            'enemy_champ_unsup': self.ev_enemy_champ_unsup,
            'adjacent_enemy_sov': self.ev_adjacent_enemy_sov,
            'champion_approach': self.ev_champion_approach,
            'territory_control': self.ev_territory_control,
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
    def random_config(archetype=None):
        """Create a diverse BotConfig according to an archetype or randomized."""
        if archetype is None:
            archetype = random.choice(['speedster', 'positional', 'hybrid', 'deep', 'wild'])

        c = BotConfig(
            w_kill_enemy=random.uniform(0.2, 3.0),
            w_advance_allied=random.uniform(0.2, 3.0),
            w_protect_sovereign=random.uniform(0.2, 3.0),
            w_muster_promote=random.uniform(0.2, 3.0),
            w_champion_support=random.uniform(0.2, 3.0),
            w_endanger_enemy_sov=random.uniform(0.2, 3.0),
            w_unsupport_enemy_ch=random.uniform(0.2, 3.0),
            w_claim_territory=random.uniform(0.2, 3.0),
            w_random=random.uniform(0.0, 0.4),
            w_deceptive=random.uniform(0.0, 0.3),
            random_early_turns=random.randint(0, 15),
            deceptive_early_turns=random.randint(0, 12),
            adaptive_turn=random.randint(10, 40),
            # Diplomacy genes
            w_dipl_defeat_vs_defeat=random.uniform(0.5, 3.0),
            w_dipl_prevail_alliance=random.uniform(0.5, 3.0),
            w_dipl_prevail_vs_defeat=random.uniform(0.5, 3.0),
            w_dipl_opp_prevail_war=random.uniform(0.2, 2.5),
            w_dipl_opp_defeat_ally=random.uniform(0.2, 2.0),
            w_dipl_peace=random.uniform(0.0, 1.5),
            top3_spread=random.uniform(0.1, 0.9),
            # Evaluator weights — randomize around defaults
            ev_ghost_enemy=random.uniform(200, 800),
            ev_own_sov_dead=random.uniform(-15000, -5000),
            ev_ally_sov_dead=random.uniform(-200, 0),
            ev_enemy_killable=random.uniform(50, 500),
            ev_enemy_trapped=random.uniform(20, 200),
            ev_enemy_unsupported=random.uniform(10, 100),
            ev_own_sov_killable=random.uniform(-600, -100),
            ev_own_sov_trapped=random.uniform(-300, -20),
            ev_allied_army=random.uniform(5, 50),
            ev_allied_knight=random.uniform(8, 65),
            ev_allied_champion=random.uniform(10, 80),
            ev_enemy_army=random.uniform(-40, -2),
            ev_enemy_knight=random.uniform(-50, -3),
            ev_enemy_champion=random.uniform(-60, -5),
            ev_allied_champ_sup=random.uniform(10, 80),
            ev_enemy_champ_unsup=random.uniform(5, 60),
            ev_adjacent_enemy_sov=random.uniform(10, 80),
            ev_champion_approach=random.uniform(1, 20),
            ev_territory_control=random.uniform(0.5, 10.0),
        )

        if archetype == 'speedster':
            c.lookahead_depth = 1
            c.lookahead_beam = random.randint(2, 4)
            c.hybrid_ratio = random.uniform(0.0, 0.2)
        elif archetype == 'positional':
            c.lookahead_depth = 2
            c.lookahead_beam = random.randint(2, 3)
            c.hybrid_ratio = random.uniform(0.8, 1.0)
        elif archetype == 'hybrid':
            c.lookahead_depth = 2
            c.lookahead_beam = random.randint(2, 3)
            c.hybrid_ratio = random.uniform(0.35, 0.65)
        elif archetype == 'deep':
            c.lookahead_depth = random.choice([3, 4])
            c.lookahead_beam = random.randint(1, 3)
            c.hybrid_ratio = random.uniform(0.5, 1.0)
        else:  # wild
            c.lookahead_depth = random.randint(1, 4)
            c.lookahead_beam = random.randint(1, 3) if c.lookahead_depth >= 4 else random.randint(1, 4)
            c.hybrid_ratio = random.uniform(0.0, 1.0)

        # All freshstart archetypes get elevated war and coalition tendencies so
        # they bootstrap wars early and generate fitness signals from turn 1.
        # Evolution will tune these if peacefulness or disruption is a better strategy.
        c.w_dipl_prevail_vs_defeat = random.uniform(1.8, 3.5)
        c.w_dipl_defeat_vs_defeat  = random.uniform(1.5, 3.0)
        c.w_dipl_prevail_alliance  = random.uniform(1.2, 2.8)

        # 4-ply bots can only have a maximum beam width of 3
        if c.lookahead_depth >= 4:
            c.lookahead_beam = min(3, c.lookahead_beam)

        return c

    def explain_personality(self, rank=None) -> str:
        """Return a human-readable explanation of this bot's personality and tactics."""
        return describe_bot(self, rank=rank)


# ---------------------------------------------------------------------------
# Human-Readable Strategy Explainer
# ---------------------------------------------------------------------------

def describe_bot(config: BotConfig, rank=None) -> str:
    """Generate a rich, human-readable narrative explanation of a bot's personality and tactics."""
    title = f"BOT #{rank}" if rank is not None else "BOT PROFILE"
    if hasattr(config, 'fitness') and config.fitness > 0:
        title += f" (Fitness: {config.fitness:.1f})"

    # 1. Determine Archetype & Title
    depth = getattr(config, 'lookahead_depth', 1)
    beam = getattr(config, 'lookahead_beam', 3)
    hratio = getattr(config, 'hybrid_ratio', 0.5)

    if depth >= 4:
        archetype_name = "Deep Horizon Mastermind"
    elif hratio >= 0.75 and depth >= 2:
        archetype_name = "Positional Grandmaster"
    elif hratio <= 0.25 and depth == 1:
        archetype_name = "Tactical Blitz Striker"
    elif depth >= 3:
        archetype_name = "Deep Horizon Strategist"
    elif 0.35 <= hratio <= 0.65:
        archetype_name = "Hybrid Combat Duelist"
    elif config.w_endanger_enemy_sov >= 3.2 or config.ev_enemy_killable >= 300:
        archetype_name = "Ruthless Sovereign Assassin"
    elif config.w_muster_promote >= 3.5:
        archetype_name = "Legion Commander"
    else:
        archetype_name = "Balanced Tactical Bot"

    lines = []
    lines.append(f"{'='*66}")
    lines.append(f"  {title} — \"{archetype_name}\"")
    lines.append(f"{'='*66}")

    # 2. Engine & Thinking Style
    pos_pct = int(round(hratio * 100))
    move_pct = 100 - pos_pct
    lines.append(f"  • Thinking Style: {depth}-Ply Lookahead (Beam: {beam})")
    lines.append(f"    - Evaluation Blend: {pos_pct}% Positional Board Eval / {move_pct}% Tactical Move Scoring")

    # 3. Core Strategic Priorities
    priorities = []
    if config.w_endanger_enemy_sov >= 2.5 or config.ev_enemy_killable >= 250:
        priorities.append(f"Fierce sovereign hunting (danger move wt: {config.w_endanger_enemy_sov:.2f}, killable sov eval: +{config.ev_enemy_killable:.0f})")
    if config.w_muster_promote >= 2.5:
        priorities.append(f"High-tempo recruitment & promotion (muster move wt: {config.w_muster_promote:.2f})")
    if config.w_champion_support >= 2.5 or config.ev_allied_champ_sup >= 30:
        priorities.append(f"Champion support formations (champ support wt: {config.w_champion_support:.2f}, support eval: +{config.ev_allied_champ_sup:.0f})")
    if config.ev_enemy_champion <= -30:
        priorities.append(f"Aggressive champion elimination (enemy champion penalty: {config.ev_enemy_champion:.1f})")
    if config.w_kill_enemy >= 1.5:
        priorities.append(f"Direct tactical combat (kill enemy move wt: {config.w_kill_enemy:.2f})")
    if getattr(config, 'w_claim_territory', 1.0) >= 2.0 or getattr(config, 'ev_territory_control', 2.0) >= 5.0:
        priorities.append(f"Territorial expansion & army recruitment (claim move wt: {getattr(config, 'w_claim_territory', 1.0):.2f}, territory eval: +{getattr(config, 'ev_territory_control', 2.0):.1f})")
    if not priorities:
        priorities.append("Balanced all-round positional and tactical play")

    lines.append("  • Strategic Priorities:")
    for p in priorities:
        lines.append(f"    - {p}")

    # 4. Self-Preservation vs Aggression
    if config.w_protect_sovereign < 0.5:
        defense_desc = f"Offense-First (protect_sov: {config.w_protect_sovereign:.2f}) — relies on overwhelming counter-threats rather than turtling."
    elif config.w_protect_sovereign >= 2.0:
        defense_desc = f"Fortified Defense (protect_sov: {config.w_protect_sovereign:.2f}) — keeps sovereign heavily guarded and retreats when pressured."
    else:
        defense_desc = f"Balanced (protect_sov: {config.w_protect_sovereign:.2f}) — defends when threatened without sacrificing offensive tempo."
    lines.append(f"  • Self-Preservation: {defense_desc}")

    # 5. Opening Style & Timing
    non_intent = config.w_random + config.w_deceptive
    if non_intent < 0.05:
        opening = "Pure Intent from Turn 1 (no bluffing or random moves)"
    else:
        opening = f"Bluffing early game (random: {config.w_random*100:.0f}%, deceptive: {config.w_deceptive*100:.0f}% for first {max(config.random_early_turns, config.deceptive_early_turns)} turns)"
    lines.append(f"  • Opening Style: {opening}")
    lines.append(f"  • Hunter Intelligence: Unlocks adaptive sovereign targeting on Turn {config.adaptive_turn}")
    lines.append(f"{'='*66}")
    # 6. Diplomacy Style
    d_dvd = getattr(config, 'w_dipl_defeat_vs_defeat',  getattr(config, 'w_diplomacy_war', 1.8))
    d_pal = getattr(config, 'w_dipl_prevail_alliance',  getattr(config, 'w_diplomacy_ally', 1.5))
    d_pvd = getattr(config, 'w_dipl_prevail_vs_defeat', getattr(config, 'w_diplomacy_war', 2.0))
    d_opw = getattr(config, 'w_dipl_opp_prevail_war',   getattr(config, 'w_diplomacy_war', 1.2))
    d_oda = getattr(config, 'w_dipl_opp_defeat_ally',   getattr(config, 'w_diplomacy_ally', 1.0))
    d_pea = getattr(config, 'w_dipl_peace',             getattr(config, 'w_diplomacy_peace', 0.5))
    t3    = getattr(config, 'top3_spread',              0.5)

    if d_pvd >= 2.2 and d_dvd >= 2.0:
        dipl_style = "Aggressive Warmonger (incites wars on defeat goals & third parties)"
    elif d_opw >= 2.0:
        dipl_style = "Disruptive Chaos Agent (incites wars among opponent factions)"
    elif d_pal >= 2.0 and d_oda >= 1.5:
        dipl_style = "Coalition Architect (forges alliances & shields defeat targets)"
    elif d_pea >= 1.5:
        dipl_style = "Peacemaker (actively de-escalates unwanted conflicts)"
    else:
        dipl_style = "Pragmatic Machiavellian (balanced targeted diplomacy)"

    lines.append(f"  • Diplomacy Style: {dipl_style}")
    lines.append(f"    - Defeat vs Defeat War:   {d_dvd:.2f}  |  Prevail Alliance:      {d_pal:.2f}")
    lines.append(f"    - Prevail vs Defeat War:  {d_pvd:.2f}  |  Opp Prevail War:       {d_opw:.2f}")
    lines.append(f"    - Opp Defeat Shield Ally: {d_oda:.2f}  |  Peace / De-escalate:   {d_pea:.2f}")
    lines.append(f"    - Opponent rank spread decay: {t3:.2f}")
    lines.append(f"{'='*66}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EvolvableBot — bot player that uses BotConfig
# ---------------------------------------------------------------------------

class EvolvableBot:
    """A bot player driven by a BotConfig genome.

    Wraps Player + BotMemory and provides compute_action / execute_action
    matching the same pattern as bot.py's compute_bot_action / execute_bot_action.
    """

    def __init__(self, config: BotConfig = None, player_id='bot'):
        self.player = Player(is_bot=True, player_id=player_id)
        self.config = config
        self.memory = BotMemory(debug=False)
        self._weights = config.to_weights_dict() if config else {}
        self._eval_weights = config.to_evaluator_weights() if config else {}

    def record_opponent_move(self, turn_number, nation, unit_type_str,
                             from_hex, to_hex, action_type, nation_names=None):
        """Record an opponent move in memory and update suspicion scores."""
        self.memory.record(turn_number, nation, unit_type_str,
                           from_hex, to_hex, action_type)
        # Simple suspicion: add points for moving a nation
        self.memory.add_score(nation.color_name, 3, nation_names)

    def guess_opponent_faction(self, nation_list, exclude_names=()):
        """Return the suspected color_name of the opponent's top prevail nation (top-1 guess)."""
        guess = self.memory.guess_faction(nation_list, exclude_names=set(exclude_names))
        return guess.color_name if guess else None

    def guess_top3_opponents(self, nation_list, exclude_names=()):
        """Return list of up to 3 color_name strings (ranked prevail guesses) for the opponent."""
        top3 = self.memory.guess_top3_factions(nation_list, exclude_names=set(exclude_names))
        return [n.color_name for n, _ in top3]

    def guess_bottom3_opponents(self, nation_list, exclude_names=()):
        """Return list of up to 3 color_name strings (inferred opponent defeat targets)."""
        bottom3 = self.memory.guess_bottom3_factions(nation_list, exclude_names=set(exclude_names))
        return [n.color_name for n, _ in bottom3]

    def compute_action(self, grid, global_cooldown_name, nation_list, turn_number,
                       dipl_state=None, bot_goals=None):
        """Select an action without executing it.  Returns action tuple or None.

        dipl_state: DiplomacyState for cooldown checking (None = skip diplomacy).
        bot_goals:  BotGoals with prevail/defeat goal lists.
        """
        suspected_ri  = None
        top3_names    = None
        bottom3_names = None
        if turn_number >= self.config.adaptive_turn:
            exclude = set(bot_goals.prevail_goals) if bot_goals else set()
            top3_names    = self.guess_top3_opponents(nation_list, exclude_names=exclude)
            bottom3_names = self.guess_bottom3_opponents(nation_list, exclude_names=exclude)
            suspected_ri  = top3_names[0] if top3_names else None

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
            return self._compute_intent(grid, global_cooldown_name, nation_list,
                                        turn_number, suspected_ri,
                                        dipl_state=dipl_state, bot_goals=bot_goals,
                                        top3_names=top3_names,
                                        bottom3_names=bottom3_names)
        elif move_type == 'random':
            return self._compute_random(grid, global_cooldown_name, nation_list,
                                        turn_number, suspected_ri,
                                        bot_goals=bot_goals)
        else:  # deceptive
            return self._compute_deceptive(grid, global_cooldown_name, nation_list,
                                           turn_number, suspected_ri,
                                           bot_goals=bot_goals)

    def _compute_intent(self, grid, gci, nation_list, turn, suspected_ri,
                        dipl_state=None, bot_goals=None, top3_names=None,
                        bottom3_names=None):
        """Strategic intent using config weights, with optional lookahead and hybrid scoring."""
        from bot import _lookahead_best

        # 1. Diplomacy actions are evaluated 1-ply (not mixed into the multi-ply tree)
        best_dipl = None
        if dipl_state is not None and bot_goals is not None:
            dipl_actions = _gather_actions(grid, self.player, gci, nation_list,
                                           suspected_human_ri=suspected_ri,
                                           turn_number=turn,
                                           weights=self._weights,
                                           dipl_state=dipl_state,
                                           bot_goals=bot_goals,
                                           top3_names=top3_names,
                                           bottom3_names=bottom3_names,
                                           exclude_diplomacy=False)
            dipl_valid = [a for a in dipl_actions if a[1] == 'diplomacy' and a[0] > -1000]
            if dipl_valid:
                best_dipl = max(dipl_valid, key=lambda a: a[0])

        # 2. Military actions: multi-ply lookahead or 1-ply tactical scoring
        if self.config.lookahead_depth > 1 or self.config.hybrid_ratio > 0.0:
            military = _lookahead_best(
                grid, self.player, gci, nation_list,
                turn, suspected_ri, self._weights,
                depth=self.config.lookahead_depth - 1,
                beam_width=self.config.lookahead_beam,
                mode=self.config.lookahead_mode,
                eval_weights=self._eval_weights,
                hybrid_ratio=self.config.hybrid_ratio,
                bot_goals=bot_goals,
                top3_names=top3_names,
                bottom3_names=bottom3_names)
        else:
            mil_actions = _gather_actions(grid, self.player, gci, nation_list,
                                          suspected_human_ri=suspected_ri,
                                          turn_number=turn,
                                          weights=self._weights,
                                          bot_goals=bot_goals,
                                          top3_names=top3_names,
                                          bottom3_names=bottom3_names,
                                          exclude_diplomacy=True)
            valid = [a for a in mil_actions if a[0] > -1000]
            if valid:
                best = max(a[0] for a in valid)
                threshold = (best * 0.85) if best > 0 else (best - 50)
                top_tier = [a for a in valid if a[0] >= threshold]
                military = random.choice(top_tier)
            else:
                military = None

        # 3. Choose between best diplomacy and best military
        # If position-mode lookahead was used, military[0] includes the board evaluation
        # baseline (~500 pts). We evaluate diplomacy on the same hybrid scale for fair comparison.
        if best_dipl is not None:
            if military is None:
                return (*best_dipl, 'intent')
            if self.config.hybrid_ratio > 0.0 and self.config.lookahead_mode == 'position':
                from evaluator import evaluate_position, _derive_ghost_set
                root_pos = evaluate_position(grid, bot_goals=bot_goals, nation_list=nation_list,
                                             weights=self._eval_weights,
                                             ghost_name_set=_derive_ghost_set(grid))
                dipl_eff_score = (1.0 - self.config.hybrid_ratio) * best_dipl[0] + self.config.hybrid_ratio * root_pos
            else:
                dipl_eff_score = best_dipl[0]

            if dipl_eff_score > military[0]:
                return (*best_dipl, 'intent')
            return (*military, 'intent')
        if military is not None:
            return (*military, 'intent')
        return None

    def _compute_random(self, grid, gci, nation_list, turn, suspected_ri, bot_goals=None):
        """Purely random legal action."""
        eligible = _eligible_nations(self.player, gci, nation_list)
        if not eligible:
            return None

        if bot_goals is not None:
            allied_name_set = set(bot_goals.prevail_goals)
        elif getattr(self.player, 'prevail_picks', None):
            allied_name_set = {n.color_name for n in self.player.prevail_picks}
        else:
            allied_name_set = set()

        pool = []
        for nation in eligible:
            for unit in grid.get_all_nation_units(nation):
                pool += [(0, 'move', unit, c) for c in grid.get_valid_moves(unit)]
                for c in grid.get_valid_attacks(unit):
                    tq, tr = c
                    allied_sovs = [s for s in grid.sovereigns.get((tq, tr), [])
                                   if s.nation.color_name in allied_name_set
                                   and unit.nation.is_enemy(s.nation)]
                    if not allied_sovs:
                        pool.append((0, 'attack', unit, c))
            for coord in grid.get_recruit_hexes(nation, turn_number=turn):
                pool.append((0, 'recruit', nation, coord))
            for coord in grid.get_promote_hexes(nation):
                pool.append((0, 'promote', nation, coord))

        if not pool:
            return None

        # Apply adaptive adjustments even to random pool
        pool = _adaptive_sovereign_adjustments(
            grid, pool, turn_number=turn,
            nation_list=nation_list, bot_goals=bot_goals)
        valid = [a for a in pool if a[0] > -1000]
        if valid:
            pool = valid

        chosen = random.choice(pool)
        return (*chosen, 'random')

    def _compute_deceptive(self, grid, gci, nation_list, turn, suspected_ri, bot_goals=None):
        """Deceptive move: temporarily pretend to have different goals.

        Uses intent scoring with randomized fake goals so the move
        looks like the bot is fighting for a different set of nations.
        """
        if bot_goals is not None:
            fake_goals = BotGoals.random(nation_list)
            actions = _gather_actions(grid, self.player, gci, nation_list,
                                      suspected_human_ri=suspected_ri,
                                      turn_number=turn,
                                      weights=self.config.to_weights_dict(),
                                      bot_goals=fake_goals)
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
        else:
            return self._compute_intent(grid, gci, nation_list, turn, suspected_ri,
                                        bot_goals=bot_goals)

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

        # Assign random goals for each bot across all 6 nations
        self.bot1_goals = BotGoals.random(self.nations)
        self.bot2_goals = BotGoals.random(self.nations)

        self.bot1 = EvolvableBot(config1, player_id='bot1')
        self.bot2 = EvolvableBot(config2, player_id='bot2')

        # Wire goals into player prediction slots so compute_score() works.
        # BotGoals stores color_name strings; player picks need Nation objects.
        _by_name = {n.color_name: n for n in self.nations}
        self.bot1.player.prevail_picks = [_by_name[c] for c in self.bot1_goals.prevail_goals]
        self.bot1.player.defeat_picks  = [_by_name[c] for c in self.bot1_goals.defeat_goals]
        self.bot2.player.prevail_picks = [_by_name[c] for c in self.bot2_goals.prevail_goals]
        self.bot2.player.defeat_picks  = [_by_name[c] for c in self.bot2_goals.defeat_goals]


        self.grid = MapGrid()
        self.grid.generate_map(nations=self.nations)

        self.turn_number = 1
        self.grid.turn_number = self.turn_number
        self.global_cooldown_name = None

        # Diplomacy state (pure-Python, no pygame)
        from diplomacy_panel import DiplomacyState
        self.dipl_state = DiplomacyState()

        # Guess accuracy tracking (populated after play())
        self.guess_correct = 0   # how many bots guessed correctly
        self.guess_total   = 0   # total guesses attempted (0, 1, or 2)

    def play(self) -> str:
        """Play the full game.  Returns a RESULT_* constant."""
        bots = [self.bot1, self.bot2]
        goals = [self.bot1_goals, self.bot2_goals]
        current = 0

        for _ in range(self.max_turns):
            self.grid.turn_number = self.turn_number
            bot = bots[current]
            bot_goal = goals[current]
            opponent = bots[1 - current]

            action = bot.compute_action(
                self.grid, self.global_cooldown_name,
                self.nations, self.turn_number,
                dipl_state=self.dipl_state,
                bot_goals=bot_goal)

            if action is None:
                # No legal moves — skip turn
                self.dipl_state.tick_cooldowns()
                current = 1 - current
                self.turn_number += 1
                continue

            # Execute the action
            moved_nation, action_type, desc = _execute(self.grid, action, dipl_state=self.dipl_state)

            if moved_nation is None:
                # Execution failed — skip turn
                self.dipl_state.tick_cooldowns()
                current = 1 - current
                self.turn_number += 1
                continue

            # Tick diplomacy cooldowns every turn
            self.dipl_state.tick_cooldowns()

            # Update cooldowns
            bot.player.add_to_cooldown(moved_nation)
            self.global_cooldown_name = moved_nation.color_name

            # Record the move for the opponent's memory (skip for diplomacy actions)
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
                from units import Army
                from units import Champion, Sovereign
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

            # Check end condition: game ends when 3+ sovereigns are destroyed
            self.grid.check_ghost_nations(self.nations)
            if self.grid.count_ghost_nations(self.nations) >= 3:
                s1 = self.bot1.player.compute_score()
                s2 = self.bot2.player.compute_score()
                self._record_guess_accuracy()
                if s1 > s2:
                    return RESULT_BOT1_WIN
                if s2 > s1:
                    return RESULT_BOT2_WIN
                return RESULT_TIE

            # Advance turn
            current = 1 - current
            self.turn_number += 1

        self._record_guess_accuracy()
        return RESULT_DRAW

    def _record_guess_accuracy(self):
        """Check each bot's guess of the opponent's prevail nations."""
        for guesser, opp_goals in [(self.bot1, self.bot2_goals),
                                   (self.bot2, self.bot1_goals)]:
            my_goals = self.bot1_goals if guesser is self.bot1 else self.bot2_goals
            guess_ri = guesser.guess_opponent_faction(self.nations, exclude_names=my_goals.prevail_goals)
            if guess_ri is not None:
                self.guess_total += 1
                if guess_ri in opp_goals.prevail_goals:
                    self.guess_correct += 1


# ---------------------------------------------------------------------------
# Tournament — round-robin within one generation
# ---------------------------------------------------------------------------

class Tournament:
    """Round-robin tournament for a population of BotConfigs."""

    def __init__(self, configs: list, games_per_pair: int = 1,
                 max_turns: int = MAX_TURNS):
        self.configs = configs
        self.games_per_pair = games_per_pair
        self.max_turns = max_turns

    def run(self) -> list:
        """Play all matchups and return configs with updated fitness scores.

        Fitness scoring: +3 win, +1 tie, +0 loss/draw.
        Also tracks aggregate guess accuracy across all games.
        """
        n = len(self.configs)
        # Reset fitness
        for c in self.configs:
            c.fitness = 0.0

        self.guess_correct = 0
        self.guess_total   = 0
        self.draws         = 0
        self.total_games   = 0

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

                    # Accumulate guess stats
                    self.guess_correct += game.guess_correct
                    self.guess_total   += game.guess_total
                    self.total_games   += 1
                    if result == RESULT_DRAW:
                        self.draws += 1

                    if result == RESULT_BOT1_WIN:
                        self.configs[i].fitness += 3
                    elif result == RESULT_BOT2_WIN:
                        self.configs[j].fitness += 3
                    elif result == RESULT_TIE:
                        self.configs[i].fitness += 1
                        self.configs[j].fitness += 1
                    elif result == RESULT_DRAW:
                        # Game hit turn limit — score based on partial goal completion
                        s1 = game.bot1.player.compute_score()
                        s2 = game.bot2.player.compute_score()
                        if s1 > s2:
                            self.configs[i].fitness += 3
                        elif s2 > s1:
                            self.configs[j].fitness += 3
                        else:
                            self.configs[i].fitness += 1
                            self.configs[j].fitness += 1

                    played += 1

        return self.configs

    @property
    def guess_accuracy(self):
        """Return guess accuracy as a float 0.0-1.0, or None if no guesses."""
        if self.guess_total == 0:
            return None
        return self.guess_correct / self.guess_total

    @property
    def decisive_rate(self):
        """Fraction of games that ended decisively (before the turn limit)."""
        if self.total_games == 0:
            return None
        return 1.0 - (self.draws / self.total_games)


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
    'w_claim_territory':    (0.0, 5.0),
    'w_random':             (0.0, 1.0),
    'w_deceptive':          (0.0, 1.0),
    'random_early_turns':   (0, 30),
    'deceptive_early_turns': (0, 25),
    'adaptive_turn':         (10, 40),
    # Diplomacy genes (fine-grained targeted diplomacy)
    'w_dipl_defeat_vs_defeat':  (0.0, 5.0),
    'w_dipl_prevail_alliance':  (0.0, 5.0),
    'w_dipl_prevail_vs_defeat': (0.0, 5.0),
    'w_dipl_opp_prevail_war':   (0.0, 5.0),
    'w_dipl_opp_defeat_ally':   (0.0, 5.0),
    'w_dipl_peace':             (0.0, 3.0),
    'top3_spread':              (0.0, 1.0),
     # Architectural genes (evolvable depth, beam, and hybrid evaluation)
    'lookahead_depth':      (1, 4),
    'lookahead_beam':       (1, 4),
    'hybrid_ratio':         (0.0, 1.0),
    # Evaluator weights
    'ev_ghost_enemy':       (100.0, 1000.0),
    'ev_own_sov_dead':      (-20000.0, -2000.0),
    'ev_ally_sov_dead':     (-500.0, 0.0),
    'ev_enemy_killable':    (50.0, 600.0),
    'ev_enemy_trapped':     (10.0, 300.0),
    'ev_enemy_unsupported': (5.0, 150.0),
    'ev_own_sov_killable':  (-800.0, -50.0),
    'ev_own_sov_trapped':   (-400.0, -10.0),
    'ev_allied_army':       (2.0, 60.0),
    'ev_allied_knight':     (3.0, 75.0),
    'ev_allied_champion':   (5.0, 100.0),
    'ev_enemy_army':        (-60.0, -1.0),
    'ev_enemy_knight':      (-70.0, -2.0),
    'ev_enemy_champion':    (-80.0, -2.0),
    'ev_allied_champ_sup':  (5.0, 100.0),
    'ev_enemy_champ_unsup': (2.0, 80.0),
    'ev_adjacent_enemy_sov': (5.0, 100.0),
    'ev_champion_approach': (0.5, 30.0),
    'ev_territory_control': (0.0, 15.0),
}

# Fields that are integers
_INT_GENES = {'random_early_turns', 'deceptive_early_turns', 'adaptive_turn', 'lookahead_depth', 'lookahead_beam'}

# All gene field names (31 genes)
_GENE_NAMES = list(_GENE_RANGES.keys())


class GeneticAlgorithm:
    """Genetic algorithm engine for evolving BotConfigs."""

    def __init__(self, population_size=settings.EVO_POPULATION,
                 generations=settings.EVO_GENERATIONS,
                 elite_count=settings.EVO_ELITE_COUNT,
                 mutation_rate=settings.EVO_MUTATION_RATE,
                 mutation_reset_rate=settings.EVO_MUTATION_RESET,
                 games_per_pair=settings.EVO_GAMES_PER_PAIR,
                 max_turns=MAX_TURNS, seed_configs=None,
                 lookahead_depth=None, lookahead_beam=None, lookahead_mode='position'):
        self.population_size = population_size
        self.generations = generations
        self.elite_count = elite_count
        self.mutation_rate = mutation_rate
        self.mutation_reset_rate = mutation_reset_rate
        self.games_per_pair = games_per_pair
        self.max_turns = max_turns
        self.lookahead_depth = lookahead_depth
        self.lookahead_beam = lookahead_beam
        self.lookahead_mode = lookahead_mode

        # Initialize population
        if seed_configs:
            # Resume: start with seed configs + fill with mutated variants + random
            self.population = []
            for sc in seed_configs[:self.elite_count]:
                sc_copy = copy.deepcopy(sc)
                if sc_copy.lookahead_depth >= 4:
                    sc_copy.lookahead_beam = min(3, sc_copy.lookahead_beam)
                self.population.append(sc_copy)

            # Inject a 4-ply upgraded mutant of the top seed so 4-ply enters the arena immediately
            if seed_configs:
                champ_4ply = copy.deepcopy(seed_configs[0])
                champ_4ply.lookahead_depth = 4
                champ_4ply.lookahead_beam = min(3, champ_4ply.lookahead_beam)
                self._mutate(champ_4ply, rate=0.15)
                champ_4ply.lookahead_depth = 4
                champ_4ply.lookahead_beam = min(3, champ_4ply.lookahead_beam)
                self.population.append(champ_4ply)

            # Fill remaining with mutated variants of seeds + random immigrants
            while len(self.population) < self.population_size:
                if random.random() < 0.5 and seed_configs:
                    # Mutated variant of a seed
                    parent = copy.deepcopy(random.choice(seed_configs))
                    self._mutate(parent, rate=0.30)  # higher mutation for diversity
                    if parent.lookahead_depth >= 4:
                        parent.lookahead_beam = min(3, parent.lookahead_beam)
                    self.population.append(parent)
                else:
                    immigrant = BotConfig.random_config()
                    if immigrant.lookahead_depth >= 4:
                        immigrant.lookahead_beam = min(3, immigrant.lookahead_beam)
                    self.population.append(immigrant)
        else:
            # Seed fresh population with diverse archetypes
            archetypes = ['speedster', 'positional', 'hybrid', 'deep', 'wild']
            self.population = [BotConfig.random_config(archetype=archetypes[i % len(archetypes)])
                                for i in range(self.population_size)]

        # Apply explicit lookahead overrides if provided via CLI
        for c in self.population:
            if self.lookahead_depth is not None:
                c.lookahead_depth = self.lookahead_depth
            if self.lookahead_beam is not None:
                c.lookahead_beam = self.lookahead_beam
            if self.lookahead_mode is not None:
                c.lookahead_mode = self.lookahead_mode
            if c.lookahead_depth >= 4:
                c.lookahead_beam = min(3, c.lookahead_beam)

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
            guess_acc = tournament.guess_accuracy

            if progress_callback:
                top4 = self.population[:4]
                progress_callback(gen, best_fit, avg_fit, self.population[0],
                                  guess_accuracy=guess_acc, top4=top4,
                                  decisive_rate=tournament.decisive_rate)

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

            # Apply explicit lookahead overrides if provided via CLI
            for c in self.population:
                if self.lookahead_depth is not None:
                    c.lookahead_depth = self.lookahead_depth
                if self.lookahead_beam is not None:
                    c.lookahead_beam = self.lookahead_beam
                if self.lookahead_mode is not None:
                    c.lookahead_mode = self.lookahead_mode
                if getattr(c, 'lookahead_depth', 1) >= 4:
                    c.lookahead_beam = min(3, getattr(c, 'lookahead_beam', 3))

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

        # 4-ply bots can only have a maximum beam width of 3
        if getattr(config, 'lookahead_depth', 1) >= 4:
            config.lookahead_beam = min(3, getattr(config, 'lookahead_beam', 3))

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
                        generations=0, top_n=settings.EVO_TOP_N_PERSIST):
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
        # Backward-compatibility for older bot_configs.json files
        if 'w_diplomacy_war' in d:
            old_war = float(d['w_diplomacy_war'])
            c.w_dipl_defeat_vs_defeat  = old_war
            c.w_dipl_prevail_vs_defeat = old_war
            c.w_dipl_opp_prevail_war   = old_war
        if 'w_diplomacy_ally' in d:
            old_ally = float(d['w_diplomacy_ally'])
            c.w_dipl_prevail_alliance = old_ally
            c.w_dipl_opp_defeat_ally  = old_ally
        if 'w_diplomacy_peace' in d:
            c.w_dipl_peace = float(d['w_diplomacy_peace'])

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

def _progress(gen, best_fit, avg_fit, best_config, guess_accuracy=None, top4=None,
              decisive_rate=None):
    """Print progress and rich human-readable personality explainer for each generation."""
    guess_str    = f"{guess_accuracy*100:.0f}%"  if guess_accuracy  is not None else "n/a"
    decisive_str = f"{decisive_rate*100:.0f}%"   if decisive_rate   is not None else "n/a"
    print(f"\n{'='*66}")
    print(f"  GENERATION {gen:3d} COMPLETE | Best: {best_fit:6.1f} | Avg: {avg_fit:5.1f}"
          f" | Deduction: {guess_str} | Decisive: {decisive_str}")

    # Leaderboard summary line
    if top4:
        parts = []
        for i, cfg in enumerate(top4, 1):
            d = getattr(cfg, 'lookahead_depth', 1)
            parts.append(f"#{i} {d}ply f={cfg.fitness:.1f}")
        print(f"  Leaderboard: {' | '.join(parts)}")
    print(f"{'='*66}")

    configs_to_show = top4 if top4 else [best_config]
    for i, cfg in enumerate(configs_to_show, 1):
        print(describe_bot(cfg, rank=f"{i} (Gen {gen})"))
        print()


def main():
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    parser = argparse.ArgumentParser(
        description='Six Nations -- Bot Evolution Chamber')
    parser.add_argument('--population', type=int, default=settings.EVO_POPULATION,
                        help=f'Population size per generation (default: {settings.EVO_POPULATION})')
    parser.add_argument('--generations', type=int, default=settings.EVO_GENERATIONS,
                        help=f'Number of generations to evolve (default: {settings.EVO_GENERATIONS})')
    parser.add_argument('--games', type=int, default=settings.EVO_GAMES_PER_PAIR,
                        help=f'Games per matchup pair (default: {settings.EVO_GAMES_PER_PAIR})')
    parser.add_argument('--max-turns', type=int, default=settings.EVO_MAX_TURNS,
                        help=f'Max turns per game (default: {settings.EVO_MAX_TURNS})')
    parser.add_argument('--freshstart', '--fresh', action='store_true',
                        help='Start a fresh evolution run instead of resuming from existing configs')
    parser.add_argument('--output', type=str, default=DEFAULT_CONFIG_PATH,
                        help='Output JSON filepath (default: bot_configs.json)')
    parser.add_argument('--depth', type=int, default=None,
                        help='Override lookahead depth for all bots (default: evolved per bot)')
    parser.add_argument('--beam', type=int, default=None,
                        help='Override lookahead beam for all bots (default: evolved per bot)')
    parser.add_argument('--mode', type=str, default='position',
                        choices=['action', 'position'],
                        help='Lookahead mode (default: position)')
    args = parser.parse_args()

    print("=" * 66)
    print("        SIX NATIONS -- ULTIMATE COMBAT BOT STABLE")
    print("=" * 66)
    print(f"  Population: {args.population}  |  Generations: {args.generations}")
    print(f"  Games/pair: {args.games}  |  Max turns: {args.max_turns}")
    if args.depth is not None or args.beam is not None:
        print(f"  Lookahead override: depth={args.depth}  beam={args.beam}  mode={args.mode}")
    else:
        print(f"  Evolving: Depth (1-3), Beam (1-4), Hybrid Eval (0-100%), Move & Board Weights")

    seed_configs = None
    should_resume = not args.freshstart
    if should_resume and os.path.exists(args.output):
        seed_configs = load_top_configs(args.output)
        if seed_configs:
            print(f"  Resuming from {len(seed_configs)} saved configs in {args.output}")
            if args.depth is not None or args.beam is not None:
                for c in seed_configs:
                    if args.depth is not None:
                        c.lookahead_depth = args.depth
                    if args.beam is not None:
                        c.lookahead_beam = args.beam
                    if args.mode is not None:
                        c.lookahead_mode = args.mode
    elif args.freshstart:
        print(f"  Starting fresh archetype-seeded population (--freshstart enabled)")
    else:
        print(f"  No existing config found at {args.output}, starting fresh archetype population")

    print()

    ga = GeneticAlgorithm(
        population_size=args.population,
        generations=args.generations,
        games_per_pair=args.games,
        max_turns=args.max_turns,
        seed_configs=seed_configs,
        lookahead_depth=args.depth,
        lookahead_beam=args.beam,
        lookahead_mode=args.mode,
    )

    t0 = time.time()
    interrupted = False
    try:
        final = ga.evolve(progress_callback=_progress)
    except KeyboardInterrupt:
        interrupted = True
        print("\n\n  !! Interrupted — saving best configs so far...")
        ga.population.sort(key=lambda c: c.fitness, reverse=True)
        final = ga.population

    elapsed = time.time() - t0

    if interrupted:
        print(f"  Partial evolution saved after {elapsed:.1f}s")
    else:
        print(f"\n  Evolution completed in {elapsed:.1f}s")

    # Determine total generations (including any previous runs)
    total_gens = args.generations
    if should_resume and os.path.exists(args.output):
        try:
            with open(args.output) as f:
                old_data = json.load(f)
            total_gens += old_data.get('generations', 0)
        except Exception:
            pass

    persist_top_configs(final, filepath=args.output,
                        generations=total_gens)

    # Print full human-readable narrative profile of #1 champion bot
    print("\n" + describe_bot(final[0], rank=1) + "\n")

    # Print summary of top 4
    print("  -- TOP 4 EVOLVED BOT STABLE --\n")
    for i, c in enumerate(final[:4]):
        depth = getattr(c, 'lookahead_depth', 1)
        beam = getattr(c, 'lookahead_beam', 3)
        hratio = getattr(c, 'hybrid_ratio', 0.5)
        print(f"  #{i+1}  fitness={c.fitness:.1f} | {depth}-ply (beam {beam}) | hybrid={hratio*100:.0f}% pos")
        print(f"      kill={c.w_kill_enemy:.2f}  advance={c.w_advance_allied:.2f}  protect_sov={c.w_protect_sovereign:.2f}")
        print(f"      muster={c.w_muster_promote:.2f}  champ_sup={c.w_champion_support:.2f}  danger_sov={c.w_endanger_enemy_sov:.2f}")
        print(f"      eval: ghost={c.ev_ghost_enemy:.0f}  killable_sov={c.ev_enemy_killable:.0f}  army={c.ev_allied_army:.1f}/{c.ev_enemy_army:.1f}  champ={c.ev_allied_champion:.1f}/{c.ev_enemy_champion:.1f}")
        print()


if __name__ == '__main__':
    main()

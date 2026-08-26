"""
Six Nations — Evolved vs Original Bot Benchmark

Pits evolved bots (from bot_configs.json) against the original default bot
(all weights = 1.0) in a series of games to measure win rates.

Usage:
    python benchmark.py                  # 20 games per evolved config
    python benchmark.py --games 50       # 50 games per config
    python benchmark.py --config path    # custom config file
"""

import argparse
import os
import random
import sys
import time

# Headless mode
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from evolution import (
    BotConfig, EvolvableBot, HeadlessGame, load_top_configs,
    RESULT_BOT1_WIN, RESULT_BOT2_WIN, RESULT_TIE, RESULT_DRAW,
    MAX_TURNS,
)


def run_matchup(evolved_config, default_config, num_games, max_turns=MAX_TURNS):
    """Play num_games between evolved and default.

    Each game alternates who goes first (bot1 vs bot2).
    Returns dict with win/loss/tie/draw counts from evolved bot's perspective.
    """
    results = {'evolved_wins': 0, 'default_wins': 0, 'ties': 0, 'draws': 0}

    for i in range(num_games):
        seed = random.randint(0, 2**31)

        # Alternate who is bot1 vs bot2
        if i % 2 == 0:
            game = HeadlessGame(evolved_config, default_config,
                                max_turns=max_turns, seed=seed)
            result = game.play()
            if result == RESULT_BOT1_WIN:
                results['evolved_wins'] += 1
            elif result == RESULT_BOT2_WIN:
                results['default_wins'] += 1
            elif result == RESULT_TIE:
                results['ties'] += 1
            else:
                results['draws'] += 1
        else:
            game = HeadlessGame(default_config, evolved_config,
                                max_turns=max_turns, seed=seed)
            result = game.play()
            if result == RESULT_BOT2_WIN:
                results['evolved_wins'] += 1
            elif result == RESULT_BOT1_WIN:
                results['default_wins'] += 1
            elif result == RESULT_TIE:
                results['ties'] += 1
            else:
                results['draws'] += 1

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark evolved bots vs the original default bot')
    parser.add_argument('--games', type=int, default=20,
                        help='Number of games per evolved config (default: 20)')
    parser.add_argument('--max-turns', type=int, default=MAX_TURNS,
                        help=f'Max turns per game (default: {MAX_TURNS})')
    parser.add_argument('--config', type=str,
                        default=os.path.join(os.path.dirname(__file__),
                                             'bot_configs.json'),
                        help='Path to evolved configs JSON')
    args = parser.parse_args()

    evolved_configs = load_top_configs(args.config)
    if not evolved_configs:
        print(f"No evolved configs found at {args.config}")
        print("Run 'python evolution.py' first to generate configs.")
        sys.exit(1)

    default_config = BotConfig()  # all weights = 1.0, default random/deceptive

    print("=" * 60)
    print("  EVOLVED vs ORIGINAL BOT BENCHMARK")
    print("=" * 60)
    print(f"  Games per matchup: {args.games}  |  Max turns: {args.max_turns}")
    print(f"  Evolved configs: {len(evolved_configs)} loaded from {args.config}")
    print(f"  Default config: all weights = 1.0, random={default_config.w_random:.2f}, "
          f"deceptive={default_config.w_deceptive:.2f}")
    print()

    total_evolved_wins = 0
    total_default_wins = 0
    total_ties = 0
    total_draws = 0

    for i, evo_config in enumerate(evolved_configs):
        t0 = time.time()
        results = run_matchup(evo_config, default_config, args.games,
                              max_turns=args.max_turns)
        elapsed = time.time() - t0

        ew = results['evolved_wins']
        dw = results['default_wins']
        ti = results['ties']
        dr = results['draws']
        total = ew + dw + ti + dr
        win_rate = ew / total * 100 if total > 0 else 0

        total_evolved_wins += ew
        total_default_wins += dw
        total_ties += ti
        total_draws += dr

        print(f"  Evolved #{i+1}  |  W={ew}  L={dw}  T={ti}  D={dr}  "
              f"|  Win rate: {win_rate:.0f}%  ({elapsed:.1f}s)")
        print(f"      kill={evo_config.w_kill_enemy:.2f}  "
              f"advance={evo_config.w_advance_allied:.2f}  "
              f"protect={evo_config.w_protect_sovereign:.2f}  "
              f"danger={evo_config.w_endanger_enemy_sov:.2f}  "
              f"rnd={evo_config.w_random:.2f}  "
              f"dec={evo_config.w_deceptive:.2f}")

    # Summary
    grand_total = total_evolved_wins + total_default_wins + total_ties + total_draws
    overall_rate = total_evolved_wins / grand_total * 100 if grand_total > 0 else 0

    print()
    print("-" * 60)
    print(f"  OVERALL: Evolved {total_evolved_wins}W  "
          f"Default {total_default_wins}W  "
          f"Ties {total_ties}  Draws {total_draws}")
    print(f"  Evolved win rate: {overall_rate:.1f}%")

    if overall_rate > 60:
        print("  >> Evolved bots are STRONGER than the original!")
    elif overall_rate < 40:
        print("  >> Original bot is STRONGER than the evolved bots!")
    else:
        print("  >> Results are roughly EVEN.")
    print("=" * 60)


if __name__ == '__main__':
    main()

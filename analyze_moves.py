#!/usr/bin/env python3
"""
analyze_moves.py — Diagnostic report for bot evolution move logs.

Reads a JSONL file produced by:
    python evolution.py --move-log <path>

and prints tables that help answer questions like:
    - Why are 1-ply bots still winning games against deeper bots?
    - Do deeper bots pass more? Make fewer attacks?
    - Do 1-ply bots win faster (shorter games)?

Usage
-----
    python analyze_moves.py evo_moves.jsonl
    python analyze_moves.py evo_moves.jsonl --ply 1 2
    python analyze_moves.py evo_moves.jsonl --summary evo_moves.jsonl.summary.jsonl

No pygame or game-engine imports required — pure stdlib only.
"""

import argparse
import json
import sys
from collections import defaultdict


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_moves(path, ply_filter=None):
    """Load all move records from a JSONL file.

    Parameters
    ----------
    path       : str  — path to the .jsonl file
    ply_filter : list[int] | None  — if set, keep only records whose
                 ply_depth is in this list

    Returns list of dicts.
    """
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: skipping malformed line: {e}", file=sys.stderr)
                continue
            if ply_filter and obj.get('ply_depth') not in ply_filter:
                continue
            records.append(obj)
    return records


def load_summaries(path):
    """Load game summary records from a .summary.jsonl file."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

ACTION_TYPES = ['attack', 'move', 'recruit', 'promote', 'promote_knight',
                'diplomacy', 'pass']

def _pct(n, total):
    return 100 * n / total if total else 0.0


def by_ply(records):
    """Group records by ply_depth."""
    groups = defaultdict(list)
    for r in records:
        groups[r.get('ply_depth', '?')].append(r)
    return dict(sorted(groups.items()))


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def print_header(path, n_records):
    print()
    print("=" * 70)
    print("  SIX NATIONS — BOT MOVE ANALYSIS")
    print("=" * 70)
    print(f"  Source : {path}")
    print(f"  Records: {n_records:,}")
    print()


def report_win_rate(summaries):
    """Win rate broken down by winner ply depth."""
    print("── WIN RATE BY PLY DEPTH " + "─" * 44)
    if not summaries:
        print("  (no summary data — re-run with --summary flag)")
        print()
        return

    # Count games and wins per ply matchup
    # A game contributes to winner_ply wins; both bots contribute to game counts
    ply_games  = defaultdict(int)   # total games this ply was involved in
    ply_wins   = defaultdict(int)   # games this ply won
    ply_as_bot1 = defaultdict(int)
    ply_as_bot2 = defaultdict(int)
    from collections import Counter
    result_counter = Counter(s.get('result') for s in summaries)

    for s in summaries:
        b1 = s.get('bot1_ply')
        b2 = s.get('bot2_ply')
        wp = s.get('winner_ply')
        res = s.get('result', '')
        if b1 is not None:
            ply_games[b1] += 1
            ply_as_bot1[b1] += 1
        if b2 is not None:
            ply_games[b2] += 1
            ply_as_bot2[b2] += 1
        if wp is not None:
            ply_wins[wp] += 1

    all_plies = sorted(set(list(ply_games.keys())))
    total_games = len(summaries)
    print(f"  Total games: {total_games}  |  "
          + "  ".join(f"{k}: {v}" for k, v in sorted(result_counter.items())))
    print()
    print(f"  {'Ply':>4}  {'Games':>7}  {'Wins':>6}  {'Win%':>6}  {'As Bot1':>8}  {'As Bot2':>8}")
    print("  " + "-" * 48)
    for ply in all_plies:
        games = ply_games[ply]
        wins  = ply_wins.get(ply, 0)
        print(f"  {ply:>4}  {games:>7}  {wins:>6}  {_pct(wins, games):>5.1f}%"
              f"  {ply_as_bot1.get(ply, 0):>8}  {ply_as_bot2.get(ply, 0):>8}")
    print()


def report_action_distribution(records):
    """Action type distribution broken down by ply depth."""
    print("── ACTION TYPE DISTRIBUTION BY PLY DEPTH " + "─" * 28)
    groups = by_ply(records)
    if not groups:
        print("  (no records)")
        print()
        return

    # Header
    cols = ACTION_TYPES
    col_w = 11
    header = f"  {'Ply':>4}  {'Total':>7}  " + "  ".join(f"{c:>{col_w}}" for c in cols)
    print(header)
    print("  " + "-" * len(header.lstrip()))

    for ply, recs in groups.items():
        total = len(recs)
        type_counts = Counter(r.get('action_type', 'unknown') for r in recs)
        row = f"  {ply:>4}  {total:>7}  "
        row += "  ".join(
            f"{_pct(type_counts.get(c, 0), total):>{col_w}.0f}%"
            for c in cols
        )
        print(row)
    print()
    print("  (Values are % of all moves for that ply depth)")
    print()


def report_avg_score(records):
    """Average chosen action score by ply depth (non-pass moves only)."""
    print("── AVERAGE ACTION SCORE BY PLY DEPTH (non-pass) " + "─" * 20)
    groups = by_ply(records)
    print(f"  {'Ply':>4}  {'Moves':>7}  {'Avg Score':>10}  {'Max Score':>10}  {'Min Score':>10}")
    print("  " + "-" * 50)
    for ply, recs in groups.items():
        scored = [r['score'] for r in recs if r.get('action_type') != 'pass']
        if not scored:
            print(f"  {ply:>4}  {'—':>7}")
            continue
        avg = sum(scored) / len(scored)
        print(f"  {ply:>4}  {len(scored):>7}  {avg:>10.1f}  {max(scored):>10.1f}  {min(scored):>10.1f}")
    print()


def report_path_distribution(records):
    """intent vs random vs deceptive breakdown by ply depth."""
    print("── MOVE PATH (INTENT / RANDOM / DECEPTIVE) BY PLY " + "─" * 18)
    groups = by_ply(records)
    paths = ['intent', 'random', 'deceptive']
    print(f"  {'Ply':>4}  {'Total':>7}  " + "  ".join(f"{p:>10}" for p in paths))
    print("  " + "-" * 44)
    for ply, recs in groups.items():
        total = len(recs)
        pc = Counter(r.get('path', 'intent') for r in recs)
        row = f"  {ply:>4}  {total:>7}  "
        row += "  ".join(f"{_pct(pc.get(p, 0), total):>9.0f}%" for p in paths)
        print(row)
    print()


def report_game_length(summaries):
    """Game length distribution by winner ply."""
    print("── GAME LENGTH BY WINNER PLY " + "─" * 40)
    if not summaries:
        print("  (no summary data)")
        print()
        return

    by_winner = defaultdict(list)
    for s in summaries:
        wp = s.get('winner_ply')
        turns = s.get('turns')
        if turns is not None:
            key = str(wp) if wp is not None else 'tie/draw'
            by_winner[key].append(turns)

    print(f"  {'Winner Ply':>12}  {'Games':>6}  {'Avg Turns':>10}  {'Min':>5}  {'Max':>5}")
    print("  " + "-" * 44)
    for wp in sorted(by_winner.keys()):
        turns = by_winner[wp]
        avg = sum(turns) / len(turns)
        print(f"  {wp:>12}  {len(turns):>6}  {avg:>10.1f}  {min(turns):>5}  {max(turns):>5}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

try:
    from collections import Counter
except ImportError:
    pass  # already imported above


def main():
    parser = argparse.ArgumentParser(
        description='Analyze bot move logs from Six Nations evolution runs.')
    parser.add_argument('moves_file',
                        help='JSONL move log file produced by --move-log')
    parser.add_argument('--summary', metavar='PATH', default=None,
                        help='Path to .summary.jsonl file (auto-detected if omitted)')
    parser.add_argument('--ply', type=int, nargs='+', default=None, metavar='N',
                        help='Filter analysis to specific ply depths (e.g. --ply 1 2)')
    args = parser.parse_args()

    # Auto-detect summary file
    summary_path = args.summary
    if summary_path is None:
        auto = args.moves_file + '.summary.jsonl'
        import os
        if os.path.exists(auto):
            summary_path = auto

    print(f"Loading move records from {args.moves_file} ...", file=sys.stderr)
    records = load_moves(args.moves_file, ply_filter=args.ply)
    summaries = load_summaries(summary_path) if summary_path else []

    if args.ply:
        # Also filter summaries so win-rate tables match
        summaries = [s for s in summaries
                     if s.get('bot1_ply') in args.ply
                     or s.get('bot2_ply') in args.ply]

    print_header(args.moves_file, len(records))

    if args.ply:
        print(f"  Filter: ply depth in {args.ply}\n")

    report_win_rate(summaries)
    report_action_distribution(records)
    report_avg_score(records)
    report_path_distribution(records)
    report_game_length(summaries)

    print("=" * 70)
    print()


if __name__ == '__main__':
    main()

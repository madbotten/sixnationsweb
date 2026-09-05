"""
Settings and configuration constants for Six Nations.
"""
import math

# -- Window -------------------------------------------------------------------
SCREEN_WIDTH  = 2000
SCREEN_HEIGHT = 1380
WINDOW_TITLE  = "Six Nations"
FPS           = 60

# -- Hex grid (flat-topped hexagons) ------------------------------------------
# HEX_WIDTH  = vertex-to-vertex horizontal distance.
# HEX_HEIGHT = vertex-to-vertex vertical distance.
# Proper flat-top ratio: HEX_HEIGHT = HEX_WIDTH * sqrt(3) / 2
HEX_WIDTH  = 180
HEX_HEIGHT = int(HEX_WIDTH * math.sqrt(3) / 2)   # ~156 px  (90% of original 200/173)

# Fixed center of the map on screen (no scroll or zoom).
MAP_CENTER_X = 1000
MAP_CENTER_Y = 715

# -- UI regions ---------------------------------------------------------------
TOP_BAR_HEIGHT  = 60   # Top status bar height
COOLDOWN_PANEL_W = 300
COOLDOWN_PANEL_H = 150

# -- Diplomacy panel ----------------------------------------------------------
DIPL_PANEL_X        = 1640
DIPL_PANEL_Y        = 70
DIPL_PANEL_W        = 340
DIPL_BOX_H          = 200
DIPL_BOX_GAP        = 20
DIPL_FLAG_W         = 40
DIPL_FLAG_H         = 34
DIPL_FLAG_GAP       = 12
DIPL_COOLDOWN_MIN   = 10    # random cooldown range (counts ALL turns: human + bot)
DIPL_COOLDOWN_MAX   = 12    # actual value chosen secretly; red border visible, count hidden

# -- Recruitment Cooldown -----------------------------------------------------
# A nation can only recruit one army per every 10 turns (each player move is a turn).
RECRUIT_COOLDOWN_TURNS = 10


# -- Nation colours (by name) -------------------------------------------------
# Insertion order is canonical nation order throughout the game.
NATION_COLORS = {
    'Yilerond':  (230, 200,  50),   # Yellow
    'Galland':   ( 55, 190,  80),   # Green
    'Beldrin':   ( 70, 185, 230),   # Sky Blue
    'Crestmoor': ( 55,  85, 200),   # Cobalt
    'Malkor':    (210,  55, 170),   # Magenta
    'Ravengard': (210,  45,  65),   # Crimson
}

# Canonical name list, preserving insertion order (Python 3.7+).
NATION_NAMES = list(NATION_COLORS.keys())

# Dark tinted fills for starting hex interiors (18% blend over dark bg).
NATION_HEX_FILLS = {
    name: tuple(int(18 + c * 0.20) for c in col)
    for name, col in NATION_COLORS.items()
}

# -- Background and UI colours ------------------------------------------------
COLOR_BACKGROUND   = (11, 14, 22)
COLOR_HEX_NEUTRAL  = (20, 26, 38)
COLOR_HEX_BORDER   = (36, 44, 60)
COLOR_TEXT_PRIMARY = (235, 240, 250)
COLOR_TEXT_MUTED   = (128, 138, 162)
COLOR_TOP_BAR      = (  8,  10,  18)
COLOR_PANEL        = ( 13,  17,  27)
COLOR_PANEL_BORDER = ( 34,  41,  58)

# -- Bot behaviour ------------------------------------------------------------
# After this turn number the bot begins using opponent goal inference:
#   • Deduces opponent's 3 prevail and 3 defeat picks from movement patterns
#   • Simulates opponent's goal-driven counter-moves in lookahead search
#   • Unlocks counter-diplomacy heuristics against opponent targets
BOT_ADAPTIVE_TURN = 4

# Fraction of moves that are RANDOM at the very start of the game (turn 1).
# By turn 50 the bot will always be ~10% random regardless of this setting.
# Range: 0.0 (pure intent from turn 1) to 1.0 (always random).
BOT_INITIAL_RANDOM = 0.60   # 60% random at start → 40% intent

# -- Deployment mode ----------------------------------------------------------
# 'DEBUG'  : show developer overlays (bot faction guess, etc.)
# 'EXPORT' : clean release build — no debug overlays shown
DEPLOYMENT = 'EXPORT'

# -- Evolution chamber --------------------------------------------------------
# Default parameters for evolution.py (overridable via CLI flags).
EVO_POPULATION       = 24     # bots per generation
EVO_GENERATIONS      = 50     # number of generations to evolve
EVO_GAMES_PER_PAIR   = 1      # games per matchup in round-robin
EVO_MAX_TURNS        = 200    # turn limit per headless game
EVO_ELITE_COUNT      = 4      # top N configs carried forward unchanged
EVO_MUTATION_RATE    = 0.15   # probability of mutating each gene
EVO_MUTATION_RESET   = 0.05   # probability of full-random reset (vs gaussian)
EVO_TOP_N_PERSIST    = 4      # number of top configs saved to bot_configs.json

# -- Bot lookahead ------------------------------------------------------------
# Multi-ply search depth. 1 = current behaviour (score one move).
# 2+ = look ahead N plies (my move, opponent response, my response, ...).
BOT_LOOKAHEAD_DEPTH  = 1      # default plies (1 = no lookahead)
BOT_LOOKAHEAD_BEAM   = 3      # top-K candidates to evaluate at each deeper ply
BOT_LOOKAHEAD_MODE   = 'action'  # 'action' (score subtraction) or 'position' (board eval)

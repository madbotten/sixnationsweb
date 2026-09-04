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
DIPLO_RING_SIZE = 300  # Square side for DiplomacyRing.jpg panel (top-right)
COOLDOWN_PANEL_W = 300
COOLDOWN_PANEL_H = 150

# -- Nation colours (ring order 0-5) ------------------------------------------
# Yellow, Green, Sky Blue, Cobalt, Magenta, Crimson
NATION_COLORS = [
    (230, 200,  50),   # 0  Yellow
    ( 55, 190,  80),   # 1  Green
    ( 70, 185, 230),   # 2  Sky Blue
    ( 55,  85, 200),   # 3  Cobalt
    (210,  55, 170),   # 4  Magenta
    (210,  45,  65),   # 5  Crimson
]

NATION_NAMES = [
    "Yilerond",  # Yellow
    "Galland",   # Green
    "Beldrin",   # Blue
    "Crestmoor", # Cobalt
    "Malkor",    # Magenta
    "Ravengard"  # Red
]

# Dark tinted fills for starting hex interiors (18% blend over dark bg).
NATION_HEX_FILLS = [
    tuple(int(18 + c * 0.20) for c in col)
    for col in NATION_COLORS
]

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
# After this turn number the bot begins using suspected-player-faction intel:
#   • Prioritise attacks on the suspected human sovereign
#   • Avoid attacks on sovereigns that only benefit the human player
BOT_ADAPTIVE_TURN = 25

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
EVO_GAMES_PER_PAIR   = 2      # games per matchup in round-robin
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

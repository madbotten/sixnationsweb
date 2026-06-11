"""
Settings and configuration constants for the Alignments game.
Contains display window dimensions, frame rate controls, and visual theme colors.
"""

# Window settings
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 1000
WINDOW_TITLE = "Alignments"
FPS = 60

# Game Phase Enumerations
PHASE_MAP_BUILDING = 0
PHASE_MAIN_GAME = 1

# Faction Turn Phase Enumerations
TURN_PHASE_INCOME = 0
TURN_PHASE_MOVE = 1
TURN_PHASE_COMBAT = 2
TURN_PHASE_CONTROL = 3
TURN_PHASE_VICTORY = 4

# Hex Grid Layout Constants
HEX_WIDTH = 293           # Width of the squashed hex artwork on screen (33% larger)
HEX_HEIGHT = 160          # Height of the squashed hex artwork on screen (33% larger)
PANEL_WIDTH = 400         # Width of the left side panel (25% of 1600)
SCROLL_SPEED = 500        # Camera scroll speed in pixels per second

# Tile Pool Specifications
# The 17 unique tiles (only one copy of each exists in the entire game)
UNIQUE_TILES = [
    "Elmany", "FungalJungle", "GoldenCanyon", "Limbo", "PitofDespair",
    "Tanelorn", "TempleofEvil", "TheDark", "Tileronde",
    "TowerofJustice", "SunkenCanopy", "PetrifiedForest", "StormTundra"
]

# The 10 common tiles (can be duplicated at random to pad decks to 16)
COMMON_TILES = [
    "Woods", "Swamp", "Mountains", "Plains", "Desert", "Hills", "Coastal", "Subterranean", "Barrens", "Jungle"
]

# Total hand capacity per player
TOTAL_TILES_PER_PLAYER = 16

# Premium Sci-Fi Visual Theme Colors (RGB format)
COLOR_BACKGROUND = (11, 14, 20)      # Sleek deep space charcoal-navy
COLOR_HUD_BG = (20, 24, 33, 180)     # Glassmorphic HUD overlay (with alpha)
COLOR_TEXT_PRIMARY = (235, 240, 250) # Crisp near-white
COLOR_TEXT_MUTED = (140, 150, 170)   # Clean futuristic gray

# Neon Energy Visual States (for grid connections and interactions)
COLOR_NEON_CYAN = (0, 243, 255)      # Active energy beams / aligned state
COLOR_NEON_PURPLE = (189, 0, 255)    # Core reactor power/charging
COLOR_NEON_PINK = (255, 0, 127)      # Unaligned node warning / pulse indicator
COLOR_NEON_GREEN = (50, 255, 120)    # Fully stabilized system state

"""
Settings and configuration constants for Six Nations.
"""
import math

# -- Window -------------------------------------------------------------------
SCREEN_WIDTH  = 2000
SCREEN_HEIGHT = 1400
WINDOW_TITLE  = "Six Nations"
FPS           = 60

# -- Hex grid (flat-topped hexagons) ------------------------------------------
# HEX_WIDTH  = vertex-to-vertex horizontal distance.
# HEX_HEIGHT = vertex-to-vertex vertical distance.
# Proper flat-top ratio: HEX_HEIGHT = HEX_WIDTH * sqrt(3) / 2
HEX_WIDTH  = 200
HEX_HEIGHT = int(HEX_WIDTH * math.sqrt(3) / 2)   # ~173 px

# Fixed center of the map on screen (no scroll or zoom).
MAP_CENTER_X = 1000
MAP_CENTER_Y = 735

# -- UI regions ---------------------------------------------------------------
TOP_BAR_HEIGHT  = 70   # Top status bar height
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

NATION_NAMES = ["Yellow", "Green", "Sky Blue", "Cobalt", "Magenta", "Crimson"]

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

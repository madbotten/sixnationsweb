"""
Units -- Six Nations

All four unit types in one place:

  Army     — occupies a single hex; cap starts at 3, grows +1 per 3 extra
              hexes of territory beyond the starting 4.
  Knight   — promoted army; counts toward the army cap; max 1 per nation.
  Champion — 1 per nation; provides support and can attack independently.
  Sovereign — 1 per nation; the win-condition piece.

No two Army/Knight units may ever occupy the same hex.
Champions and Sovereigns may share a hex with armies/knights of their own nation.
"""


class Army:
    def __init__(self, nation, q: int, r: int):
        self.nation = nation   # factions.Nation
        self.q      = q
        self.r      = r

    @property
    def hex_location(self):
        return (self.q, self.r)

    @hex_location.setter
    def hex_location(self, loc):
        self.q, self.r = loc

    def __repr__(self):
        return f"Army({self.nation.color_name}, ({self.q},{self.r}))"


class Knight:
    """Promoted army. Counts toward army cap. Max 1 per nation."""
    def __init__(self, nation, q: int, r: int):
        self.nation = nation   # factions.Nation
        self.q      = q
        self.r      = r

    @property
    def hex_location(self):
        return (self.q, self.r)

    @hex_location.setter
    def hex_location(self, loc):
        self.q, self.r = loc

    def __repr__(self):
        return f"Knight({self.nation.color_name}, ({self.q},{self.r}))"


class Champion:
    """1 per nation. Provides support; can attack without an army."""
    def __init__(self, nation, q: int, r: int):
        self.nation = nation   # factions.Nation
        self.q      = q
        self.r      = r

    @property
    def hex_location(self):
        return (self.q, self.r)

    @hex_location.setter
    def hex_location(self, loc):
        self.q, self.r = loc

    def __repr__(self):
        return f"Champion({self.nation.color_name}, ({self.q},{self.r}))"


class Sovereign:
    """1 per nation. The win-condition piece — losing it ends the nation."""
    def __init__(self, nation, q: int, r: int):
        self.nation = nation   # factions.Nation
        self.q      = q
        self.r      = r

    @property
    def hex_location(self):
        return (self.q, self.r)

    @hex_location.setter
    def hex_location(self, loc):
        self.q, self.r = loc

    def __repr__(self):
        return f"Sovereign({self.nation.color_name}, ({self.q},{self.r}))"

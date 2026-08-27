"""
Champion and Sovereign units -- Six Nations
Each nation has at most 1 Champion and 1 Sovereign.
"""


class Champion:
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

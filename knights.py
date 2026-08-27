"""
Knight unit -- Six Nations
Each nation may have at most 1 Knight (promoted from an army on home territory).
Counts toward the nation's army capacity.
"""


class Knight:
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

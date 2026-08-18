"""
Nation System -- Six Nations
Six nations arranged in a diplomatic ring (indices 0-5).
Adjacent nations on the ring are allies; all others are enemies.
"""
import settings


class Nation:
    """Represents one of the six nations on the diplomatic ring."""

    def __init__(self, ring_index: int):
        self.ring_index  = ring_index
        self.color_rgb   = settings.NATION_COLORS[ring_index]
        self.color_light = settings.NATION_HEX_FILLS[ring_index]
        self.color_name  = settings.NATION_NAMES[ring_index]
        self.is_ghost    = False   # True when this nation's sovereign is destroyed

    def is_ally(self, other: "Nation") -> bool:
        """True when the two nations are immediate neighbours on the ring."""
        diff = abs(self.ring_index - other.ring_index)
        return diff == 1 or diff == 5

    def is_enemy(self, other: "Nation") -> bool:
        """True when the two nations are neither the same nor allies."""
        if self.ring_index == other.ring_index:
            return False
        return not self.is_ally(other)

    def enemy_nations(self, all_nations: "list[Nation]") -> "list[Nation]":
        """Return the 3 enemy nations (opposite side of the ring)."""
        return [n for n in all_nations if self.is_enemy(n)]

    def __repr__(self) -> str:
        return f"Nation({self.color_name})"


# The six predefined nation singletons, shared across the whole game.
NATIONS: list = [Nation(i) for i in range(6)]

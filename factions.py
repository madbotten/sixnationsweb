"""
Faction System - Alignments
Defines the Faction class and predefined Factions in the diplomatic ring.
"""

class Faction:
    def __init__(self, ring_number, race, home_terrain):
        """
        Initializes a Faction instance.
        
        Args:
            ring_number (int): The position on the diplomatic ring (0-9).
            race (str): The race of the faction (e.g. 'Humans').
            home_terrain (str): The home terrain type (e.g. 'Plains').
        """
        self.ring_number = ring_number
        self.race = race
        self.home_terrain = home_terrain
        self._gold = 1

    @property
    def gold(self):
        """Returns the gold amount of the faction."""
        return self._gold

    @gold.setter
    def gold(self, val):
        """Sets the gold amount, validating that it is a nonnegative integer."""
        if not isinstance(val, int) or val < 0:
            raise ValueError("Gold must be a nonnegative integer.")
        self._gold = val

    def diplomatic_distance(self, faction):
        """
        Calculates the shortest diplomatic distance to another faction along the ring (0-9).
        distance(x, y) = min(|x - y|, 10 - |x - y|)
        """
        return min(abs(self.ring_number - faction.ring_number), 10 - abs(self.ring_number - faction.ring_number))

    def isFullyAligned(self, faction):
        """Returns True if the faction is fully aligned (distance = 0) with the given faction."""
        return self.diplomatic_distance(faction) == 0

    def isStronglyAligned(self, faction):
        """Returns True if the faction is strongly aligned (distance = 1) with the given faction."""
        return self.diplomatic_distance(faction) == 1

    def isLooselyAligned(self, faction):
        """Returns True if the faction is loosely aligned (distance = 2 or 3) with the given faction."""
        return self.diplomatic_distance(faction) in (2, 3)

    def isOpposed(self, faction):
        """Returns True if the faction is opposed (distance = 4 or 5) to the given faction."""
        return self.diplomatic_distance(faction) in (4, 5)

    def __repr__(self):
        return f"Faction(ring_number={self.ring_number}, race='{self.race}', home_terrain='{self.home_terrain}', gold={self._gold})"


# Predefined static list of the 10 factions from the diplomatic ring
FACTIONS = [
    Faction(0, "Humans", "Plains"),
    Faction(1, "Elves", "Woods"),
    Faction(2, "Dwarves", "Mountains"),
    Faction(3, "Giants", "Hills"),
    Faction(4, "Lizardfolk", "Jungle"),
    Faction(5, "Kuotoa", "Swamp"),
    Faction(6, "Drow", "Subterranean"),
    Faction(7, "Pirates", "Coastal"),
    Faction(8, "Barbarians", "Barrens"),
    Faction(9, "Nomads", "Desert")
]

# Quick lookup dictionary mapping ring number to Faction
FACTIONS_BY_RING = {f.ring_number: f for f in FACTIONS}

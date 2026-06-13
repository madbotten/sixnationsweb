"""
Armies System - Alignments
Defines the Army class representing game units on the hex grid.
"""

import util

class Army:
    def __init__(self, faction, q, r, strength=1, index=1):
        """
        Initializes an Army game unit.
        
        Args:
            faction (Faction): The faction object this army belongs to.
            q (int): Axial coordinate q.
            r (int): Axial coordinate r.
            strength (int): Nonnegative integer strength of the army.
            index (int): The army index on the tile.
        """
        from factions import Faction
        if not isinstance(faction, Faction):
            raise ValueError("faction must be a Faction instance")
        self._faction = faction

        self.q = q
        self.r = r

        if not isinstance(strength, int) or strength < 0:
            raise ValueError("Strength must be a nonnegative integer.")
        self._strength = strength

        self._index = index
        self.has_moved = False

    @property
    def faction(self):
        """Returns the faction of the army."""
        return self._faction

    @faction.setter
    def faction(self, val):
        """Sets the faction of the army, validating the input."""
        from factions import Faction
        if not isinstance(val, Faction):
            raise ValueError("faction must be a Faction instance")
        self._faction = val

    @property
    def strength(self):
        """Returns the strength of the army."""
        return self._strength

    @strength.setter
    def strength(self, val):
        """Sets the strength of the army, validating that it is a nonnegative integer."""
        if not isinstance(val, int) or val < 0:
            raise ValueError("Strength must be a nonnegative integer.")
        self._strength = val

    @property
    def index(self):
        """Returns the index of the army."""
        return self._index

    @index.setter
    def index(self, val):
        """Sets the index of the army."""
        self._index = val

    @property
    def hex_location(self):
        """Returns the hex location as an axial coordinate tuple (q, r)."""
        return (self.q, self.r)

    @hex_location.setter
    def hex_location(self, loc):
        """Sets the hex location using an axial coordinate tuple (q, r)."""
        self.q, self.r = loc

    @property
    def name(self):
        """Returns the specific name of the army."""
        return f"{self._faction.race} Army"

    @property
    def image_filename(self):
        """Returns the image filename for this army (e.g. 'elf.jpg')."""
        race = self._faction.race.lower()
        if race == "dwarves":
            race_singular = "dwarf"
        elif race == "elves":
            race_singular = "elf"
        elif race == "giants":
            race_singular = "giant"
        elif race == "nomads":
            race_singular = "nomad"
        elif race == "barbarians":
            race_singular = "barbarian"
        elif race == "pirates":
            race_singular = "pirate"
        elif race == "kuotoa":
            race_singular = "kuotoa"
        elif race == "humans":
            race_singular = "human"
        elif race == "lizardfolk":
            race_singular = "lizard"
        else:
            race_singular = race
        return f"{race_singular}.jpg"

    def get_surface(self, size=(100, 100), mask_type="circle"):
        """
        Loads and returns the cached, masked Pygame surface representing this army's image.
        """
        glow_color = (0, 243, 255) # Cyan
        return util.load_army_image(self._faction.race, alpha=True, color_fallback=glow_color, size=size, mask_type=mask_type)

    def __repr__(self):
        return f"Army(faction={self._faction.race}, loc=({self.q}, {self.r}), strength={self._strength}, index={self._index})"

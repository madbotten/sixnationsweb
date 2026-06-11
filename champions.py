"""
Champions System - Alignments
Defines the Champion class representing game units on the hex grid.
"""

import util

class Champion:
    def __init__(self, faction, q, r):
        """
        Initializes a Champion game unit.
        
        Args:
            faction (Faction): The faction object this champion belongs to.
            q (int): Axial coordinate q.
            r (int): Axial coordinate r.
        """
        from factions import Faction
        if not isinstance(faction, Faction):
            raise ValueError("faction must be a Faction instance")
        self._faction = faction
        self._index = 1
        self.q = q
        self.r = r

    @property
    def faction(self):
        """Returns the faction of the champion."""
        return self._faction

    @faction.setter
    def faction(self, val):
        """Sets the faction of the champion."""
        from factions import Faction
        if not isinstance(val, Faction):
            raise ValueError("faction must be a Faction instance")
        self._faction = val

    @property
    def index(self):
        """Returns the index of the champion (always 1)."""
        return 1

    @property
    def strength(self):
        """Returns the strength of the champion (always 3)."""
        return 3

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
        """Returns the specific name of the champion."""
        return f"{self._faction.race} Champion"

    @property
    def image_filename(self):
        """Returns the image filename for this champion (e.g. 'elfchampion.jpg')."""
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
        else:
            race_singular = race
        return f"{race_singular}champion.jpg"

    def get_surface(self, size=(100, 100), mask_type="circle"):
        """
        Loads and returns the cached, masked Pygame surface representing this champion's image.
        """
        # Fallback cyan color
        glow_color = (0, 243, 255)
        return util.load_champion_image(self._faction.race, alpha=True, color_fallback=glow_color, size=size, mask_type=mask_type)

    def __repr__(self):
        return f"Champion(faction={self._faction.race}, loc=({self.q}, {self.r}), strength=3)"

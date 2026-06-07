"""
Champions System - Alignments
Defines the Champion class representing game units on the hex grid.
"""

import util

class Champion:
    def __init__(self, alignment, index, q, r, strength):
        """
        Initializes a Champion game unit.
        
        Args:
            alignment (str): The single alignment part ('good', 'evil', 'lawful', 'chaotic', 'neutral').
            index (int): The champion number (1 to 4) representing which champion of that alignment this is.
            q (int): Axial coordinate q.
            r (int): Axial coordinate r.
            strength (int): Nonnegative integer strength of the champion.
        """
        alignment_lower = alignment.lower()
        if alignment_lower not in {"good", "evil", "lawful", "chaotic", "neutral"}:
            raise ValueError("Alignment must be one of: 'good', 'evil', 'lawful', 'chaotic', 'neutral'")
        self._alignment = alignment_lower

        if not isinstance(index, int) or not (1 <= index <= 4):
            raise ValueError("Champion index must be an integer between 1 and 4 inclusive.")
        self._index = index

        self.q = q
        self.r = r

        if not isinstance(strength, int) or strength < 0:
            raise ValueError("Strength must be a nonnegative integer.")
        self._strength = strength

    @property
    def alignment(self):
        """Returns the alignment of the champion."""
        return self._alignment

    @alignment.setter
    def alignment(self, val):
        """Sets the alignment of the champion, validating the input."""
        val_lower = val.lower()
        if val_lower not in {"good", "evil", "lawful", "chaotic", "neutral"}:
            raise ValueError("Alignment must be one of: 'good', 'evil', 'lawful', 'chaotic', 'neutral'")
        self._alignment = val_lower

    @property
    def index(self):
        """Returns the index of the champion (1-4)."""
        return self._index

    @index.setter
    def index(self, val):
        """Sets the index of the champion, validating that it is an integer 1-4."""
        if not isinstance(val, int) or not (1 <= val <= 4):
            raise ValueError("Champion index must be an integer between 1 and 4 inclusive.")
        self._index = val

    @property
    def strength(self):
        """Returns the strength of the champion."""
        return self._strength

    @strength.setter
    def strength(self, val):
        """Sets the strength of the champion, validating that it is a nonnegative integer."""
        if not isinstance(val, int) or val < 0:
            raise ValueError("Strength must be a nonnegative integer.")
        self._strength = val

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
        """Returns the specific name of the champion including its index."""
        base_name = {
            "good": "Good Champion",
            "evil": "Evil Champion",
            "neutral": "Neutral Champion",
            "lawful": "Champion of Law",
            "chaotic": "Champion of Chaos"
        }.get(self._alignment, self._alignment.capitalize() + " Champion")
        return f"{base_name} {self._index}"

    @property
    def image_filename(self):
        """Returns the image filename for this champion (e.g. 'Neutral3.jpg')."""
        return f"{self._alignment.capitalize()}{self._index}.jpg"

    def get_surface(self, size=(100, 100), mask_type="circle"):
        """
        Loads and returns the cached, masked Pygame surface representing this champion's image.
        """
        # Pick fallback color based on alignment
        glow_color = (189, 0, 255) # default purple
        
        if self._alignment == "good":
            glow_color = (0, 243, 255) # Cyan
        elif self._alignment == "evil":
            glow_color = (255, 0, 127) # Pink
        elif self._alignment == "neutral":
            glow_color = (50, 255, 120) # Green
        elif self._alignment == "lawful":
            glow_color = (0, 100, 255) # Blue
        elif self._alignment == "chaotic":
            glow_color = (255, 128, 0) # Orange
            
        return util.load_champion_image(self._alignment, self._index, alpha=True, color_fallback=glow_color, size=size, mask_type=mask_type)

    def __repr__(self):
        return f"Champion(alignment='{self._alignment}', index={self._index}, loc=({self.q}, {self.r}), strength={self._strength})"

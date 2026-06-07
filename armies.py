"""
Armies System - Alignments
Defines the Army class representing game units on the hex grid.
"""

import util

class Army:
    def __init__(self, alignment, q, r, strength=1, index=1, source_hex_name="Unknown", source_hex_coords=(0, 0)):
        """
        Initializes an Army game unit.
        
        Args:
            alignment (str): The single alignment part ('good', 'evil', 'lawful', 'chaotic', 'neutral').
            q (int): Axial coordinate q.
            r (int): Axial coordinate r.
            strength (int): Nonnegative integer strength of the army.
            index (int): The army number (1 to 4) representing which army of that alignment this is.
            source_hex_name (str): The name of the hex from which the army was mustered.
            source_hex_coords (tuple): The (q, r) coordinate of the source hex.
        """
        alignment_lower = alignment.lower()
        if alignment_lower not in {"good", "evil", "lawful", "chaotic", "neutral"}:
            raise ValueError("Alignment must be one of: 'good', 'evil', 'lawful', 'chaotic', 'neutral'")
        self._alignment = alignment_lower

        self.q = q
        self.r = r

        if not isinstance(strength, int) or strength < 0:
            raise ValueError("Strength must be a nonnegative integer.")
        self._strength = strength

        if not isinstance(index, int) or not (1 <= index <= 4):
            raise ValueError("Army index must be an integer between 1 and 4 inclusive.")
        self._index = index

        self.source_hex_name = source_hex_name
        self.source_hex_coords = source_hex_coords

    @property
    def alignment(self):
        """Returns the alignment of the army."""
        return self._alignment

    @alignment.setter
    def alignment(self, val):
        """Sets the alignment of the army, validating the input."""
        val_lower = val.lower()
        if val_lower not in {"good", "evil", "lawful", "chaotic", "neutral"}:
            raise ValueError("Alignment must be one of: 'good', 'evil', 'lawful', 'chaotic', 'neutral'")
        self._alignment = val_lower

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
        """Returns the index of the army (1-4)."""
        return self._index

    @index.setter
    def index(self, val):
        """Sets the index of the army, validating that it is an integer 1-4."""
        if not isinstance(val, int) or not (1 <= val <= 4):
            raise ValueError("Army index must be an integer between 1 and 4 inclusive.")
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
        base_name = {
            "good": "Good Army",
            "evil": "Evil Army",
            "neutral": "Neutral Army",
            "lawful": "Army of Law",
            "chaotic": "Army of Chaos"
        }.get(self._alignment, self._alignment.capitalize() + " Army")
        return base_name

    @property
    def image_filename(self):
        """Returns the image filename for this army (e.g. 'Neutral1.jpg')."""
        return f"{self._alignment.capitalize()}{self._index}.jpg"

    def get_surface(self, size=(100, 100), mask_type="circle"):
        """
        Loads and returns the cached, masked Pygame surface representing this army's image.
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
            
        return util.load_army_image(self._alignment, self._index, alpha=True, color_fallback=glow_color, size=size, mask_type=mask_type)

    def __repr__(self):
        return f"Army(alignment='{self._alignment}', loc=({self.q}, {self.r}), strength={self._strength}, index={self._index}, source_hex='{self.source_hex_name}')"

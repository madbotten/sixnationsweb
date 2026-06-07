"""
Powers System - Alignments
Defines the Power class representing game units on the hex grid.
"""

import util

# Predefined default alignments based on the Power name/type
DEFAULT_ALIGNMENTS = {
    "angel": ["lawful", "good"],
    "rakshasa": ["lawful", "evil"],
    "void": [],
    "dragon": ["chaotic", "neutral"],
    "demon": ["chaotic", "evil"],
    "couatl": ["chaotic", "good"],
    "shoggoth": ["neutral", "evil"],
    "kirin": ["lawful", "neutral"],
    "pegasus": ["neutral", "good"]
}

# Predefined unique abilities for each Power
UNIQUE_ABILITIES = {
    "angel": "Smite",
    "rakshasa": "Illusion",
    "void": "Annihilate",
    "dragon": "Fire Breath",
    "demon": "Hellfire",
    "couatl": "Shield",
    "shoggoth": "Madness Aura",
    "kirin": "Divine Grace",
    "pegasus": "Swift Flight"
}

class Power:
    def __init__(self, name, q, r, strength, alignment_part1=None, alignment_part2=None):
        """
        Initializes a Power game unit.
        
        Args:
            name (str): The name/type of the power (e.g., 'Angel', 'Demon', 'Void').
            q (int): Axial coordinate q.
            r (int): Axial coordinate r.
            strength (int or float): Nonnegative strength of the power.
            alignment_part1 (str, optional): First part of the alignment (e.g., 'lawful', 'chaotic').
            alignment_part2 (str, optional): Second part of the alignment (e.g., 'good', 'evil').
        """
        self.name = name
        self.q = q
        self.r = r
        
        if strength < 0:
            raise ValueError("Strength must be nonnegative.")
        self._strength = strength
        
        # Populate default alignments if not provided
        if alignment_part1 is None and alignment_part2 is None:
            defaults = DEFAULT_ALIGNMENTS.get(name.lower(), [])
            if len(defaults) == 2:
                alignment_part1, alignment_part2 = defaults
            else:
                alignment_part1, alignment_part2 = None, None
                
        # Store parts in lowercase for consistency
        self.alignment_part1 = alignment_part1.lower() if alignment_part1 else None
        self.alignment_part2 = alignment_part2.lower() if alignment_part2 else None
        
        # Initialize abilities
        self.unique_ability = UNIQUE_ABILITIES.get(name.lower(), "Special")
        self.shared_abilities = ["Move"]
        if name.lower() != "void":
            self.shared_abilities.append("Summon Champion")

    @property
    def abilities(self):
        """Returns a list of abilities available to this Power (shared + unique)."""
        return self.shared_abilities + [self.unique_ability]


    @property
    def hex_location(self):
        """Returns the hex location as an axial coordinate tuple (q, r)."""
        return (self.q, self.r)

    @hex_location.setter
    def hex_location(self, loc):
        """Sets the hex location using an axial coordinate tuple (q, r)."""
        self.q, self.r = loc

    @property
    def strength(self):
        """Returns the strength of the power unit (always nonnegative)."""
        return self._strength

    @strength.setter
    def strength(self, val):
        """Sets the strength of the power unit, validating that it is nonnegative."""
        if val < 0:
            raise ValueError("Strength must be nonnegative.")
        self._strength = val

    def get_alignment_parts(self):
        """
        Returns the two parts of the alignment as a list of strings.
        If the Power has no alignment parts (e.g., 'Void'), returns an empty list.
        """
        if self.alignment_part1 is None or self.alignment_part2 is None:
            return []
        return [self.alignment_part1, self.alignment_part2]

    def is_aligned(self, part):
        """
        Returns True if the Power has the specified alignment part (case-insensitive).
        If one of the Power's alignment parts is 'neutral', it acts as a wildcard
        for that axis (matching both parts of that axis).
        Any non-neutral part matches itself and 'neutral'.
        """
        part_lower = part.lower()
        parts = self.get_alignment_parts()
        if not parts:
            return False
            
        p_order, p_moral = parts[0], parts[1]
        
        order_matches = set()
        if p_order == "neutral":
            order_matches = {"neutral", "lawful", "chaotic"}
        else:
            order_matches = {p_order, "neutral"}
            
        moral_matches = set()
        if p_moral == "neutral":
            moral_matches = {"neutral", "good", "evil"}
        else:
            moral_matches = {p_moral, "neutral"}
            
        allowed = order_matches.union(moral_matches)
        return part_lower in allowed


    def get_surface(self, size=(100, 100), mask_type="circle"):
        """
        Loads and returns the cached, masked Pygame surface representing this power's image.
        """
        # Pick fallback color based on alignment parts (moral/order axis)
        # Defaults to hot purple if unknown
        glow_color = (189, 0, 255)
        
        parts = self.get_alignment_parts()
        if parts:
            moral = parts[1] # e.g. "good", "evil", "neutral"
            if "good" in moral:
                glow_color = (0, 243, 255) # Cyan
            elif "evil" in moral:
                glow_color = (255, 0, 127) # Pink
            elif "neutral" in moral:
                glow_color = (50, 255, 120) # Green
            
        return util.load_power_image(self.name, alpha=True, color_fallback=glow_color, size=size, mask_type=mask_type)

    def __repr__(self):
        return f"Power(name='{self.name}', loc=({self.q}, {self.r}), strength={self._strength}, alignment={self.get_alignment_parts()})"

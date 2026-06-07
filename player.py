"""
Player System - Alignments
Defines the Player class representing game players with alignment attributes.
"""

import random

POSSIBLE_ALIGNMENTS = [
    ["lawful", "good"],
    ["lawful", "evil"],
    ["chaotic", "neutral"],
    ["chaotic", "evil"],
    ["chaotic", "good"],
    ["neutral", "evil"],
    ["lawful", "neutral"],
    ["neutral", "good"]
]

class Player:
    def __init__(self, alignment_part1=None, alignment_part2=None):
        """
        Initializes a Player. If no alignment parts are provided,
        selects a random alignment pair from POSSIBLE_ALIGNMENTS.
        """
        if alignment_part1 is None or alignment_part2 is None:
            chosen = random.choice(POSSIBLE_ALIGNMENTS)
            self.alignment_part1 = chosen[0]
            self.alignment_part2 = chosen[1]
        else:
            self.alignment_part1 = alignment_part1.lower()
            self.alignment_part2 = alignment_part2.lower()

    def get_alignment_parts(self):
        """
        Returns the two parts of the player's alignment as a list of strings.
        """
        return [self.alignment_part1, self.alignment_part2]

    def can_control_power(self, power):
        """
        Determines if the player can control the given power based on alignment rules:
        - Void is always controllable.
        - If the player has a neutral alignment part (either order or moral), they can control
          any Power except those that have the opposite alignment of their other quality.
        - Otherwise (both parts non-neutral), they can control any Power that shares at least one
          alignment part (order or moral) with them, plus Void.
        """
        # Void is a special case and is always controllable
        if power.name.lower() == "void":
            return True
            
        u_align = power.get_alignment_parts()
        if not u_align:
            return True
            
        p_align = self.get_alignment_parts()
        p_order, p_moral = p_align[0], p_align[1]
        
        opposite = {
            "lawful": "chaotic",
            "chaotic": "lawful",
            "good": "evil",
            "evil": "good",
            "neutral": "neutral"
        }
        
        is_order_neutral = (p_order == "neutral")
        is_moral_neutral = (p_moral == "neutral")
        
        if is_order_neutral and is_moral_neutral:
            # True Neutral controls everything
            return True
            
        if is_order_neutral:
            # Player is e.g. neutral evil. Other quality is moral (evil).
            # Opp_moral is opposite of evil (good).
            # Power cannot have that opposite alignment part.
            opp_moral = opposite.get(p_moral)
            return opp_moral not in u_align
            
        if is_moral_neutral:
            # Player is e.g. lawful neutral. Other quality is order (lawful).
            # Opp_order is opposite of lawful (chaotic).
            # Power cannot have that opposite alignment part.
            opp_order = opposite.get(p_order)
            return opp_order not in u_align
            
        # No neutral parts (CE, LE, CG, LG)
        if p_order == "lawful" and p_moral == "good":
            # Lawful Good can control anything sharing at least one part, except chaotic
            return any(part in u_align for part in p_align) and "chaotic" not in u_align
            
        return any(part in u_align for part in p_align)

    def __repr__(self):
        return f"Player(alignment={self.get_alignment_parts()})"

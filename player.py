"""
Player System - Alignments
Defines the Player class representing game players with alignment attributes.
"""

import random

class Player:
    def __init__(self, faction=None):
        """
        Initializes a Player. If no faction is provided, selects a random Faction.
        """
        if faction is None:
            from factions import FACTIONS
            self.faction = random.choice(FACTIONS)
        else:
            self.faction = faction

    def choose_next_faction(self, previous_faction=None):
        """
        Determines the next Faction to control.
        Has a 50% chance to pick a random Fully or Strongly Aligned Faction (relative to self.faction),
        and a 50% chance to pick a random Loosely Aligned Faction.
        Excludes previous_faction if provided.
        """
        from factions import FACTIONS
        
        group_a = []
        group_b = []
        
        for f in FACTIONS:
            # Exclude the previously moved faction
            if previous_faction is not None and f.ring_number == previous_faction.ring_number:
                continue
            
            # Group by alignment relation to player's secret faction
            if self.faction.isFullyAligned(f) or self.faction.isStronglyAligned(f):
                group_a.append(f)
            elif self.faction.isLooselyAligned(f):
                group_b.append(f)
                
        # 50% chance for Group A, 50% chance for Group B
        if not group_a:
            chosen_group = group_b
        elif not group_b:
            chosen_group = group_a
        else:
            chosen_group = group_a if random.random() < 0.5 else group_b
            
        return random.choice(chosen_group)

    def __repr__(self):
        return f"Player(faction={self.faction})"

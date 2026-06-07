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

    def __repr__(self):
        return f"Player(alignment={self.get_alignment_parts()})"

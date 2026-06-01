"""
Bot Player Controller - Alignments
Handles decision making and hand operations for the automated bot player.
"""

import random

class BotPlayer:
    def __init__(self, hand=None):
        # A list of tile strings in the bot's hand (exactly 12)
        self.hand = list(hand) if hand else []

    def choose_placement(self, map_grid):
        """
        Analyses the map grid and makes a valid placement selection.
        Returns a tuple: (q, r, terrain_type) or None if no placement is possible.
        Removes the chosen tile from the bot's hand.
        """
        if not self.hand:
            print("[Bot Warning] Bot hand is empty!")
            return None
            
        # Create a shuffled list of hand tiles to try
        try_hand = list(self.hand)
        random.shuffle(try_hand)
        
        # Prioritise unique tiles to maintain smart strategic play
        # False (Uniques) comes first when sorting by standard boolean ascending
        try_hand.sort(key=lambda t: t in ["Woods", "Swamp", "Mountains", "Plains", "Desert"])
        
        for chosen_terrain in try_hand:
            # Retrieve empty adjacent positions that satisfy placement restrictions for this tile
            valid_spots = map_grid.get_valid_placements(chosen_terrain)
            if valid_spots:
                # Cluster spots closest to origin to maintain organic maps
                valid_spots.sort(key=lambda coord: abs(coord[0]) + abs(coord[1]))
                
                options = valid_spots[:min(3, len(valid_spots))]
                chosen_coord = random.choice(options)
                
                # Commit hand removal
                self.hand.remove(chosen_terrain)
                return chosen_coord[0], chosen_coord[1], chosen_terrain

        # If no valid moves are possible with any tile in hand
        print("[Bot Warning] No valid moves available for any tile in bot hand!")
        return None

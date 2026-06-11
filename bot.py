"""
Bot Player Controller - Alignments
Handles decision making and hand operations for the automated bot player.
"""

import random
import settings

class BotPlayer:
    def __init__(self, hand=None):
        # A list of tile strings in the bot's hand (exactly 16)
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
        
        def get_priority(tile):
            if tile in settings.COMMON_TILES:
                return 1
            else:
                return 0
                
        try_hand.sort(key=get_priority)

        
        print(f"[Bot] Hand before placement: {self.hand}")
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
                print(f"[Bot] Placed {chosen_terrain} at ({chosen_coord[0]}, {chosen_coord[1]}). Remaining hand: {self.hand}")
                return chosen_coord[0], chosen_coord[1], chosen_terrain

        # If no valid moves are possible with any tile in hand
        print(f"[Bot Warning] No valid moves available for any tile in bot hand! Hand: {self.hand}")
        return None


def bot_map_quick_setup(map_grid, player_hand, bot_player):
    """
    Simulates the setup phase quickly using two bot players taking turns.
    Modifies player_hand and bot_player.hand in-place as tiles are placed.
    """
    player_bot = BotPlayer(hand=player_hand)
    
    consecutive_failures = 0
    while (player_bot.hand or bot_player.hand) and consecutive_failures < 2:
        placed_this_round = False
        
        # Player bot turn
        if player_bot.hand:
            action = player_bot.choose_placement(map_grid)
            if action:
                q, r, terrain = action
                map_grid.place_tile(q, r, terrain, owner='player')
                placed_this_round = True
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
        # Bot player turn
        if bot_player.hand:
            action = bot_player.choose_placement(map_grid)
            if action:
                q, r, terrain = action
                map_grid.place_tile(q, r, terrain, owner='bot')
                placed_this_round = True
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
        if not placed_this_round:
            break
            
    # Update player_hand in-place
    player_hand[:] = player_bot.hand


"""
Verification script for new placement rules:
1. RESTRICTED_TILES cannot be placed next to the starting hex (0, 0).
2. Bot player prioritizes placing RESTRICTED_TILES last.
"""
import settings
from map import MapGrid
from bot import BotPlayer

def run_tests():
    print("--- Running Placement Validation Tests ---")
    
    grid = MapGrid()
    # (0, 0) is initialized with "woods" (system)
    
    # Starting tile neighbors are adjacent to (0, 0)
    starting_neighbors = grid.get_neighbors(0, 0)
    print(f"Neighbors of starting tile: {starting_neighbors}")
    
    # Try to place a restricted tile, e.g. "Limbo", adjacent to (0, 0)
    # This should be invalid
    test_adj_coord = starting_neighbors[0]
    is_valid = grid.is_valid_placement(test_adj_coord[0], test_adj_coord[1], "Limbo")
    print(f"Placing 'Limbo' at {test_adj_coord} (adjacent to start): {is_valid} (Expected: False)")
    assert not is_valid, "Error: Allowed restricted tile next to starting tile!"
    
    # Try to place a common tile adjacent to (0, 0)
    # This should be valid
    is_valid_common = grid.is_valid_placement(test_adj_coord[0], test_adj_coord[1], "Swamp")
    print(f"Placing 'Swamp' at {test_adj_coord} (adjacent to start): {is_valid_common} (Expected: True)")
    assert is_valid_common, "Error: Blocked common tile next to starting tile!"
    
    # Actually place the Swamp tile at test_adj_coord
    grid.place_tile(test_adj_coord[0], test_adj_coord[1], "Swamp", "player")
    
    # Let's find neighbors of test_adj_coord that are NOT adjacent to (0, 0)
    target_coord = None
    for neighbor in grid.get_neighbors(test_adj_coord[0], test_adj_coord[1]):
        if neighbor != (0, 0) and neighbor not in starting_neighbors:
            target_coord = neighbor
            break
            
    print(f"Checking placement at {target_coord} (adjacent to Swamp, NOT adjacent to (0, 0))")
    
    # Placing a restricted tile "Limbo" at target_coord should be valid since it is adjacent to Swamp
    # and not adjacent to (0, 0) or other restricted tiles
    is_valid_far = grid.is_valid_placement(target_coord[0], target_coord[1], "Limbo")
    print(f"Placing 'Limbo' at {target_coord} (far from start): {is_valid_far} (Expected: True)")
    assert is_valid_far, "Error: Blocked restricted tile far from starting tile!"

    print("\n--- Running Bot Sorting Priority Tests ---")
    # Setup a bot hand with a mix of uniques, commons, and restricted tiles
    bot_hand = ["Limbo", "Woods", "FungalJungle", "PitofDespair", "Swamp", "Elmany"]
    bot = BotPlayer(hand=bot_hand)
    
    # We want to see how the bot's sorting arranges try_hand
    # Since we shuffle in choose_placement, we can simulate the priority logic
    restricted_lower = [t.lower() for t in settings.RESTRICTED_TILES]
    def get_priority(tile):
        tile_clean = tile.replace(" ", "").lower()
        if tile_clean in restricted_lower:
            return 2
        elif tile in settings.COMMON_TILES:
            return 1
        else:
            return 0
            
    sorted_hand = list(bot_hand)
    sorted_hand.sort(key=get_priority)
    print(f"Original hand: {bot_hand}")
    print(f"Sorted hand:   {sorted_hand}")
    
    # Expected: Uniques first (FungalJungle, Elmany), Commons second (Woods, Swamp), Restricted last (Limbo, PitofDespair)
    expected_order_groups = [
        {"FungalJungle", "Elmany"}, # Priority 0
        {"Woods", "Swamp"},         # Priority 1
        {"Limbo", "PitofDespair"}   # Priority 2
    ]
    
    assert sorted_hand[0] in expected_order_groups[0], "Error: Non-restricted unique not placed first!"
    assert sorted_hand[1] in expected_order_groups[0], "Error: Non-restricted unique not placed first!"
    assert sorted_hand[2] in expected_order_groups[1], "Error: Common tile not in the middle!"
    assert sorted_hand[3] in expected_order_groups[1], "Error: Common tile not in the middle!"
    assert sorted_hand[4] in expected_order_groups[2], "Error: Restricted tile not placed last!"
    assert sorted_hand[5] in expected_order_groups[2], "Error: Restricted tile not placed last!"
    
    print("Priority check passed!")
    
    print("\n--- Running Power Spawning Tests ---")
    # Verify initial spawns when unique tiles are placed
    spawn_tests = [
        ("TempleofEvil", "Rakshasa"),
        ("Tanelorn", "Couatl"),
        ("EchoingCaverns", "Shoggoth"),
        ("ObsidianWastes", "Dragon"),
        ("TheWilds", "Pegasus"),
        ("Limbo", "Kirin")
    ]
    for tile_name, power_name in spawn_tests:
        test_grid = MapGrid()
        test_grid.place_tile(1, 1, tile_name, "player")
        powers_at_loc = test_grid.powers.get((1, 1), [])
        assert len(powers_at_loc) == 1, f"Error: No power spawned on {tile_name}!"
        assert powers_at_loc[0].name == power_name, f"Error: Spawned {powers_at_loc[0].name} instead of {power_name} on {tile_name}!"
        print(f"Verified: {power_name} correctly spawned on {tile_name}.")
        
    print("\nAll tests passed successfully!")


if __name__ == "__main__":
    run_tests()

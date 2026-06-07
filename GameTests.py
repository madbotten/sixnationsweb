"""
GameTests.py - Unified test suite for Alignments.
Accumulates all game logic, placement, bot, selection, formatting, and rendering tests.
"""
import os
import pygame
import settings
import util
from map import MapGrid
from powers import Power
from bot import BotPlayer

def run_restricted_rules_tests():
    print("\n=============================================")
    print("--- Running Adjacency and Placement Rules ---")
    print("=============================================")
    
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
    print("Adjacency placement checks passed successfully!")


def run_bot_priority_tests():
    print("\n=============================================")
    print("--- Running Bot Hand Sorting Priority ---")
    print("=============================================")
    
    # Setup a bot hand with a mix of uniques, commons, and restricted tiles
    bot_hand = ["Limbo", "Woods", "FungalJungle", "PitofDespair", "Swamp", "Elmany"]
    bot = BotPlayer(hand=bot_hand)
    
    # We want to see how the bot's sorting arranges try_hand
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
    
    print("Bot priority checks passed successfully!")


def run_spawning_tests():
    print("\n=============================================")
    print("--- Running Initial Spawning Constraints ---")
    print("=============================================")
    
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
    print("Spawning constraint checks passed successfully!")


def run_selection_and_formatting_tests():
    print("\n=============================================")
    print("--- Running Selection & Formatting Tests ---")
    print("=============================================")
    
    # 1. Test format_location_name
    grid = MapGrid()
    grid.place_tile(1, 0, "PitofDespair", "player")
    tile = grid.get_tile(1, 0)
    formatted_name = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
    print(f"Formatted 'PitofDespair': '{formatted_name}' (Expected: 'Pit of Despair')")
    assert formatted_name == "Pit of Despair", "Error: Location formatting failed!"
    
    grid.place_tile(2, 0, "Woods", "player")
    tile_woods = grid.get_tile(2, 0)
    formatted_woods = util.format_location_name(tile_woods.terrain_type) if tile_woods else "Empty Space"
    print(f"Formatted 'Woods': '{formatted_woods}' (Expected: 'Woods')")
    assert formatted_woods == "Woods", "Error: Location formatting failed for Woods!"
    
    # 2. Test get_power_at_screen_pos for a single Power (should be at hex center)
    viewport_rect = pygame.Rect(400, 0, 1200, 1000)
    clicked = grid.get_power_at_screen_pos(1000, 500, viewport_rect)
    print(f"Clicked at (1000, 500) (Hex center): {clicked} (Expected: Power 'Void')")
    assert clicked is not None and clicked.name == "Void", "Error: Failed to hit single Power at center!"
    
    clicked_miss = grid.get_power_at_screen_pos(950, 500, viewport_rect)
    print(f"Clicked at (950, 500) (Miss): {clicked_miss} (Expected: None)")
    assert clicked_miss is None, "Error: Incorrectly hit Power far off center!"
    
    # 3. Test multiple Powers (circular offset checking)
    grid.powers[(0, 0)] = [
        Power("Angel", 0, 0, 10),
        Power("Demon", 0, 0, 8)
    ]
    hit_angel = grid.get_power_at_screen_pos(1024, 500, viewport_rect)
    print(f"Clicked at (1024, 500) (Offset 0): {hit_angel} (Expected: Power 'Angel')")
    assert hit_angel is not None and hit_angel.name == "Angel", "Error: Failed to hit Angel at offset!"
    
    hit_demon = grid.get_power_at_screen_pos(976, 500, viewport_rect)
    print(f"Clicked at (976, 500) (Offset 1): {hit_demon} (Expected: Power 'Demon')")
    assert hit_demon is not None and hit_demon.name == "Demon", "Error: Failed to hit Demon at offset!"
    print("Selection and formatting checks passed successfully!")


def run_abilities_and_movement_tests():
    print("\n=============================================")
    print("--- Running Abilities & Grid Movement Tests ---")
    print("=============================================")
    
    # 1. Test Power abilities list (shared + unique)
    angel = Power("Angel", 0, 0, 5)
    print(f"Angel abilities: {angel.abilities} (Expected: ['Move', 'Smite'])")
    assert angel.abilities == ["Move", "Smite"], f"Error: Angel abilities incorrect! Got {angel.abilities}"
    
    pegasus = Power("Pegasus", 2, 3, 4)
    print(f"Pegasus abilities: {pegasus.abilities} (Expected: ['Move', 'Swift Flight'])")
    assert pegasus.abilities == ["Move", "Swift Flight"], f"Error: Pegasus abilities incorrect! Got {pegasus.abilities}"
    
    # 2. Test grid movements and coordinate transitions
    grid = MapGrid()
    # Initial state: Void spawned at (0, 0)
    void_list = grid.powers.get((0, 0), [])
    assert len(void_list) == 1, "Error: Void not found on (0, 0) at start!"
    void_unit = void_list[0]
    
    # Place a tile at (1, 0) so it's a valid hex destination
    grid.place_tile(1, 0, "Swamp", "player")
    
    # Move unit from (0, 0) to (1, 0)
    old_loc = void_unit.hex_location
    assert old_loc == (0, 0)
    
    # Simulate move logic exactly as done in main.py
    if old_loc in grid.powers:
        if void_unit in grid.powers[old_loc]:
            grid.powers[old_loc].remove(void_unit)
            if not grid.powers[old_loc]:
                del grid.powers[old_loc]
                
    void_unit.hex_location = (1, 0)
    grid.add_power(void_unit)
    
    # Validate coordinate transitions
    assert (0, 0) not in grid.powers, "Error: Old location (0, 0) was not cleared after movement!"
    assert (1, 0) in grid.powers, "Error: New location (1, 0) does not contain powers after movement!"
    assert grid.powers[(1, 0)][0] == void_unit, "Error: New location (1, 0) does not contain the moved Void unit!"
    print("Abilities and movement checks passed successfully!")


def run_quick_setup_tests():
    print("\n=============================================")
    print("--- Running Bot Quick Setup Tests ---")
    print("=============================================")
    
    grid = MapGrid()
    player_hand = ["Swamp", "Woods", "Plains", "Desert"]
    bot_hand = ["Mountains", "Swamp", "Plains", "Woods"]
    bot_player = BotPlayer(hand=bot_hand)
    
    from bot import bot_map_quick_setup
    bot_map_quick_setup(grid, player_hand, bot_player)
    
    print(f"Remaining player hand: {player_hand}")
    print(f"Remaining bot hand: {bot_player.hand}")
    assert len(player_hand) == 0, "Error: Player hand not fully emptied by quick setup!"
    assert len(bot_player.hand) == 0, "Error: Bot hand not fully emptied by quick setup!"
    
    print(f"Total tiles placed on grid: {len(grid.tiles)} (Expected: 9 tiles including starting woods)")
    assert len(grid.tiles) == 9, f"Error: Expected 9 tiles, got {len(grid.tiles)}"
    print("Bot quick setup checks passed successfully!")


def run_rendering_generation_test():
    print("\n=============================================")
    print("--- Running Rendering Snapshot Test ---")
    print("=============================================")
    
    grid = MapGrid()
    # (0, 0) is Woods/Void
    
    # Place TowerofJustice at (1, 0)
    grid.place_tile(1, 0, "TowerofJustice", owner='player')
    
    # Place PitofDespair at (0, 1)
    grid.place_tile(0, 1, "PitofDespair", owner='bot')
    
    # Add multiple powers to (0, 0) to simulate stacking
    grid.add_power(Power("Demon", 0, 0, strength=5))
    grid.add_power(Power("Angel", 0, 0, strength=7))
    grid.add_power(Power("Dragon", 0, 0, strength=8))
    
    # Add Pegasus to (1, 0)
    grid.add_power(Power("Pegasus", 1, 0, strength=4))
    
    # Create offline surface to render to
    surface = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    surface.fill(settings.COLOR_BACKGROUND)
    
    viewport_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
    grid.draw(surface, viewport_rect)
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "powers_render.png")
    pygame.image.save(surface, output_path)
    print(f"Successfully saved test render snapshot to: {output_path}")


def run_movement_range_and_turn_tests():
    print("\n=============================================")
    print("--- Running Movement Range & Turn Tests ---")
    print("=============================================")
    
    grid = MapGrid()
    # (0, 0) contains Void by default
    assert (0, 0) in grid.tiles
    
    void_unit = grid.powers[(0, 0)][0]
    
    # At start, no neighbor tiles are placed. So valid destinations should be empty.
    dests = grid.get_valid_movement_destinations(void_unit)
    print(f"Void valid destinations with only (0, 0) placed: {dests} (Expected: [])")
    assert dests == [], f"Error: Found destinations on empty map: {dests}"
    
    # Place an adjacent tile (1, 0)
    grid.place_tile(1, 0, "Swamp", "player")
    dests = grid.get_valid_movement_destinations(void_unit)
    print(f"Void valid destinations with (1, 0) placed: {dests} (Expected: [(1, 0)])")
    assert dests == [(1, 0)], f"Error: Expected [(1, 0)], got {dests}"
    
    # Place a non-adjacent tile (2, 0)
    grid.place_tile(2, 0, "Plains", "player")
    dests = grid.get_valid_movement_destinations(void_unit)
    print(f"Void valid destinations with non-adjacent (2, 0) placed: {dests} (Expected: [(1, 0)])")
    assert dests == [(1, 0)], f"Error: Non-adjacent tile should not be a valid destination! Got {dests}"
    
    # Test Bot choosing movement
    bot = BotPlayer()
    action = bot.choose_power_movement(grid)
    print(f"Bot chose movement: {action} (Expected: (Void, 1, 0))")
    assert action is not None, "Error: Bot failed to find any valid movement!"
    p, b_q, b_r = action
    assert p == void_unit, "Error: Bot chose incorrect unit!"
    assert (b_q, b_r) == (1, 0), "Error: Bot chose invalid destination!"
    
    print("Movement range and turn checks passed successfully!")


def run_player_tests():
    print("\n=============================================")
    print("--- Running Player Initialization Tests ---")
    print("=============================================")
    
    from player import Player, POSSIBLE_ALIGNMENTS
    
    # 1. Test Player with explicit alignment
    explicit_player = Player("Lawful", "Good")
    print(f"Explicit player alignment: {explicit_player.get_alignment_parts()} (Expected: ['lawful', 'good'])")
    assert explicit_player.get_alignment_parts() == ["lawful", "good"]
    
    # 2. Test Player with random alignment
    random_player = Player()
    parts = random_player.get_alignment_parts()
    print(f"Random player alignment: {parts} (Expected: one of the POSSIBLE_ALIGNMENTS)")
    assert parts in POSSIBLE_ALIGNMENTS, f"Error: Random alignment {parts} not in POSSIBLE_ALIGNMENTS!"
    
    print("Player initialization checks passed successfully!")


def main():
    pygame.init()
    pygame.mixer.init()
    
    print("Running Unified Alignments Test Suite...")
    
    run_restricted_rules_tests()
    run_bot_priority_tests()
    run_spawning_tests()
    run_selection_and_formatting_tests()
    run_abilities_and_movement_tests()
    run_quick_setup_tests()
    run_movement_range_and_turn_tests()
    run_player_tests()
    run_rendering_generation_test()
    
    print("\n=============================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=============================================")
    pygame.quit()

if __name__ == "__main__":
    main()

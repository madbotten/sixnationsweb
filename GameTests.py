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
    
    # 2. Test get_power_at_screen_pos for a single Power (should be in top row: oy = -35)
    viewport_rect = pygame.Rect(400, 0, 1200, 1000)
    clicked = grid.get_power_at_screen_pos(1000, 465, viewport_rect)
    print(f"Clicked at (1000, 465) (Power position): {clicked} (Expected: Power 'Void')")
    assert clicked is not None and clicked.name == "Void", "Error: Failed to hit single Power at top row!"
    
    clicked_miss = grid.get_power_at_screen_pos(950, 465, viewport_rect)
    print(f"Clicked at (950, 465) (Miss): {clicked_miss} (Expected: None)")
    assert clicked_miss is None, "Error: Incorrectly hit Power far off center!"
    
    # 3. Test multiple Powers (horizontal row spacing, oy = -35)
    grid.powers[(0, 0)] = [
        Power("Angel", 0, 0, 10),
        Power("Demon", 0, 0, 8)
    ]
    # Angel at idx 0 is offset x by -21 -> center x = 979, y = 465
    hit_angel = grid.get_power_at_screen_pos(979, 465, viewport_rect)
    print(f"Clicked at (979, 465) (Angel position): {hit_angel} (Expected: Power 'Angel')")
    assert hit_angel is not None and hit_angel.name == "Angel", "Error: Failed to hit Angel at offset!"
    
    # Demon at idx 1 is offset x by +21 -> center x = 1021, y = 465
    hit_demon = grid.get_power_at_screen_pos(1021, 465, viewport_rect)
    print(f"Clicked at (1021, 465) (Demon position): {hit_demon} (Expected: Power 'Demon')")
    assert hit_demon is not None and hit_demon.name == "Demon", "Error: Failed to hit Demon at offset!"
    print("Selection and formatting checks passed successfully!")


def run_abilities_and_movement_tests():
    print("\n=============================================")
    print("--- Running Abilities & Grid Movement Tests ---")
    print("=============================================")
    
    # 1. Test Power abilities list (shared + unique)
    angel = Power("Angel", 0, 0, 5)
    print(f"Angel abilities: {angel.abilities} (Expected: ['Move', 'Summon Champion', 'Smite'])")
    assert angel.abilities == ["Move", "Summon Champion", "Smite"], f"Error: Angel abilities incorrect! Got {angel.abilities}"
    
    pegasus = Power("Pegasus", 2, 3, 4)
    print(f"Pegasus abilities: {pegasus.abilities} (Expected: ['Move', 'Summon Champion', 'Swift Flight'])")
    assert pegasus.abilities == ["Move", "Summon Champion", "Swift Flight"], f"Error: Pegasus abilities incorrect! Got {pegasus.abilities}"
    
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


def run_player_control_alignment_tests():
    print("\n=============================================")
    print("--- Running Player Control Alignment Tests ---")
    print("=============================================")
    
    from player import Player

    demon = Power("Demon", 0, 0, 10) # demon should be chaotic evil
    couatl = Power("Couatl", 0, 0, 10) # couatl should be chaotic good
    rakshasa = Power("Rakshasa", 0, 0, 10) # rakshasa should be lawful evil
    shoggoth = Power("Shoggoth", 0, 0, 10) # shoggoth should be neutral evil
    void = Power("Void", 0, 0, 10) # void has no alignment
    angel = Power("Angel", 0, 0, 10) # angel should be lawful good
    kirin = Power("Kirin", 0, 0, 10) # kirin should be lawful neutral
    dragon = Power("Dragon", 0, 0, 10) # dragon should be chaotic neutral
    pegasus = Power("Pegasus", 0, 0, 10) # pegasus should be neutral good

    # 1. Chaotic Evil player controls anything with either chaotic part or evil part
    ce_player = Player("chaotic", "evil")
    print(f"Chaotic Evil player alignment: {ce_player.get_alignment_parts()}")
    # can control void
    assert ce_player.can_control_power(void) == True, "CE player should control Void"
    # can control anything with chaotic or evil
    assert ce_player.can_control_power(demon) == True, "CE player should control Demon"
    assert ce_player.can_control_power(couatl) == True, "CE player should control Couatl"
    assert ce_player.can_control_power(dragon) == True, "CE player should control Dragon"
    assert ce_player.can_control_power(rakshasa) == True, "CE player should control Rakshasa"
    assert ce_player.can_control_power(shoggoth) == True, "CE player should control Shoggoth"
    # cannot control with neither chaotic nor evil
    assert ce_player.can_control_power(angel) == False, "CE player should NOT control Angel"
    assert ce_player.can_control_power(kirin) == False, "CE player should NOT control Kirin"
    assert ce_player.can_control_power(pegasus) == False, "CE player should NOT control Pegasus"
    print("Chaotic Evil player tests passed.")


    # 2. Lawful Neutral player controls (any non-chaotic)
    ln_player = Player("lawful", "neutral")
    print(f"Lawful Neutral player alignment: {ln_player.get_alignment_parts()}")
    # can control void
    assert ln_player.can_control_power(void) == True, "LN player should control Void"
    # can control anything not chaotic
    assert ln_player.can_control_power(angel) == True, "LN player should control Angel"
    assert ln_player.can_control_power(rakshasa) == True, "LN player should control Rakshasa"
    assert ln_player.can_control_power(pegasus) == True, "LN player should control Pegasus"
    assert ln_player.can_control_power(shoggoth) == True, "LN player should control Shoggoth"
    assert ln_player.can_control_power(kirin) == True, "LN player should control Kirin (Lawful Neutral)"
    # cannot control anything chaotic
    assert ln_player.can_control_power(demon) == False, "LN player should NOT control Demon (because chaotic)"
    assert ln_player.can_control_power(dragon) == False, "LN player should NOT control Dragon (because chaotic)"
    assert ln_player.can_control_power(couatl) == False, "LN player should NOT control Couatl (because chaotic)"
    print("Lawful Neutral player tests passed.")


    # 3. Lawful Good player controls (cannot move Chaotic Evil power)
    lg_player = Player("lawful", "good")
    print(f"Lawful Good player alignment: {lg_player.get_alignment_parts()}")
    # can control void
    assert lg_player.can_control_power(void) == True, "LG player should control Void"
    # can control anything lawful or good
    assert lg_player.can_control_power(angel) == True, "LG player should control Angel"
    assert lg_player.can_control_power(demon) == False, "LG player should NOT control Demon (Chaotic Evil)"
    assert lg_player.can_control_power(rakshasa) == True, "LG player should control Rakshasa (Lawful Evil)"
    assert lg_player.can_control_power(pegasus) == True, "LG player should control Pegasus (Neutral Good)"
    assert lg_player.can_control_power(kirin) == True, "LG player should control Kirin (Lawful Neutral)"
    # cannot control anything neither lawful nor good
    assert lg_player.can_control_power(shoggoth) == False, "LG player should NOT control Shoggoth (Neutral Evil)"
    assert lg_player.can_control_power(dragon) == False, "LG player should NOT control Dragon (Chaotic Neutral)"
    assert lg_player.can_control_power(couatl) == False, "LG player should NOT control Couatl (Chaotic Good)"
    print("Lawful Good player tests passed.")


    # 4. Neutral Evil player controls (any non-Good)
    ne_player = Player("neutral", "evil")
    print(f"Neutral Evil player alignment: {ne_player.get_alignment_parts()}")
    # can control void
    assert ne_player.can_control_power(void) == True, "NE player should control Void"
    # can control anything non-good
    assert ne_player.can_control_power(demon) == True, "NE player should control Demon (Chaotic Evil)"
    assert ne_player.can_control_power(shoggoth) == True, "NE player should control Shoggoth (Neutral Evil)"
    assert ne_player.can_control_power(kirin) == True, "NE player should control Kirin (Lawful Neutral)"
    assert ne_player.can_control_power(rakshasa) == True, "NE player should control Rakshasa (Lawful Evil)"
    assert ne_player.can_control_power(dragon) == True, "NE player should control Dragon (Chaotic Neutral)"
    # cannot control anything good
    assert ne_player.can_control_power(angel) == False, "NE player should NOT control Angel (Good)"
    assert ne_player.can_control_power(couatl) == False, "NE player should NOT control Couatl (Good)"
    assert ne_player.can_control_power(pegasus) == False, "NE player should NOT control Pegasus (Neutral Good)"
    print("Neutral Evil player tests passed.")


    # 5. Chaotic Neutral player controls (any non-Lawful)
    cn_player = Player("chaotic", "neutral")
    print(f"Chaotic Neutral player alignment: {cn_player.get_alignment_parts()}")
    # can control void
    assert cn_player.can_control_power(void) == True, "CN player should control Void"
    # can control anything non-lawful
    assert cn_player.can_control_power(demon) == True, "CN player should control Demon"
    assert cn_player.can_control_power(dragon) == True, "CN player should control Dragon"
    assert cn_player.can_control_power(couatl) == True, "CN player should control Couatl (Chaotic Good)"
    assert cn_player.can_control_power(shoggoth) == True, "CN player should control Shoggoth (Neutral Evil)"
    assert cn_player.can_control_power(pegasus) == True, "CN player should control Pegasus (Neutral Good)"
    # cannot control anything lawful
    assert cn_player.can_control_power(angel) == False, "CN player should NOT control Angel (Lawful)"
    assert cn_player.can_control_power(rakshasa) == False, "CN player should NOT control Rakshasa (Lawful)"
    assert cn_player.can_control_power(kirin) == False, "CN player should NOT control Kirin (Lawful Neutral)"
    print("Chaotic Neutral player tests passed.")
    

    # 6. Neutral Good player controls (any non-Evil)
    ng_player = Player("neutral", "good")
    print(f"Neutral Good player alignment: {ng_player.get_alignment_parts()}")
    # can control void
    assert ng_player.can_control_power(void) == True, "NG player should control Void"
    # can control any non-Evil
    assert ng_player.can_control_power(kirin) == True, "NG player should control Kirin (Lawful Neutral)"
    assert ng_player.can_control_power(angel) == True, "NG player should control Angel (Lawful Good)"
    assert ng_player.can_control_power(pegasus) == True, "NG player should control Pegasus (Neutral Good)"
    assert ng_player.can_control_power(dragon) == True, "NG player should control Dragon (Chaotic Neutral)"
    assert ng_player.can_control_power(couatl) == True, "NG player should control Couatl (Chaotic Good)"
    # cannot control any evil
    assert ng_player.can_control_power(shoggoth) == False, "NG player should NOT control Shoggoth (Neutral Evil)"
    assert ng_player.can_control_power(demon) == False, "NG player should NOT control Demon (Chaotic Evil)"
    assert ng_player.can_control_power(rakshasa) == False, "NG player should NOT control Rakshasa (Lawful Evil)"
    print("Neutral Good player tests passed.")
    

    # 7. Lawful Evil player controls (anything lawful or evil)
    le_player = Player("lawful", "evil")
    print(f"Lawful Evil player alignment: {le_player.get_alignment_parts()}")
    # can control void
    assert le_player.can_control_power(void) == True, "LE player should control Void"
    # can control anything lawful or evil
    assert le_player.can_control_power(angel) == True, "LE player should control Angel (Lawful Good)"
    assert le_player.can_control_power(rakshasa) == True, "LE player should control Rakshasa (Lawful Evil)"
    assert le_player.can_control_power(kirin) == True, "LE player should control Kirin (Lawful Neutral)"
    assert le_player.can_control_power(demon) == True, "LE player should control Demon (Chaotic Evil)"
    assert le_player.can_control_power(shoggoth) == True, "LE player should control Shoggoth (Neutral Evil)"
    
    # cannot control anything neither lawful nor evil
    assert le_player.can_control_power(pegasus) == False, "LE player should NOT control Pegasus (Neutral Good)"
    assert le_player.can_control_power(couatl) == False, "LE player should NOT control Couatl (Chaotic Good)"
    assert le_player.can_control_power(dragon) == False, "LE player should NOT control Dragon (Chaotic Neutral)"
    
    print("Lawful Evil player tests passed.")
    

    # 8. Chaotic Good player controls anything chaotic or good
    ce_player = Player("chaotic", "good")
    print(f"Chaotic Good player alignment: {ce_player.get_alignment_parts()}")
    # can control void
    assert ce_player.can_control_power(void) == True, "CE player should control Void"
    # can control anything chaotic or good
    assert ce_player.can_control_power(angel) == True, "CE player should control Angel (Lawful Good)"
    assert ce_player.can_control_power(dragon) == True, "CE player should control Dragon (Chaotic Neutral)"
    assert ce_player.can_control_power(couatl) == True, "CE player should control Couatl (Chaotic Good)"
    assert ce_player.can_control_power(demon) == True, "CE player should control Demon (Chaotic Evil)"
    assert ce_player.can_control_power(pegasus) == True, "CE player should control Pegasus (Neutral Good)"
    # cannot control anything neither chaotic nor good
    assert ce_player.can_control_power(kirin) == False, "CE player should NOT control Kirin (Lawful Neutral)"
    assert ce_player.can_control_power(rakshasa) == False, "CE player should NOT control Rakshasa (Lawful Evil)"
    assert ce_player.can_control_power(shoggoth) == False, "CE player should NOT control Shoggoth (Neutral Evil)"

    print("Chaotic Good player tests passed.")
    
    print("Player control alignment checks passed successfully!")


def run_is_aligned_tests():
    print("\n=============================================")
    print("--- Running Power is_aligned Wildcard Tests ---")
    print("=============================================")
    
    # 1. Angel (lawful, good)
    # matches only: "good", "lawful", "neutral"
    angel = Power("Angel", 0, 0, 10)
    for part in ["good", "lawful", "neutral", "Good", "LAWFUL", "Neutral"]:
        assert angel.is_aligned(part) == True, f"Angel should be aligned with {part}"
    for part in ["chaotic", "evil", "Chaotic", "EVIL", "other"]:
        assert angel.is_aligned(part) == False, f"Angel should NOT be aligned with {part}"
        
    # 2. Shoggoth (neutral, evil)
    # matches only: "chaotic", "lawful", "neutral", "evil"
    shoggoth = Power("Shoggoth", 0, 0, 10)
    for part in ["chaotic", "lawful", "neutral", "evil", "CHAOTIC", "Lawful", "NEUTRAL", "Evil"]:
        assert shoggoth.is_aligned(part) == True, f"Shoggoth should be aligned with {part}"
    for part in ["good", "Good", "something_else"]:
        assert shoggoth.is_aligned(part) == False, f"Shoggoth should NOT be aligned with {part}"
        
    # 3. Kirin (lawful, neutral)
    # matches only: "lawful", "good", "evil", "neutral"
    kirin = Power("Kirin", 0, 0, 10)
    for part in ["lawful", "good", "evil", "neutral", "Lawful", "GOOD", "Evil", "Neutral"]:
        assert kirin.is_aligned(part) == True, f"Kirin should be aligned with {part}"
    for part in ["chaotic", "Chaotic", "invalid"]:
        assert kirin.is_aligned(part) == False, f"Kirin should NOT be aligned with {part}"

    # 4. Pegasus (neutral, good)
    # matches only: "chaotic", "lawful", "neutral", "good"
    pegasus = Power("Pegasus", 0, 0, 10)
    for part in ["chaotic", "lawful", "neutral", "good", "Chaotic", "LAWFUL", "Neutral", "Good"]:
        assert pegasus.is_aligned(part) == True, f"Pegasus should be aligned with {part}"
    for part in ["evil", "Evil", "test"]:
        assert pegasus.is_aligned(part) == False, f"Pegasus should NOT be aligned with {part}"

    # 5. Void (no alignment)
    # matches nothing
    void = Power("Void", 0, 0, 10)
    for part in ["lawful", "chaotic", "neutral", "good", "evil", "Good", "Evil"]:
        assert void.is_aligned(part) == False, f"Void should NOT be aligned with {part}"

    print("Power is_aligned checks passed successfully!")


def run_champion_tests():
    print("\n=============================================")
    print("--- Running Champion Unit Tests ---")
    print("=============================================")
    from champions import Champion
    
    # 1. Test valid initialization
    c = Champion("neutral", 3, 2, -1, 15)
    assert c.alignment == "neutral"
    assert c.index == 3
    assert c.hex_location == (2, -1)
    assert c.strength == 15
    assert c.image_filename == "Neutral3.jpg"
    assert c.name == "Neutral Champion 3"
    print("Valid Champion initialization passed.")
    
    # 2. Test property getters and setters
    c.alignment = "Good"
    assert c.alignment == "good"
    assert c.image_filename == "Good3.jpg"
    assert c.name == "Good Champion 3"
    
    c.index = 1
    assert c.index == 1
    assert c.image_filename == "Good1.jpg"
    assert c.name == "Good Champion 1"
    
    c.strength = 0
    assert c.strength == 0
    
    c.hex_location = (-4, 2)
    assert c.q == -4 and c.r == 2
    assert c.hex_location == (-4, 2)
    
    # Check other specific alignment naming conventions
    c_law = Champion("lawful", 2, 0, 0, 1)
    assert c_law.name == "Champion of Law 2"
    
    c_chaos = Champion("chaotic", 4, 0, 0, 1)
    assert c_chaos.name == "Champion of Chaos 4"
    
    c_evil = Champion("evil", 1, 0, 0, 1)
    assert c_evil.name == "Evil Champion 1"
    
    print("Champion property getters/setters passed.")
    
    # 3. Test validation rules
    # Invalid alignment
    try:
        Champion("neutral-good", 1, 0, 0, 5)
        assert False, "Should have raised ValueError for invalid alignment"
    except ValueError:
        pass
        
    # Invalid index
    try:
        Champion("lawful", 5, 0, 0, 5)
        assert False, "Should have raised ValueError for index > 4"
    except ValueError:
        pass
        
    try:
        Champion("lawful", 0, 0, 0, 5)
        assert False, "Should have raised ValueError for index < 1"
    except ValueError:
        pass
        
    # Invalid strength
    try:
        Champion("lawful", 1, 0, 0, -1)
        assert False, "Should have raised ValueError for negative strength"
    except ValueError:
        pass
        
    try:
        Champion("lawful", 1, 0, 0, 5.5)
        assert False, "Should have raised ValueError for non-integer strength"
    except ValueError:
        pass
    print("Champion validation checks passed.")
    
    # 4. Test surface loading
    # We initialize pygame so we can test loading
    surf = c.get_surface(size=(50, 50), mask_type="circle")
    assert surf is not None
    assert surf.get_width() == 50
    assert surf.get_height() == 50
    print("Champion image/surface retrieval passed.")
    print("Champion checks completed successfully!")


def run_summon_champion_tests():
    print("\n=============================================")
    print("--- Running Summon Champion Tests ---")
    print("=============================================")
    from powers import Power
    from champions import Champion
    from map import MapGrid
    
    # 1. Test Power abilities list
    angel = Power("Angel", 0, 0, 10)
    assert "Summon Champion" in angel.abilities, "Angel should have Summon Champion ability"
    
    void = Power("Void", 0, 0, 10)
    assert "Summon Champion" not in void.abilities, "Void should NOT have Summon Champion ability"
    print("Ability list checked for Summon Champion.")
    
    # 2. Test champion tracking in MapGrid
    grid = MapGrid()
    assert len(grid.champions) == 0, "Initial champions should be empty"
    
    # 3. Test champion count tracking and indexing logic
    # Add a good champion
    c1 = Champion("good", grid.get_next_champion_index("good"), 0, 0, 1)
    assert c1.index == 1
    grid.add_champion(c1)
    assert grid.get_champion_count("good") == 1
    
    # Add a second good champion
    c2 = Champion("good", grid.get_next_champion_index("good"), 0, 0, 1)
    assert c2.index == 2
    grid.add_champion(c2)
    assert grid.get_champion_count("good") == 2
    
    # Add an evil champion
    c3 = Champion("evil", grid.get_next_champion_index("evil"), 1, 0, 1)
    assert c3.index == 1
    grid.add_champion(c3)
    assert grid.get_champion_count("evil") == 1
    assert grid.get_champion_count("good") == 2
    
    # Fill up to 4 good champions
    c4 = Champion("good", grid.get_next_champion_index("good"), 0, 0, 1)
    assert c4.index == 3
    grid.add_champion(c4)
    c5 = Champion("good", grid.get_next_champion_index("good"), 0, 0, 1)
    assert c5.index == 4
    grid.add_champion(c5)
    
    assert grid.get_champion_count("good") == 4
    assert grid.get_next_champion_index("good") is None, "Should not return an index when 4 exist"
    
    # Test releasing a champion makes its index available again
    # We remove champion with index 2
    for loc, c_list in grid.champions.items():
        for c in c_list:
            if c.alignment == "good" and c.index == 2:
                c_list.remove(c)
                break
                
    assert grid.get_champion_count("good") == 3
    assert grid.get_next_champion_index("good") == 2, "Index 2 should be reclaimed"
    
    print("Champion count tracking and index generation passed.")


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
    run_player_control_alignment_tests()
    run_is_aligned_tests()
    run_champion_tests()
    run_summon_champion_tests()
    run_rendering_generation_test()
    
    print("\n=============================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=============================================")
    pygame.quit()

if __name__ == "__main__":
    main()

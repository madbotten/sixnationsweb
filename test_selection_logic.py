"""
Verification script for selection helper functions and formatting.
"""
import pygame
import settings
import util
from map import MapGrid
from powers import Power

def test_selection_helpers():
    print("--- Running Selection Logic Tests ---")
    pygame.init()
    
    # 1. Test format_location_name
    grid = MapGrid()
    grid.place_tile(1, 0, "PitofDespair", "player")
    tile = grid.get_tile(1, 0)
    formatted_name = util.format_location_name(tile.terrain_type) if tile else "Empty Space"
    print(f"Formatted 'PitofDespair': '{formatted_name}' (Expected: 'Pit of Despair')")
    assert formatted_name == "Pit of Despair", "Error: Location formatting failed!"
    
    # Test flat-out common tile
    grid.place_tile(2, 0, "Woods", "player")
    tile_woods = grid.get_tile(2, 0)
    formatted_woods = util.format_location_name(tile_woods.terrain_type) if tile_woods else "Empty Space"
    print(f"Formatted 'Woods': '{formatted_woods}' (Expected: 'Woods')")
    assert formatted_woods == "Woods", "Error: Location formatting failed for Woods!"
    
    # 2. Test get_power_at_screen_pos for a single Power (should be at hex center)
    # The starting tile is Woods at (0, 0) and contains the Void power.
    viewport_rect = pygame.Rect(400, 0, 1200, 1000)
    
    # Center of viewport: cx = 400 + 600 = 1000.
    # Center of hex (0, 0): lx = 0, ly = 0.
    # So screen center of (0, 0) is: 1000 + camera_x, 500 + camera_y.
    # With camera_x = 0, camera_y = 0, center is (1000, 500).
    # Click right on center (1000, 500)
    clicked = grid.get_power_at_screen_pos(1000, 500, viewport_rect)
    print(f"Clicked at (1000, 500) (Hex center): {clicked} (Expected: Power 'Void')")
    assert clicked is not None and clicked.name == "Void", "Error: Failed to hit single Power at center!"
    
    # Click far off center (950, 500) -> should miss
    clicked_miss = grid.get_power_at_screen_pos(950, 500, viewport_rect)
    print(f"Clicked at (950, 500) (Miss): {clicked_miss} (Expected: None)")
    assert clicked_miss is None, "Error: Incorrectly hit Power far off center!"
    
    # 3. Test multiple Powers (circular offset checking)
    # Clear and place multiple powers on (0, 0): e.g., Angel (idx 0), Demon (idx 1)
    grid.powers[(0, 0)] = [
        Power("Angel", 0, 0, 10),
        Power("Demon", 0, 0, 8)
    ]
    # For num_powers = 2:
    # idx 0: angle = 0, ox = 24, oy = 0. Center = (1024, 500).
    # idx 1: angle = pi, ox = -24, oy = 0. Center = (976, 500).
    
    # Click at (1024, 500) -> should hit Angel
    hit_angel = grid.get_power_at_screen_pos(1024, 500, viewport_rect)
    print(f"Clicked at (1024, 500) (Offset 0): {hit_angel} (Expected: Power 'Angel')")
    assert hit_angel is not None and hit_angel.name == "Angel", "Error: Failed to hit Angel at offset!"
    
    # Click at (976, 500) -> should hit Demon
    hit_demon = grid.get_power_at_screen_pos(976, 500, viewport_rect)

    print(f"Clicked at (976, 500) (Offset 1): {hit_demon} (Expected: Power 'Demon')")
    assert hit_demon is not None and hit_demon.name == "Demon", "Error: Failed to hit Demon at offset!"
    
    print("\nAll selection tests passed successfully!")
    pygame.quit()

if __name__ == "__main__":
    test_selection_helpers()

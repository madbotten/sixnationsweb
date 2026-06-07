"""
Test script to verify drawing of multiple Powers on a single hex tile.
Saves a rendering to powers_render.png.
"""
import os
import pygame
import settings
import util
from map import MapGrid
from powers import Power

def run_test():
    # Force pygame to use dummy video driver for headless environments if needed,
    # but since this runs on user's machine (mac), we can just initialize standard.
    # We will save to a surface directly.
    pygame.init()
    
    # Initialize mixer to avoid issues
    pygame.mixer.init()
    
    # Create map grid
    map_grid = MapGrid()
    
    # Place TowerofJustice at (1, 0)
    map_grid.place_tile(1, 0, "TowerofJustice", owner='player')
    
    # Place PitofDespair at (0, 1)
    map_grid.place_tile(0, 1, "PitofDespair", owner='bot')
    
    # By default:
    # (0, 0) has "woods" and "Void" power.
    # (1, 0) has "TowerofJustice" and "Angel" power.
    # (0, 1) has "PitofDespair" and "Demon" power.
    
    # Now, let's add multiple powers to the central tile (0, 0) to test stacking!
    # Currently it has Void. Let's add Demon and Angel to (0, 0) too.
    map_grid.add_power(Power("Demon", 0, 0, strength=5))
    map_grid.add_power(Power("Angel", 0, 0, strength=7))
    map_grid.add_power(Power("Dragon", 0, 0, strength=8))
    
    # Let's add multiple powers to (1, 0) too
    map_grid.add_power(Power("Pegasus", 1, 0, strength=4))
    
    # Create an offline surface of screen size to draw onto
    surface = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    surface.fill(settings.COLOR_BACKGROUND)
    
    # Viewport rect
    viewport_rect = pygame.Rect(0, 0, settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
    
    # Draw map grid
    map_grid.draw(surface, viewport_rect)
    
    # Save the surface
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "powers_render.png")
    pygame.image.save(surface, output_path)
    print(f"Successfully saved test render to: {output_path}")
    
    pygame.quit()

if __name__ == "__main__":
    run_test()

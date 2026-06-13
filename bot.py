"""
Bot Player Controller - Alignments
Handles decision making and hand operations for the automated bot player.
"""

import random
import settings
import pygame

class BotPlayer:
    def __init__(self, hand=None):
        # A list of tile strings in the bot's hand (exactly 16)
        self.hand = list(hand) if hand else []


def run_bot_muster_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Muster/Income phase.
    """
    pygame.time.delay(500)
    advance_phase_callback()


def run_bot_move_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Movement phase.
    """
    pygame.time.delay(500)
    advance_phase_callback()


def run_bot_combat_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Combat phase.
    """
    pygame.time.delay(500)
    advance_phase_callback()


def run_bot_control_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Control phase.
    """
    pygame.time.delay(500)
    advance_phase_callback()

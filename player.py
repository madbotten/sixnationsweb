"""
Player System - Alignments
Defines the Player class representing game players with alignment attributes,
as well as the bot player decision-making and phase handlers.
"""

import random
import pygame
import settings

class Player:
    def __init__(self, faction=None, is_bot=False):
        """
        Initializes a Player. If no faction is provided, selects a random Faction.
        """
        self.is_bot = is_bot
        if faction is None:
            from factions import FACTIONS
            self.faction = random.choice(FACTIONS)
        else:
            self.faction = faction

    def is_robot(self):
        """
        Returns True if this player is controlled by a robot/AI, False otherwise.
        """
        return self.is_bot

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
        return f"Player(faction={self.faction}, is_bot={self.is_bot})"


class BotPlayer:
    def __init__(self, hand=None):
        # A list of tile strings in the bot's hand (exactly 16)
        self.hand = list(hand) if hand else []


def run_bot_muster_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Muster/Income phase.

    Priority:
    1. If the faction has gold and no army sits on its stronghold, spend 1 gold
       to place an army there.
    2. Otherwise, if the faction has gold, flip a coin: on heads (50%) spend 1
       gold to place an army on a random hex controlled by the faction.
    """
    print(f"[Bot Debug] Starting Muster Phase for {faction.race}...")

    if faction.gold >= 1:
        sh_coord = map_grid.find_stronghold_coord(faction)

        # Priority 1: reinforce the stronghold if it has no army
        if sh_coord is not None:
            armies_on_stronghold = map_grid.armies.get(sh_coord, [])
            own_armies_on_sh = [a for a in armies_on_stronghold if a.faction == faction]
            if not own_armies_on_sh and map_grid.can_muster_army(faction, sh_coord[0], sh_coord[1]):
                map_grid.muster_army(faction, sh_coord[0], sh_coord[1], strength=1)
                faction.gold -= 1
                print(f"[Bot Muster] {faction.race} placed an army on its stronghold at {sh_coord}.")
                pygame.time.delay(300)
                advance_phase_callback()
                return

        # Priority 2: 50% chance to drop an army on a random controlled hex
        if faction.gold >= 1 and random.random() < 0.5:
            controlled_hexes = [
                coord for coord, tile in map_grid.tiles.items()
                if tile.owner == faction and map_grid.can_muster_army(faction, coord[0], coord[1])
            ]
            if controlled_hexes:
                target = random.choice(controlled_hexes)
                map_grid.muster_army(faction, target[0], target[1], strength=1)
                faction.gold -= 1
                print(f"[Bot Muster] {faction.race} placed an army on controlled hex {target}.")

    pygame.time.delay(500)
    advance_phase_callback()


def run_bot_move_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Movement phase.
    """
    print(f"[Bot Debug] Starting Movement Phase for {faction.race}...")
    pygame.time.delay(500)
    advance_phase_callback()


def run_bot_combat_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Combat phase.
    """
    print(f"[Bot Debug] Starting Combat Phase for {faction.race}...")
    pygame.time.delay(500)
    advance_phase_callback()


def run_bot_control_phase(faction, map_grid, advance_phase_callback):
    """
    Simulates the Bot player's Control phase.
    """
    print(f"[Bot Debug] Starting Control Phase for {faction.race}...")
    pygame.time.delay(500)
    advance_phase_callback()

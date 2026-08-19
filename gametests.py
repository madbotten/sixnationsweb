"""
GameTests.py — Unit tests for Six Nations
Covers 24 tests of basic and advanced game mechanics.
"""

import unittest
from factions import NATIONS, Nation
from player import Player
from map import MapGrid
from armies import Army
from champions import Champion, Sovereign
from bot import BotMemory
from moves import serialize_move, apply_serialized_move


class TestSixNations(unittest.TestCase):

    def setUp(self):
        # Reset ghost flags on shared nation singletons before each test
        for nation in NATIONS:
            nation.is_ghost = False
        self.grid = MapGrid()
        self.grid.generate_map()

    # -----------------------------------------------------------------------
    # 1. Diplomacy and Ring Geometry
    # -----------------------------------------------------------------------

    def test_01_diplomatic_ring_alliances(self):
        """Adjacent nations on the 0-5 ring are allies; self is neither ally nor enemy."""
        n0, n1, n2, n3, n4, n5 = NATIONS
        self.assertTrue(n0.is_ally(n1))
        self.assertTrue(n0.is_ally(n5))
        self.assertFalse(n0.is_ally(n2))
        self.assertFalse(n0.is_ally(n3))
        self.assertFalse(n0.is_ally(n0))
        self.assertTrue(n3.is_ally(n2))
        self.assertTrue(n3.is_ally(n4))

    def test_02_diplomatic_ring_enemies(self):
        """Opposite 3 nations across the ring are enemies."""
        n0, n1, n2, n3, n4, n5 = NATIONS
        # For Yellow (0): Cobalt (3), Sky Blue (2), Magenta (4) are enemies
        self.assertTrue(n0.is_enemy(n2))
        self.assertTrue(n0.is_enemy(n3))
        self.assertTrue(n0.is_enemy(n4))
        self.assertFalse(n0.is_enemy(n1))
        self.assertFalse(n0.is_enemy(n5))
        self.assertFalse(n0.is_enemy(n0))

    def test_03_enemy_nations_count(self):
        """Every nation has exactly 2 allies and 3 enemies."""
        for n in NATIONS:
            enemies = n.enemy_nations(NATIONS)
            allies = [other for other in NATIONS if n.is_ally(other)]
            self.assertEqual(len(enemies), 3)
            self.assertEqual(len(allies), 2)

    # -----------------------------------------------------------------------
    # 2. Board Generation & Starting Setup
    # -----------------------------------------------------------------------

    def test_04_board_initial_tile_count(self):
        """Hex board has exactly 37 hex tiles."""
        self.assertEqual(len(self.grid.tiles), 37)

    def test_05_board_initial_units_count(self):
        """Initial map contains 6 sovereigns, 6 champions, and 18 armies (3 per nation)."""
        sov_count = sum(len(sl) for sl in self.grid.sovereigns.values())
        champ_count = sum(len(cl) for cl in self.grid.champions.values())
        army_count = sum(len(al) for al in self.grid.armies.values())

        self.assertEqual(sov_count, 6)
        self.assertEqual(champ_count, 6)
        self.assertEqual(army_count, 18)

    def test_06_sovereign_champion_co_location(self):
        """Each sovereign and champion start co-located at their nation's corner hex."""
        for nation_idx, corner in enumerate(MapGrid.NATION_CORNERS):
            sovs = self.grid.sovereigns.get(corner, [])
            champs = self.grid.champions.get(corner, [])
            self.assertEqual(len(sovs), 1)
            self.assertEqual(len(champs), 1)
            self.assertEqual(sovs[0].nation.ring_index, nation_idx)
            self.assertEqual(champs[0].nation.ring_index, nation_idx)

    # -----------------------------------------------------------------------
    # 3. Player Cooldown Mechanics
    # -----------------------------------------------------------------------

    def test_07_player_cooldown_fifo(self):
        """Player cooldown holds at most the 2 most recently moved nations (FIFO)."""
        player = Player(NATIONS[0])
        self.assertEqual(player.cooldown, [])

        player.add_to_cooldown(NATIONS[1])
        self.assertEqual(player.cooldown, [1])

        player.add_to_cooldown(NATIONS[2])
        self.assertEqual(player.cooldown, [2, 1])

        player.add_to_cooldown(NATIONS[3])
        self.assertEqual(player.cooldown, [3, 2])

    def test_08_nation_on_cooldown_check(self):
        """nation_on_cooldown returns True only for nations currently in the cooldown list."""
        player = Player(NATIONS[0])
        player.add_to_cooldown(NATIONS[1])
        player.add_to_cooldown(NATIONS[2])

        self.assertTrue(player.nation_on_cooldown(NATIONS[1]))
        self.assertTrue(player.nation_on_cooldown(NATIONS[2]))
        self.assertFalse(player.nation_on_cooldown(NATIONS[0]))
        self.assertFalse(player.nation_on_cooldown(NATIONS[3]))

    # -----------------------------------------------------------------------
    # 4. Support System
    # -----------------------------------------------------------------------

    def test_09_unit_support_alone_vs_grouped(self):
        """An isolated unit is unsupported; 2 units of the same nation in the same hex are supported."""
        grid = MapGrid()
        grid.generate_map()
        # Clear units for a clean test hex at (0,0)
        grid.armies.clear()
        grid.champions.clear()
        grid.sovereigns.clear()

        army1 = Army(NATIONS[0], 0, 0)
        grid.add_army(army1)
        self.assertFalse(grid.is_supported(army1))

        # Add a champion of the same nation to (0,0)
        champ = Champion(NATIONS[0], 0, 0)
        grid.add_champion(champ)
        self.assertTrue(grid.is_supported(army1))
        self.assertTrue(grid.is_supported(champ))

    def test_10_unit_support_allied_nations(self):
        """Units of allied nations in the same hex provide mutual support."""
        grid = MapGrid()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Nations 0 (Yellow) and 1 (Green) are allies
        army_yellow = Army(NATIONS[0], 0, 0)
        champ_green = Champion(NATIONS[1], 0, 0)
        grid.add_army(army_yellow)
        grid.add_champion(champ_green)

        self.assertTrue(grid.is_supported(army_yellow))
        self.assertTrue(grid.is_supported(champ_green))

    # -----------------------------------------------------------------------
    # 5. Movement Rules
    # -----------------------------------------------------------------------

    def test_11_valid_move_army(self):
        """Army can move to an adjacent empty hex, but cannot enter a hex with an army or enemy."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        army_a = Army(NATIONS[0], 0, 0)
        grid.add_army(army_a)

        # (1,0) is an adjacent empty hex on the board, so it's a valid move
        self.assertIn((1, 0), grid.get_valid_moves(army_a))

        # Put an allied army at (1,0) -> only 1 army per hex allowed
        army_b = Army(NATIONS[1], 1, 0)
        grid.add_army(army_b)
        self.assertNotIn((1, 0), grid.get_valid_moves(army_a))

        # Put an enemy sovereign at (0,1) -> non-attack moves cannot enter enemy hexes
        sov_enemy = Sovereign(NATIONS[3], 0, 1)
        grid.add_sovereign(sov_enemy)
        self.assertNotIn((0, 1), grid.get_valid_moves(army_a))

    def test_12_valid_move_champion_can_stack_with_army(self):
        """Champion can move into a hex containing a friendly army."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        champ = Champion(NATIONS[0], 0, 0)
        grid.add_champion(champ)
        friendly_army = Army(NATIONS[0], 1, 0)
        grid.add_army(friendly_army)

        self.assertIn((1, 0), grid.get_valid_moves(champ))

    # -----------------------------------------------------------------------
    # 6. Combat: Army vs Army
    # -----------------------------------------------------------------------

    def test_13_unsupported_army_vs_unsupported_army(self):
        """Unsupported army attacking unsupported enemy army: both destroyed."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_army = Army(NATIONS[0], 0, 0)
        def_army = Army(NATIONS[3], 1, 0) # Nations 0 & 3 are enemies
        grid.add_army(atk_army)
        grid.add_army(def_army)

        success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
        self.assertTrue(success)
        self.assertIn(atk_army, destroyed)
        self.assertIn(def_army, destroyed)
        self.assertEqual(len(grid.armies.get((0,0), [])), 0)
        self.assertEqual(len(grid.armies.get((1,0), [])), 0)

    def test_14_supported_army_vs_unsupported_army(self):
        """Supported army attacking unsupported enemy army: enemy destroyed, attacker advances."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_army = Army(NATIONS[0], 0, 0)
        atk_champ = Champion(NATIONS[0], 0, 0) # provides support
        def_army = Army(NATIONS[3], 1, 0)
        grid.add_army(atk_army)
        grid.add_champion(atk_champ)
        grid.add_army(def_army)

        success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
        self.assertTrue(success)
        self.assertIn(def_army, destroyed)
        self.assertNotIn(atk_army, destroyed)
        # Attacking army should have advanced to (1,0)
        self.assertEqual(atk_army.hex_location, (1, 0))

    def test_15_unsupported_army_cannot_attack_supported_army(self):
        """Unsupported army attacking a supported army is an illegal attack."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_army = Army(NATIONS[0], 0, 0)
        def_army = Army(NATIONS[3], 1, 0)
        def_champ = Champion(NATIONS[3], 1, 0)
        grid.add_army(atk_army)
        grid.add_army(def_army)
        grid.add_champion(def_champ)

        success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
        self.assertFalse(success)
        self.assertEqual(destroyed, [])

    def test_16_army_cannot_attack_champion(self):
        """Armies are not allowed to attack champions."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_army = Army(NATIONS[0], 0, 0)
        enemy_champ = Champion(NATIONS[3], 1, 0)
        grid.add_army(atk_army)
        grid.add_champion(enemy_champ)

        success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
        self.assertFalse(success)

    # -----------------------------------------------------------------------
    # 7. Combat: Champion vs Units
    # -----------------------------------------------------------------------

    def test_17_champion_attacks_unsupported_army(self):
        """Unsupported champion attacking unsupported enemy army destroys army."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        champ = Champion(NATIONS[0], 0, 0)
        enemy_army = Army(NATIONS[3], 1, 0)
        grid.add_champion(champ)
        grid.add_army(enemy_army)

        success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
        self.assertTrue(success)
        self.assertIn(enemy_army, destroyed)
        self.assertNotIn(champ, destroyed)

    def test_18_champion_attacks_sovereign_shielded_by_army(self):
        """Supported champion attacking sovereign supported by army destroys army, sovereign survives."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_champ = Champion(NATIONS[0], 0, 0)
        atk_army = Army(NATIONS[0], 0, 0) # supports atk_champ
        grid.add_champion(atk_champ)
        grid.add_army(atk_army)

        def_sov = Sovereign(NATIONS[3], 1, 0)
        def_army = Army(NATIONS[3], 1, 0) # shields def_sov
        grid.add_sovereign(def_sov)
        grid.add_army(def_army)

        success, msg, destroyed = grid.resolve_attack(atk_champ, 1, 0)
        self.assertTrue(success)
        self.assertIn(def_army, destroyed)
        self.assertNotIn(def_sov, destroyed)
        self.assertIn(def_sov, grid.sovereigns.get((1, 0), []))

    # -----------------------------------------------------------------------
    # 8. Trapped Sovereign & Sovereign Combat
    # -----------------------------------------------------------------------

    def test_19_trapped_sovereign_detection_and_army_kill(self):
        """Unsupported sovereign with opposite enemy neighbours is trapped and can be killed by an army."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Target sovereign at (0,0)
        sov = Sovereign(NATIONS[0], 0, 0)
        grid.add_sovereign(sov)

        # Opposite directions: (0,-1) and (0,1)
        enemy_top = Army(NATIONS[3], 0, -1)
        enemy_bot = Army(NATIONS[3], 0, 1)
        grid.add_army(enemy_top)
        grid.add_army(enemy_bot)

        self.assertTrue(grid.is_trapped(sov))

        # Army can attack trapped, unsupported sovereign
        success, msg, destroyed = grid.resolve_attack(enemy_top, 0, 0)
        self.assertTrue(success)
        self.assertIn(sov, destroyed)
        self.assertEqual(enemy_top.hex_location, (0, 0))

    def test_20_sovereign_cannot_attack(self):
        """Sovereigns cannot initiate attacks."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        sov = Sovereign(NATIONS[0], 0, 0)
        enemy = Army(NATIONS[3], 1, 0)
        grid.add_sovereign(sov)
        grid.add_army(enemy)

        success, msg, destroyed = grid.resolve_attack(sov, 1, 0)
        self.assertFalse(success)

    # -----------------------------------------------------------------------
    # 9. Recruit & Promote
    # -----------------------------------------------------------------------

    def test_21_recruit_army_mechanics(self):
        """Recruit adds an army on an available home hex if under the 3-army limit."""
        grid = MapGrid()
        grid.generate_map()
        # Nation 0 starts with 3 armies; clear one to test recruiting
        armies_n0 = grid.get_all_nation_units(NATIONS[0])
        armies_only = [u for u in armies_n0 if isinstance(u, Army)]
        grid.remove_army(armies_only[0])

        recruit_hexes = grid.get_recruit_hexes(NATIONS[0])
        self.assertTrue(len(recruit_hexes) >= 1)

        target_hex = recruit_hexes[0]
        new_army = grid.recruit_army(NATIONS[0], *target_hex)
        self.assertEqual(new_army.nation.ring_index, 0)
        self.assertEqual(new_army.hex_location, target_hex)
        # Now back at 3 armies, recruit_hexes should be empty
        self.assertEqual(grid.get_recruit_hexes(NATIONS[0]), [])

    def test_22_promote_champion_mechanics(self):
        """Promote replaces an army on a home hex with a champion."""
        grid = MapGrid()
        grid.generate_map()
        # Remove starting champion of Nation 0 so promotion is possible
        champs = [u for u in grid.get_all_nation_units(NATIONS[0]) if isinstance(u, Champion)]
        grid.remove_champion(champs[0])

        promo_hexes = grid.get_promote_hexes(NATIONS[0])
        self.assertTrue(len(promo_hexes) >= 1)

        promo_hex = promo_hexes[0]
        army_to_promote = grid.armies[promo_hex][0]
        new_champ = grid.promote_to_champion(army_to_promote)

        self.assertEqual(new_champ.nation.ring_index, 0)
        self.assertEqual(new_champ.hex_location, promo_hex)
        self.assertEqual(grid.get_promote_hexes(NATIONS[0]), [])

    # -----------------------------------------------------------------------
    # 10. Win, Loss, and Ghost Nations
    # -----------------------------------------------------------------------

    def test_23_ghost_nation_and_win_loss_conditions(self):
        """Loss of sovereign marks nation as ghost; 2 dead enemies trigger win; own sovereign dead triggers loss."""
        player = Player(NATIONS[0]) # Yellow's enemies are 2, 3, 4
        enemies = player.get_enemies(NATIONS)

        # Initially no ghosts, no win, no loss
        self.grid.check_ghost_nations(NATIONS)
        self.assertFalse(self.grid.check_win_condition(player, NATIONS))
        self.assertFalse(self.grid.check_loss_condition(player))

        # Kill 1 enemy sovereign
        sov_enemy1 = [s for sl in self.grid.sovereigns.values() for s in sl if s.nation == enemies[0]][0]
        self.grid.remove_sovereign(sov_enemy1)
        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(enemies[0].is_ghost)
        self.assertFalse(self.grid.check_win_condition(player, NATIONS))

        # Kill 2nd enemy sovereign -> Win condition met
        sov_enemy2 = [s for sl in self.grid.sovereigns.values() for s in sl if s.nation == enemies[1]][0]
        self.grid.remove_sovereign(sov_enemy2)
        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(self.grid.check_win_condition(player, NATIONS))

        # Kill player's own sovereign -> Loss condition met
        sov_own = [s for sl in self.grid.sovereigns.values() for s in sl if s.nation == NATIONS[0]][0]
        self.grid.remove_sovereign(sov_own)
        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(self.grid.check_loss_condition(player))

    # -----------------------------------------------------------------------
    # 11. Bot Memory and Scoring
    # -----------------------------------------------------------------------

    def test_24_bot_memory_scoring_and_guessing(self):
        """BotMemory adds points, propagates half to allies, and guesses the correct faction excluding bot's color."""
        mem = BotMemory(debug=False)
        # Adding 4 points to Yellow (0) gives +4 to Yellow and +2 to allies Green (1) and Crimson (5)
        mem.add_score(0, 4)
        self.assertEqual(mem.nation_scores[0], 4)
        self.assertEqual(mem.nation_scores[1], 2)
        self.assertEqual(mem.nation_scores[5], 2)

        # Bot is Green (1) -> guess should exclude 1 and pick Yellow (0)
        guess = mem.guess_faction(NATIONS, exclude_ring_indices=(1,))
        self.assertEqual(guess.ring_index, 0)

    def test_25_bot_does_not_hand_human_victory(self):
        """When human is 1 kill away from winning, bot completely suppresses attacks on remaining human targets."""
        from bot import _adaptive_sovereign_adjustments
        grid = MapGrid()
        grid.generate_map()

        # Human suspected = Cobalt (3), enemies = Yellow(0), Green(1), Crimson(5)
        # Bot = Sky Blue (2), enemies = Cobalt(3), Magenta(4), Crimson(5)
        # Green (1) is already a ghost -> human has 1 kill (1 away from winning)
        NATIONS[1].is_ghost = True

        # Candidate action: attack Yellow (0) sovereign with Sky Blue (2) army (enemy of Yellow)
        yellow_sov = [s for sl in grid.sovereigns.values() for s in sl if s.nation.ring_index == 0][0]
        attacker = Army(NATIONS[2], 0, -2) # Sky Blue army
        actions = [(1020.0, 'attack', attacker, yellow_sov.hex_location)]

        # Adjust actions with suspected human = 3
        adjusted = _adaptive_sovereign_adjustments(grid, actions, bot_ri=2, suspected_human_ri=3,
                                                   turn_number=30, nation_list=NATIONS)
        self.assertEqual(len(adjusted), 1)
        # Score must be <= -1000 (disqualified) so bot never executes it
        self.assertTrue(adjusted[0][0] < -1000)

    # -----------------------------------------------------------------------
    # 12. Advance after combat
    # -----------------------------------------------------------------------

    def test_26_champion_advances_after_killing_army(self):
        """Champion advances into hex after destroying an enemy army (hex clear)."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        champ = Champion(NATIONS[0], 0, 0)
        enemy_army = Army(NATIONS[3], 1, 0)
        grid.add_champion(champ)
        grid.add_army(enemy_army)

        success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
        self.assertTrue(success)
        self.assertIn(enemy_army, destroyed)
        self.assertEqual(champ.hex_location, (1, 0))

    def test_27_champion_advances_after_killing_champion(self):
        """Supported champion advances after destroying unsupported enemy champion."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_champ = Champion(NATIONS[0], 0, 0)
        support = Army(NATIONS[0], 0, 0)  # provides support
        enemy_champ = Champion(NATIONS[3], 1, 0)
        grid.add_champion(atk_champ)
        grid.add_army(support)
        grid.add_champion(enemy_champ)

        success, msg, destroyed = grid.resolve_attack(atk_champ, 1, 0)
        self.assertTrue(success)
        self.assertIn(enemy_champ, destroyed)
        self.assertEqual(atk_champ.hex_location, (1, 0))

    def test_28_champion_advances_after_killing_sovereign(self):
        """Champion advances after destroying an unsupported enemy sovereign."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        champ = Champion(NATIONS[0], 0, 0)
        enemy_sov = Sovereign(NATIONS[3], 1, 0)
        grid.add_champion(champ)
        grid.add_sovereign(enemy_sov)

        success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
        self.assertTrue(success)
        self.assertIn(enemy_sov, destroyed)
        self.assertEqual(champ.hex_location, (1, 0))

    def test_29_champion_does_not_advance_when_enemies_remain(self):
        """Champion kills one enemy but does NOT advance because another enemy remains."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        champ = Champion(NATIONS[0], 0, 0)
        support = Army(NATIONS[0], 0, 0)      # supports champion
        enemy_army1 = Army(NATIONS[3], 1, 0)
        enemy_army2 = Army(NATIONS[3], 1, 0)   # second enemy in same hex
        grid.add_champion(champ)
        grid.add_army(support)
        grid.add_army(enemy_army1)
        grid.add_army(enemy_army2)

        success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
        self.assertTrue(success)
        # Champion should stay at origin because enemies remain
        self.assertEqual(champ.hex_location, (0, 0))

    def test_30_army_does_not_advance_when_army_present(self):
        """Supported army kills enemy army but does NOT advance because a friendly army is already there."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_army = Army(NATIONS[0], 0, 0)
        support = Champion(NATIONS[0], 0, 0)  # provides support
        friendly_army = Army(NATIONS[1], 1, 0)  # allied army already in target hex
        enemy_army = Army(NATIONS[3], 1, 0)
        grid.add_army(atk_army)
        grid.add_champion(support)
        grid.add_army(friendly_army)
        grid.add_army(enemy_army)

        success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
        self.assertTrue(success)
        self.assertIn(enemy_army, destroyed)
        # Army should NOT advance because another army is in the target hex
        self.assertEqual(atk_army.hex_location, (0, 0))

    def test_31_army_advances_into_clear_hex(self):
        """Supported army kills lone enemy army and advances into the now-empty hex."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        atk_army = Army(NATIONS[0], 0, 0)
        support = Champion(NATIONS[0], 0, 0)  # provides support
        enemy_army = Army(NATIONS[3], 1, 0)
        grid.add_army(atk_army)
        grid.add_champion(support)
        grid.add_army(enemy_army)

        success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
        self.assertTrue(success)
        self.assertIn(enemy_army, destroyed)
        self.assertEqual(atk_army.hex_location, (1, 0))

    # -----------------------------------------------------------------------
    # 13. Move serialization round-trip
    # -----------------------------------------------------------------------

    def test_32_serialize_apply_move(self):
        """Serialize a move action and apply it — unit should end up at target hex."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        army = Army(NATIONS[0], 0, 0)
        grid.add_army(army)

        # Serialize
        move_data = serialize_move('move', 0, unit_type='army',
                                  from_hex=(0, 0), to_hex=(1, 0))
        self.assertEqual(move_data['type'], 'move')
        self.assertEqual(move_data['nation_ri'], 0)
        self.assertEqual(move_data['from'], [0, 0])
        self.assertEqual(move_data['to'], [1, 0])

        # Apply
        success, msg, moved_nation, destroyed = apply_serialized_move(
            grid, move_data, NATIONS)
        self.assertTrue(success)
        self.assertEqual(moved_nation.ring_index, 0)
        self.assertEqual(army.hex_location, (1, 0))

    def test_33_serialize_apply_attack(self):
        """Serialize an attack and apply it — enemy should be destroyed."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        champ = Champion(NATIONS[0], 0, 0)
        enemy = Army(NATIONS[3], 1, 0)
        grid.add_champion(champ)
        grid.add_army(enemy)

        move_data = serialize_move('attack', 0, unit_type='champion',
                                  from_hex=(0, 0), to_hex=(1, 0))
        success, msg, moved_nation, destroyed = apply_serialized_move(
            grid, move_data, NATIONS)
        self.assertTrue(success)
        self.assertIn(enemy, destroyed)

    def test_34_serialize_apply_recruit(self):
        """Serialize a recruit action and apply it — new army should appear."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Place a sovereign so the nation isn't a ghost
        sov = Sovereign(NATIONS[0], 0, 0)
        grid.add_sovereign(sov)

        move_data = serialize_move('recruit', 0, to_hex=(1, 0))
        success, msg, moved_nation, destroyed = apply_serialized_move(
            grid, move_data, NATIONS)
        self.assertTrue(success)
        self.assertEqual(moved_nation.ring_index, 0)
        armies_at = grid.armies.get((1, 0), [])
        self.assertEqual(len(armies_at), 1)
        self.assertEqual(armies_at[0].nation.ring_index, 0)


if __name__ == '__main__':
    unittest.main()

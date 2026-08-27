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
from knights import Knight
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

    # -----------------------------------------------------------------------
    # 14. Bot sovereign protection — never kill own secret nation's sovereign
    # -----------------------------------------------------------------------

    def test_35_score_attack_forbids_allied_sovereign(self):
        """_score_attack returns -9999 when targeting the bot's allied sovereign."""
        from bot import _score_attack
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Bot's secret nation is NATIONS[0] (Yellow).
        # Allied nations: 0 (Yellow), 1 (Green), 5 (Crimson).
        # Enemy nations:  2 (Sky Blue), 3 (Cobalt), 4 (Magenta).
        bot_secret = NATIONS[0]
        allied_ring_set = {n.ring_index for n in NATIONS if not bot_secret.is_enemy(n)}
        enemy_ring_set  = {n.ring_index for n in bot_secret.enemy_nations(NATIONS)}

        # Place an enemy champion (Nation 3, Cobalt) adjacent to allied sovereign (Nation 1, Green)
        attacker = Champion(NATIONS[3], 0, 0)
        allied_sov = Sovereign(NATIONS[1], 1, 0)
        grid.add_champion(attacker)
        grid.add_sovereign(allied_sov)

        # Nation 3 IS enemy of Nation 1 per diplomacy, so the attack is "legal"
        self.assertTrue(NATIONS[3].is_enemy(NATIONS[1]))

        score = _score_attack(grid, attacker, 1, 0, enemy_ring_set,
                              allied_ring_set=allied_ring_set)
        self.assertEqual(score, -9999.0,
            "Attack on allied sovereign must be scored -9999")

    def test_36_score_attack_allows_enemy_sovereign(self):
        """_score_attack scores positively when targeting an enemy sovereign."""
        from bot import _score_attack
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        bot_secret = NATIONS[0]
        allied_ring_set = {n.ring_index for n in NATIONS if not bot_secret.is_enemy(n)}
        enemy_ring_set  = {n.ring_index for n in bot_secret.enemy_nations(NATIONS)}

        # Place an allied champion (Nation 1, Green) adjacent to enemy sovereign (Nation 3, Cobalt)
        attacker = Champion(NATIONS[1], 0, 0)
        enemy_sov = Sovereign(NATIONS[3], 1, 0)
        grid.add_champion(attacker)
        grid.add_sovereign(enemy_sov)

        self.assertTrue(NATIONS[1].is_enemy(NATIONS[3]))

        score = _score_attack(grid, attacker, 1, 0, enemy_ring_set,
                              allied_ring_set=allied_ring_set)
        self.assertGreater(score, 0,
            "Attack on enemy sovereign must score positively")

    def test_37_compute_bot_action_never_targets_allied_sovereign(self):
        """compute_bot_action must never return an attack on an allied sovereign."""
        from bot import compute_bot_action
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Bot is Nation 0 (Yellow). Allies: 0, 1, 5.
        bot_player = Player(secret_nation=NATIONS[0], is_bot=True)
        allied_ring_set = {n.ring_index for n in NATIONS if not NATIONS[0].is_enemy(n)}

        # Place all 6 sovereigns in their home hexes
        for nation in NATIONS:
            home = grid.NATION_HEXES[nation.ring_index][0]
            grid.add_sovereign(Sovereign(nation, *home))

        # Place a champion from Nation 3 (enemy of Nation 1) next to Nation 1's sovereign
        # so there's a "legal" attack available
        n1_home = grid.NATION_HEXES[1][0]
        neighbors = grid.get_neighbors(*n1_home)
        if neighbors:
            adj = neighbors[0]
            grid.add_champion(Champion(NATIONS[3], *adj))

        # Run compute_bot_action many times to check random path too
        for i in range(50):
            action = compute_bot_action(
                grid, bot_player, None, NATIONS, turn_number=1)
            if action is None:
                continue
            # action format: (score, atype, *payload, path_label)
            score, atype = action[0], action[1]
            if atype == 'attack':
                unit, coord = action[2], action[3]
                tq, tr = coord
                # Check no allied sovereign is at the target hex
                for sov in grid.sovereigns.get((tq, tr), []):
                    if sov.nation.ring_index in allied_ring_set:
                        self.fail(
                            f"Iteration {i}: Bot chose to attack allied sovereign "
                            f"{sov.nation.color_name} at {coord}")

    def test_38_bot_never_attacks_own_secret_sovereign(self):
        """Bot must never attack a sovereign of its own secret nation specifically."""
        from bot import _score_attack
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Bot's secret nation is NATIONS[2] (Sky Blue).
        # Enemies of Sky Blue: 5 (Crimson), 0 (Yellow), 1 (Green)
        bot_secret = NATIONS[2]
        allied_ring_set = {n.ring_index for n in NATIONS if not bot_secret.is_enemy(n)}
        enemy_ring_set  = {n.ring_index for n in bot_secret.enemy_nations(NATIONS)}

        # Nation 5 (Crimson) IS enemy of Nation 2 (Sky Blue) per the ring
        self.assertTrue(NATIONS[5].is_enemy(NATIONS[2]))

        # Place Nation 5's champion attacking Nation 2's (bot's OWN) sovereign
        attacker = Champion(NATIONS[5], 0, 0)
        own_sov  = Sovereign(NATIONS[2], 1, 0)
        grid.add_champion(attacker)
        grid.add_sovereign(own_sov)

        score = _score_attack(grid, attacker, 1, 0, enemy_ring_set,
                              allied_ring_set=allied_ring_set)
        self.assertEqual(score, -9999.0,
            "Attack on bot's OWN secret sovereign must be -9999")


class TestSovereignEnemyMoveRestriction(unittest.TestCase):
    """Tests for the rule: enemy players can only move a sovereign to a hex where it would be supported."""

    def setUp(self):
        for nation in NATIONS:
            nation.is_ghost = False
        self.grid = MapGrid()
        self.grid.generate_map()
        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

    def test_enemy_cannot_move_sovereign_to_unsupported_hex(self):
        """An enemy player cannot move a sovereign to an empty/unsupported hex."""
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)

        # Cobalt (3) is enemy of Yellow (0)
        mover_secret = NATIONS[3]
        self.assertTrue(mover_secret.is_enemy(NATIONS[0]))

        # With no friendly/allied pieces around, enemy cannot move the sovereign anywhere
        valid = self.grid.get_valid_moves(sov, mover_secret_nation=mover_secret)
        self.assertEqual(len(valid), 0,
            "Enemy should not be able to move a sovereign to any hex where it would be unsupported")

    def test_enemy_can_move_sovereign_to_supported_hex(self):
        """An enemy player CAN move a sovereign to a hex where an allied/friendly piece is present."""
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)

        # Place a Yellow army at neighbor (0, -1) and a Green (ally of Yellow) champion at (1, -2)
        army = Army(NATIONS[0], 0, -1)
        champ = Champion(NATIONS[1], 1, -2)
        self.grid.add_army(army)
        self.grid.add_champion(champ)

        mover_secret = NATIONS[3]  # Enemy
        valid = self.grid.get_valid_moves(sov, mover_secret_nation=mover_secret)

        self.assertIn((0, -1), valid, "Enemy should be able to move sovereign to hex with same-color army")
        self.assertIn((1, -2), valid, "Enemy should be able to move sovereign to hex with allied champion")

    def test_ally_can_move_sovereign_to_unsupported_hex(self):
        """The sovereign's owner or ally CAN move the sovereign to an unsupported hex."""
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)

        mover_secret = NATIONS[0]  # Owner (Yellow)
        valid = self.grid.get_valid_moves(sov, mover_secret_nation=mover_secret)
        self.assertTrue(len(valid) > 0,
            "Owner should be able to move sovereign freely to empty neighboring hexes")


class TestHexControlAndMuster(unittest.TestCase):
    """Tests for the Hex Control territory system, dynamic army caps, and updated muster rules."""

    def setUp(self):
        for nation in NATIONS:
            nation.is_ghost = False
        self.grid = MapGrid()
        self.grid.generate_map()

    def test_initial_hex_control_setup(self):
        """24 homeland hexes are owned by their respective nations; 13 center hexes start neutral."""
        owned_count = 0
        neutral_count = 0
        for coord, owner_ri in self.grid.tile_control.items():
            if owner_ri is None:
                neutral_count += 1
            else:
                owned_count += 1
                self.assertIn(owner_ri, range(6))

        self.assertEqual(owned_count, 24, "24 homeland hexes must start owned")
        self.assertEqual(neutral_count, 13, "13 center hexes must start neutral (None)")
        for n in NATIONS:
            self.assertEqual(self.grid.get_controlled_hex_count(n), 4, "Each nation starts with 4 hexes")
            self.assertEqual(self.grid.get_max_army_cap(n), 3, "4 hexes = baseline 3 army cap")

    def test_neutral_hex_claimed_on_entry(self):
        """When any unit enters an unowned neutral hex, it claims control for its nation."""
        self.assertIsNone(self.grid.tile_control.get((0, 0)))
        army = Army(NATIONS[0], 0, -1)
        self.grid.add_army(army)
        self.grid.apply_move(army, 0, 0)
        self.assertEqual(self.grid.tile_control.get((0, 0)), 0,
            "Entering neutral hex should claim it for mover's nation")

    def test_allied_unit_does_not_steal_control(self):
        """An allied unit moving into your territory does NOT seize control (first come keeps it)."""
        # Yellow (0) owns (0, -2)
        self.assertEqual(self.grid.tile_control.get((0, -2)), 0)
        # Clear units from destination (0, -2) so it's a vacant move destination
        self.grid.armies.pop((0, -2), None)

        # Green (1) is ally of Yellow (0)
        green_army = Army(NATIONS[1], 0, -1)
        self.grid.add_army(green_army)
        # Move green army to (0, -2)
        success, msg = self.grid.apply_move(green_army, 0, -2)
        self.assertTrue(success, f"Move failed: {msg}")
        self.assertEqual(self.grid.tile_control.get((0, -2)), 0,
            "Allied unit should not seize territory from an ally")

    def test_enemy_unit_seizes_control(self):
        """An enemy Army or Champion moving into your territory SEIZES control."""
        # Yellow (0) owns (0, -2)
        self.assertEqual(self.grid.tile_control.get((0, -2)), 0)
        # Clear units from destination (0, -2) so it's a vacant move destination
        self.grid.armies.pop((0, -2), None)

        # Cobalt (3) is enemy of Yellow (0)
        cobalt_army = Army(NATIONS[3], 0, -1)
        self.grid.add_army(cobalt_army)
        success, msg = self.grid.apply_move(cobalt_army, 0, -2)
        self.assertTrue(success, f"Move failed: {msg}")
        self.assertEqual(self.grid.tile_control.get((0, -2)), 3,
            "Enemy army must seize territory upon entering")

    def test_army_cap_progression(self):
        """Cap is 3 base (4 hexes), and increases by +1 for every 3 additional hexes."""
        n0 = NATIONS[0]
        self.assertEqual(self.grid.get_max_army_cap(n0), 3)

        # Give n0 2 extra hexes (total 6) -> cap still 3
        self.grid.tile_control[(0, 0)] = 0
        self.grid.tile_control[(0, 1)] = 0
        self.assertEqual(self.grid.get_controlled_hex_count(n0), 6)
        self.assertEqual(self.grid.get_max_army_cap(n0), 3)

        # Give 1 more hex (total 7, +3 over base) -> cap becomes 4
        self.grid.tile_control[(1, 0)] = 0
        self.assertEqual(self.grid.get_controlled_hex_count(n0), 7)
        self.assertEqual(self.grid.get_max_army_cap(n0), 4)

        # Total 10 hexes (+6 over base) -> cap becomes 5
        self.grid.tile_control[(1, 1)] = 0
        self.grid.tile_control[(-1, 0)] = 0
        self.grid.tile_control[(-1, 1)] = 0
        self.assertEqual(self.grid.get_controlled_hex_count(n0), 10)
        self.assertEqual(self.grid.get_max_army_cap(n0), 5)

    def test_muster_hex_requires_no_enemy_adjacency(self):
        """Muster is only legal on controlled hexes that are NOT adjacent to any enemy unit."""
        n0 = NATIONS[0]
        # Remove an army so can_muster_army is True
        armies = [u for u in self.grid.get_all_nation_units(n0) if isinstance(u, Army)]
        self.grid.remove_army(armies[0])

        valid_muster = self.grid.get_valid_muster_hexes(n0)
        self.assertTrue(len(valid_muster) > 0)

        # Place an enemy adjacent to one of the valid muster hexes
        target_hex = valid_muster[0]
        nbrs = self.grid.get_neighbors(*target_hex)
        enemy_army = Army(NATIONS[3], *nbrs[0])
        self.grid.add_army(enemy_army)

        new_valid_muster = self.grid.get_valid_muster_hexes(n0)
        self.assertNotIn(target_hex, new_valid_muster,
            "Hex adjacent to an enemy unit must be blocked from mustering")

    def test_sovereign_cannot_enter_enemy_territory(self):
        """A Sovereign cannot move into territory controlled by an enemy nation."""
        # Yellow (0) sovereign at (0, -2)
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)

        # Set neighbor (0, -1) as owned by Cobalt (3, enemy of Yellow)
        self.grid.tile_control[(0, -1)] = 3
        # Set neighbor (1, -2) as neutral (None)
        self.grid.tile_control[(1, -2)] = None

        valid = self.grid.get_valid_moves(sov, mover_secret_nation=NATIONS[0])
        self.assertNotIn((0, -1), valid, "Sovereign must NOT be allowed to enter enemy territory")
        self.assertIn((1, -2), valid, "Sovereign should be allowed to enter neutral territory")


class TestPositionalEvaluator(unittest.TestCase):
    """Tests for the positional board evaluator."""

    def setUp(self):
        for nation in NATIONS:
            nation.is_ghost = False
        self.grid = MapGrid()
        self.grid.generate_map()
        self.nation_list = list(NATIONS)

    def tearDown(self):
        for nation in NATIONS:
            nation.is_ghost = False

    def test_ghost_enemy_boosts_score(self):
        """Killing an enemy sovereign (ghost nation) should raise our score."""
        from evaluator import evaluate_position
        secret = self.nation_list[0]  # nation 0
        enemies = secret.enemy_nations(self.nation_list)

        score_before = evaluate_position(self.grid, secret, self.nation_list)

        # Mark one enemy as ghost
        enemies[0].is_ghost = True
        score_after = evaluate_position(self.grid, secret, self.nation_list)

        self.assertGreater(score_after, score_before,
            "Score should increase when an enemy sovereign is killed (ghost)")

    def test_own_sov_dead_catastrophic(self):
        """If our own sovereign is dead, score should be extremely negative."""
        from evaluator import evaluate_position
        secret = self.nation_list[0]

        score_alive = evaluate_position(self.grid, secret, self.nation_list)

        secret.is_ghost = True
        score_dead = evaluate_position(self.grid, secret, self.nation_list)

        self.assertLess(score_dead, -5000,
            "Score should be catastrophically negative when own sovereign is dead")
        self.assertLess(score_dead, score_alive,
            "Dead sovereign score must be lower than alive score")

    def test_trapped_unsupported_enemy_scores_higher(self):
        """An enemy sovereign that is trapped+unsupported should yield a higher
        position score than one that is safe."""
        from evaluator import evaluate_position

        # Create a minimal grid with a controllable scenario
        grid = MapGrid()
        grid.generate_map()
        secret = self.nation_list[0]
        enemies = secret.enemy_nations(self.nation_list)
        target_enemy = enemies[0]

        # Baseline score
        score_baseline = evaluate_position(grid, secret, self.nation_list)

        # Now create a scenario where the enemy sovereign is trapped:
        # Remove the enemy sovereign, place it somewhere surrounded by enemies
        # Remove all enemy sovs first
        for coord in list(grid.sovereigns.keys()):
            grid.sovereigns[coord] = [
                s for s in grid.sovereigns[coord]
                if s.nation.ring_index != target_enemy.ring_index
            ]
            if not grid.sovereigns[coord]:
                del grid.sovereigns[coord]

        # Place enemy sovereign at a hex and surround with allied armies
        center = (0, 0)
        enemy_sov = Sovereign(target_enemy, center[0], center[1])
        grid.sovereigns.setdefault(center, []).append(enemy_sov)

        neighbors = grid.get_neighbors(center[0], center[1])
        # Place allied armies at opposing neighbors to create a trap
        allied_nation = self.nation_list[0]
        for i in [0, 3]:  # opposite neighbors
            nq, nr = neighbors[i]
            # Clear any existing armies
            grid.armies.pop((nq, nr), None)
            trap_army = Army(allied_nation, nq, nr)
            grid.armies.setdefault((nq, nr), []).append(trap_army)

        score_trapped = evaluate_position(grid, secret, self.nation_list)
        self.assertGreater(score_trapped, score_baseline,
            "Score should be higher when enemy sovereign is trapped+unsupported")

    def test_material_advantage(self):
        """Having more allied pieces should yield a higher score."""
        from evaluator import evaluate_position

        grid1 = MapGrid()
        grid1.generate_map()
        secret = self.nation_list[0]

        score1 = evaluate_position(grid1, secret, self.nation_list)

        # Add extra allied armies
        grid2 = MapGrid()
        grid2.generate_map()
        allied = [n for n in self.nation_list if not secret.is_enemy(n)]
        bonus_nation = allied[0]
        # Find a free hex and add an army
        for q in range(-2, 3):
            for r in range(-2, 3):
                if (q, r) in grid2.tiles and (q, r) not in grid2.armies:
                    grid2.armies[(q, r)] = [Army(bonus_nation, q, r)]
                    break
            else:
                continue
            break

        score2 = evaluate_position(grid2, secret, self.nation_list)
        self.assertGreater(score2, score1,
            "Score should increase with more allied material")

    def test_perspective_symmetry(self):
        """Evaluating from two opposing factions should give different scores;
        a position good for one should be worse for the other."""
        from evaluator import evaluate_position

        secret_a = self.nation_list[0]
        enemies_of_a = secret_a.enemy_nations(self.nation_list)
        secret_b = enemies_of_a[0]  # pick an enemy

        # Make an enemy of A a ghost — good for A, bad-ish for B
        enemies_of_a[1].is_ghost = True

        score_a = evaluate_position(self.grid, secret_a, self.nation_list)
        score_b = evaluate_position(self.grid, secret_b, self.nation_list)

        # A should benefit more than B from killing B's potential ally/target
        self.assertGreater(score_a, score_b,
            "The player who benefits from the ghost should have a higher score")

    def test_territory_control_evaluation(self):
        """Controlling more territory should increase the positional evaluation score."""
        from evaluator import evaluate_position

        secret = self.nation_list[0]
        score_base = evaluate_position(self.grid, secret, self.nation_list)

        # Flip 3 neutral hexes to Nation 0
        self.grid.tile_control[(0, 0)] = 0
        self.grid.tile_control[(0, 1)] = 0
        self.grid.tile_control[(1, 0)] = 0

        score_expanded = evaluate_position(self.grid, secret, self.nation_list)
        self.assertGreater(score_expanded, score_base,
            "Score should increase when controlling additional hexes")

    def test_territory_move_scoring(self):
        """Moves that claim neutral or enemy territory should receive higher tactical move scores."""
        from bot import _score_move
        n0 = self.nation_list[0]
        army = Army(n0, 0, -1)
        self.grid.add_army(army)

        allied_ris = {0, 1, 5}
        enemy_ris = {2, 3, 4}

        # Move into neutral hex (0, 0)
        self.grid.tile_control[(0, 0)] = None
        score_high_claim = _score_move(self.grid, army, 0, 0, enemy_ris, allied_ris,
                                       weights={'claim_territory': 3.0})
        score_low_claim = _score_move(self.grid, army, 0, 0, enemy_ris, allied_ris,
                                      weights={'claim_territory': 0.0})

        self.assertGreater(score_high_claim, score_low_claim + 50.0,
            "Higher claim_territory weight should yield higher move score when claiming territory")

    def test_custom_eval_weights(self):
        """Custom eval weights passed as dict or from BotConfig should override defaults."""
        from evaluator import evaluate_position
        from evolution import BotConfig

        secret = self.nation_list[0]
        config = BotConfig(ev_allied_army=500.0)
        custom_weights = config.to_evaluator_weights()

        score_default = evaluate_position(self.grid, secret, self.nation_list)
        score_custom = evaluate_position(self.grid, secret, self.nation_list, weights=custom_weights)

        # Because allied armies are present on the board and their weight went from 15.0 to 500.0,
        # the custom score should be significantly higher.
        self.assertGreater(score_custom, score_default + 100.0,
            "Custom evaluator weights should be used in position evaluation")

    def test_describe_bot_generates_narrative(self):
        """describe_bot should output a human-readable profile with archetype and key stats."""
        from evolution import BotConfig, describe_bot

        config = BotConfig(
            lookahead_depth=2,
            lookahead_beam=3,
            hybrid_ratio=0.70,
            w_endanger_enemy_sov=4.0,
            w_protect_sovereign=0.2,
            fitness=75.0
        )
        desc = describe_bot(config, rank=1)
        self.assertIn("BOT #1", desc)
        self.assertIn("Fitness: 75.0", desc)
        self.assertIn("2-Ply Lookahead", desc)
        self.assertIn("70% Positional Board Eval", desc)
        self.assertIn("Offense-First", desc)

    def test_archetype_generation(self):
        """random_config should generate valid configs for all archetype presets."""
        from evolution import BotConfig

        for arch in ['speedster', 'positional', 'hybrid', 'deep', 'wild']:
            c = BotConfig.random_config(archetype=arch)
            self.assertGreaterEqual(c.lookahead_depth, 1)
            self.assertLessEqual(c.lookahead_depth, 4)
            self.assertGreaterEqual(c.hybrid_ratio, 0.0)
            self.assertLessEqual(c.hybrid_ratio, 1.0)
            self.assertGreaterEqual(c.lookahead_beam, 1)
            if c.lookahead_depth >= 4:
                self.assertLessEqual(c.lookahead_beam, 3, "4-ply bots must have max beam of 3")

    def test_hybrid_scoring_execution(self):
        """compute_bot_action with hybrid_ratio should compute legal action."""
        import bot
        from player import Player
        from evolution import BotConfig

        bot_player = Player(self.nation_list[0], is_bot=True, player_id='test_bot')
        config = BotConfig(lookahead_depth=2, lookahead_beam=2, hybrid_ratio=0.5,
                           w_random=0.0, w_deceptive=0.0)

        action = bot.compute_bot_action(
            self.grid, bot_player, global_cooldown_idx=None, nation_list=self.nation_list,
            turn_number=5, suspected_human_ri=self.nation_list[3].ring_index,
            evolved_config=config)

        self.assertIsNotNone(action, "Bot should compute a valid action with hybrid scoring")
        self.assertEqual(action[-1], 'intent')

    def test_4ply_lookahead_execution(self):
        """compute_bot_action with 4-ply lookahead should compute legal action."""
        import bot
        from player import Player
        from evolution import BotConfig

        bot_player = Player(self.nation_list[0], is_bot=True, player_id='test_bot_4ply')
        config = BotConfig(lookahead_depth=4, lookahead_beam=2, hybrid_ratio=0.7,
                           w_random=0.0, w_deceptive=0.0)

        action = bot.compute_bot_action(
            self.grid, bot_player, global_cooldown_idx=None, nation_list=self.nation_list,
            turn_number=5, suspected_human_ri=self.nation_list[3].ring_index,
            evolved_config=config)

        self.assertIsNotNone(action, "4-ply bot should compute a valid action")
        self.assertEqual(action[-1], 'intent')

class TestKnightMechanics(unittest.TestCase):
    """Unit tests for Knight promotion, army capacity, movement, and combat."""

    def setUp(self):
        self.grid = MapGrid()
        self.grid.generate_map()
        self.nation_list = list(NATIONS)

    def test_knight_promotion_on_home_territory(self):
        """A nation can promote an army on home territory to a knight; max 1 knight per nation."""
        n0 = NATIONS[0]
        self.assertFalse(self.grid._has_knight(n0))

        valid_promos = self.grid.get_promote_knight_hexes(n0)
        self.assertTrue(len(valid_promos) > 0, "Home hexes with armies should be eligible for knight promotion")

        # Promote one army
        promo_hex = valid_promos[0]
        army = self.grid.armies[promo_hex][0]
        knight = self.grid.promote_to_knight(army)

        self.assertIsInstance(knight, Knight)
        self.assertTrue(self.grid._has_knight(n0))
        self.assertIn(knight, self.grid.knights.get(promo_hex, []))
        self.assertNotIn(army, self.grid.armies.get(promo_hex, []))

        # Cannot promote a second knight
        self.assertEqual(self.grid.get_promote_knight_hexes(n0), [],
                         "Nation with an active knight must not be allowed to promote another")

    def test_knight_counts_toward_army_cap(self):
        """The knight counts as one of the nation's active armies for army capacity."""
        n0 = NATIONS[0]
        # Start: 3 armies, 0 knights -> army_count = 3, max cap = 3 -> cannot muster
        self.assertEqual(self.grid._army_count(n0), 3)
        self.assertFalse(self.grid.can_muster_army(n0))

        # Promote 1 army to knight -> 2 armies, 1 knight -> army_count is still 3
        army = list(self.grid.armies.values())[0][0]
        if army.nation.ring_index != 0:
            army = [a for alist in self.grid.armies.values() for a in alist if a.nation.ring_index == 0][0]
        self.grid.promote_to_knight(army)

        self.assertEqual(self.grid._army_count(n0), 3)
        self.assertFalse(self.grid.can_muster_army(n0), "Knight must count toward active army limit")

    def test_unsupported_army_cannot_attack_unsupported_knight(self):
        """An unsupported army cannot attack an unsupported knight."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3] # Enemy

        army = Army(n_yellow, 0, 0)
        knight = Knight(n_cobalt, 0, 1)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_army(army)
        self.grid.add_knight(knight)

        self.assertFalse(self.grid.is_supported(army))
        self.assertFalse(self.grid.is_supported(knight))

        # Valid attacks for unsupported army should NOT include knight
        valid_attacks = self.grid.get_valid_attacks(army)
        self.assertNotIn((0, 1), valid_attacks)

        success, msg, destroyed = self.grid.resolve_attack(army, 0, 1)
        self.assertFalse(success, "Unsupported army attack on knight must fail")
        self.assertEqual(destroyed, [])

    def test_unsupported_knight_attacks_unsupported_army_trades(self):
        """An unsupported knight attacking an unsupported army results in mutual destruction."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        knight = Knight(n_yellow, 0, 0)
        army = Army(n_cobalt, 0, 1)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_knight(knight)
        self.grid.add_army(army)

        self.assertFalse(self.grid.is_supported(knight))
        self.assertFalse(self.grid.is_supported(army))

        valid_attacks = self.grid.get_valid_attacks(knight)
        self.assertIn((0, 1), valid_attacks)

        success, msg, destroyed = self.grid.resolve_attack(knight, 0, 1)
        self.assertTrue(success)
        self.assertIn(knight, destroyed)
        self.assertIn(army, destroyed)
        self.assertNotIn((0, 0), self.grid.knights)
        self.assertNotIn((0, 1), self.grid.armies)

    def test_unsupported_knight_attacks_unsupported_knight_trades(self):
        """Unsupported knight attacking unsupported knight results in mutual destruction."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        k1 = Knight(n_yellow, 0, 0)
        k2 = Knight(n_cobalt, 0, 1)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_knight(k1)
        self.grid.add_knight(k2)

        valid_attacks = self.grid.get_valid_attacks(k1)
        self.assertIn((0, 1), valid_attacks)

        success, msg, destroyed = self.grid.resolve_attack(k1, 0, 1)
        self.assertTrue(success)
        self.assertIn(k1, destroyed)
        self.assertIn(k2, destroyed)

    def test_supported_army_attacks_unsupported_knight(self):
        """Supported army attacking unsupported knight destroys knight and advances."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        army = Army(n_yellow, 0, 0)
        champ_supp = Champion(n_yellow, 0, 0)
        knight = Knight(n_cobalt, 0, 1)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_army(army)
        self.grid.add_champion(champ_supp)
        self.grid.add_knight(knight)

        self.assertTrue(self.grid.is_supported(army))
        self.assertFalse(self.grid.is_supported(knight))

        valid_attacks = self.grid.get_valid_attacks(army)
        self.assertIn((0, 1), valid_attacks)

        success, msg, destroyed = self.grid.resolve_attack(army, 0, 1)
        self.assertTrue(success)
        self.assertEqual(destroyed, [knight])
        self.assertEqual(army.hex_location, (0, 1), "Supported army should advance into knight's hex")

    def test_supported_army_attacks_supported_knight_both_destroyed(self):
        """Supported army attacking supported knight results in mutual destruction."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        army = Army(n_yellow, 0, 0)
        champ1 = Champion(n_yellow, 0, 0)
        knight = Knight(n_cobalt, 0, 1)
        champ2 = Champion(n_cobalt, 0, 1)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_army(army)
        self.grid.add_champion(champ1)
        self.grid.add_knight(knight)
        self.grid.add_champion(champ2)

        self.assertTrue(self.grid.is_supported(army))
        self.assertTrue(self.grid.is_supported(knight))

        success, msg, destroyed = self.grid.resolve_attack(army, 0, 1)
        self.assertTrue(success)
        self.assertIn(army, destroyed)
        self.assertIn(knight, destroyed)

    def test_champion_attacks_knight(self):
        """Champion destroys unsupported knight and advances."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        champ = Champion(n_yellow, 0, 0)
        knight = Knight(n_cobalt, 0, 1)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_champion(champ)
        self.grid.add_knight(knight)

        valid_attacks = self.grid.get_valid_attacks(champ)
        self.assertIn((0, 1), valid_attacks)

        success, msg, destroyed = self.grid.resolve_attack(champ, 0, 1)
        self.assertTrue(success)
        self.assertEqual(destroyed, [knight])
        self.assertEqual(champ.hex_location, (0, 1))

    def test_knight_attacks_trapped_sovereign(self):
        """Knight can attack an unsupported, trapped sovereign, but cannot attack champions."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        knight = Knight(n_yellow, 0, 0)
        sov = Sovereign(n_cobalt, 0, 1)
        champ = Champion(n_cobalt, 1, 0)
        # Trap the sovereign at (0, 1) using enemies at opposite directions
        enemy_trap1 = Army(n_yellow, 0, 2)
        enemy_trap2 = Army(n_yellow, 0, 0) # knight is already here at (0, 0)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        self.grid.add_knight(knight)
        self.grid.add_sovereign(sov)
        self.grid.add_champion(champ)
        self.grid.add_army(enemy_trap1)

        self.assertTrue(self.grid.is_trapped(sov))

        valid_attacks = self.grid.get_valid_attacks(knight)
        self.assertIn((0, 1), valid_attacks, "Knight should be able to attack trapped sovereign")
        self.assertNotIn((1, 0), valid_attacks, "Knight cannot attack champion")

        success, msg, destroyed = self.grid.resolve_attack(knight, 0, 1)
        self.assertTrue(success)
        self.assertEqual(destroyed, [sov])

    def test_knight_movement_and_stacking(self):
        """Knight seizes territory and cannot stack on another army or knight."""
        n_yellow = NATIONS[0]
        n_cobalt = NATIONS[3]

        knight = Knight(n_yellow, 0, 0)
        self.grid.armies.clear()
        self.grid.knights.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()
        self.grid.add_knight(knight)

        # Move to neutral hex (0, 1)
        self.grid.tile_control[(0, 1)] = None
        self.grid.apply_move(knight, 0, 1)
        self.assertEqual(self.grid.tile_control.get((0, 1)), 0, "Knight claims neutral hex")

        # Move to enemy hex (0, 2)
        self.grid.tile_control[(0, 2)] = 3
        self.grid.apply_move(knight, 0, 2)
        self.assertEqual(self.grid.tile_control.get((0, 2)), 0, "Knight seizes enemy hex")

        # Destination occupied by an army
        army = Army(n_yellow, 0, 1)
        self.grid.add_army(army)
        valid_moves = self.grid.get_valid_moves(knight)
        self.assertNotIn((0, 1), valid_moves, "Knight cannot move onto hex occupied by army")


class TestGhostNationTerritory(unittest.TestCase):
    """Tests for territory release when a nation loses its sovereign."""

    def setUp(self):
        for nation in NATIONS:
            nation.is_ghost = False
        self.grid = MapGrid()
        self.grid.generate_map()

    def test_ghost_nation_empty_tiles_become_neutral(self):
        """When a nation collapses, its empty tiles revert to neutral."""
        # Cobalt (3) owns its 4 home hexes at start; clear units so they're empty
        cobalt_hexes = [coord for coord, ri in self.grid.tile_control.items() if ri == 3]
        self.assertTrue(len(cobalt_hexes) > 0, "Cobalt should own tiles at start")

        # Remove Cobalt's sovereign to trigger collapse
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.ring_index == 3]
        for s in cobalt_sovs:
            self.grid.remove_sovereign(s)
        # Also clear all Cobalt units from its hexes so they're empty
        for coord in cobalt_hexes:
            self.grid.armies[coord] = [a for a in self.grid.armies.get(coord, [])
                                       if a.nation.ring_index != 3]
            self.grid.champions[coord] = [c for c in self.grid.champions.get(coord, [])
                                          if c.nation.ring_index != 3]

        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(NATIONS[3].is_ghost)

        for coord in cobalt_hexes:
            self.assertIsNone(
                self.grid.tile_control.get(coord),
                f"Empty collapsed tile {coord} should be neutral, not Cobalt's")

    def test_ghost_nation_occupied_tile_goes_to_single_occupier(self):
        """A collapsed nation's tile with one occupying unit goes to that unit's nation."""
        # Place a Yellow army on one of Cobalt's home hexes
        cobalt_hex = [coord for coord, ri in self.grid.tile_control.items() if ri == 3][0]
        yellow_army = Army(NATIONS[0], *cobalt_hex)
        self.grid.armies[cobalt_hex] = [yellow_army]
        self.grid.champions[cobalt_hex] = []

        # Collapse Cobalt
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.ring_index == 3]
        for s in cobalt_sovs:
            self.grid.remove_sovereign(s)

        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(NATIONS[3].is_ghost)
        self.assertEqual(
            self.grid.tile_control.get(cobalt_hex), 0,
            "Tile with lone Yellow army should transfer to Yellow on Cobalt collapse")

    def test_ghost_nation_contested_tile_becomes_neutral(self):
        """A collapsed nation's tile with units from 2+ nations stays neutral."""
        cobalt_hex = [coord for coord, ri in self.grid.tile_control.items() if ri == 3][0]
        # Place Yellow army and Green champion on same hex
        self.grid.armies[cobalt_hex] = [Army(NATIONS[0], *cobalt_hex)]
        self.grid.champions[cobalt_hex] = [Champion(NATIONS[1], *cobalt_hex)]

        # Collapse Cobalt
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.ring_index == 3]
        for s in cobalt_sovs:
            self.grid.remove_sovereign(s)

        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(NATIONS[3].is_ghost)
        self.assertIsNone(
            self.grid.tile_control.get(cobalt_hex),
            "Contested collapsed tile should be neutral")

    def test_move_into_ghost_territory_claims_hex(self):
        """Moving an army into a former ghost nation's neutral tile claims it."""
        # Find a Cobalt hex adjacent to a neutral hex
        cobalt_hex = None
        target_hex = None
        for coord, ri in self.grid.tile_control.items():
            if ri == 3:
                for nq, nr in self.grid.get_neighbors(*coord):
                    if self.grid.tile_control.get((nq, nr)) is None and self.grid.get_tile(nq, nr):
                        cobalt_hex = coord
                        target_hex = (nq, nr)
                        break
            if cobalt_hex:
                break

        if cobalt_hex is None:
            self.skipTest("No Cobalt hex adjacent to a neutral tile in this layout")

        # Collapse Cobalt, leaving cobalt_hex empty → becomes neutral
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.ring_index == 3]
        for s in cobalt_sovs:
            self.grid.remove_sovereign(s)
        self.grid.armies[cobalt_hex] = []
        self.grid.champions[cobalt_hex] = []
        self.grid.check_ghost_nations(NATIONS)
        self.assertIsNone(self.grid.tile_control.get(cobalt_hex),
                          "Cobalt hex should be neutral after collapse")

        # Place a Yellow army on the neutral cobalt_hex and move to target_hex
        yellow_army = Army(NATIONS[0], *cobalt_hex)
        self.grid.armies[cobalt_hex] = [yellow_army]
        # target_hex must be clear and on board
        self.grid.armies[target_hex] = []
        self.grid.apply_move(yellow_army, *target_hex)
        self.assertEqual(
            self.grid.tile_control.get(target_hex), 0,
            "Yellow army moving into neutral territory should claim it")


if __name__ == '__main__':
    unittest.main()


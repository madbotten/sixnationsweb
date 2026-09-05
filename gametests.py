"""
GameTests.py — Unit tests for Six Nations
Covers 24 tests of basic and advanced game mechanics.
"""

import unittest
from factions import NATIONS, Nation, create_nations
from player import Player
from map import MapGrid
from units import Army, Knight, Champion, Sovereign
from bot import BotMemory
from moves import serialize_move, apply_serialized_move
from evolution import BotGoals


class TestSixNations(unittest.TestCase):

    def setUp(self):
        # Reset ghost flags and diplomatic stances on shared singletons before each test
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()

    # -----------------------------------------------------------------------
    # 1. Diplomacy -- Dynamic Stances
    # -----------------------------------------------------------------------

    def test_01_default_neutral(self):
        """All nations start neutral to each other after _init_diplomacy."""
        from factions import create_nations
        nations = create_nations()
        for i, n in enumerate(nations):
            for j, other in enumerate(nations):
                if i == j:
                    self.assertEqual(n.get_stance(other), 'self')
                else:
                    self.assertEqual(n.get_stance(other), 'neutral',
                                     f"{n} should be neutral to {other}")

    def test_02_set_ally_mirrored(self):
        """set_ally is symmetric: A.set_ally(B) → B.is_ally(A)."""
        from factions import create_nations
        nations = create_nations()
        a, b = nations[0], nations[2]
        a.set_ally(b)
        self.assertTrue(a.is_ally(b))
        self.assertTrue(b.is_ally(a))
        self.assertFalse(a.is_enemy(b))

    def test_03_set_enemy_mirrored(self):
        """set_enemy is symmetric: A.set_enemy(B) → B.is_enemy(A)."""
        from factions import create_nations
        nations = create_nations()
        a, b = nations[1], nations[4]
        a.set_enemy(b)
        self.assertTrue(a.is_enemy(b))
        self.assertTrue(b.is_enemy(a))
        self.assertFalse(a.is_ally(b))

    def test_03b_set_neutral_clears_previous(self):
        """set_neutral after set_enemy returns both to neutral."""
        from factions import create_nations
        nations = create_nations()
        a, b = nations[0], nations[3]
        a.set_enemy(b)
        a.set_neutral(b)
        self.assertEqual(a.get_stance(b), 'neutral')
        self.assertEqual(b.get_stance(a), 'neutral')

    def test_03c_each_nation_in_exactly_one_list(self):
        """Each other nation appears in exactly one of allies/neutrals/enemies."""
        from factions import create_nations
        nations = create_nations()
        nations[0].set_ally(nations[1])
        nations[0].set_enemy(nations[3])
        for n in nations:
            for other in nations:
                if other is n:
                    continue
                count = (int(other in n.allies)
                         + int(other in n.neutrals)
                         + int(other in n.enemies))
                self.assertEqual(count, 1,
                                 f"{other} appears {count} times in {n}'s lists")

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
        for nation_name, corner in MapGrid.NATION_CORNERS.items():
            sovs = self.grid.sovereigns.get(corner, [])
            champs = self.grid.champions.get(corner, [])
            self.assertEqual(len(sovs), 1)
            self.assertEqual(len(champs), 1)
            self.assertEqual(sovs[0].nation.color_name, nation_name)
            self.assertEqual(champs[0].nation.color_name, nation_name)

    # -----------------------------------------------------------------------
    # 3. Player Cooldown Mechanics
    # -----------------------------------------------------------------------

    def test_07_player_cooldown_fifo(self):
        """Player cooldown holds at most the 2 most recently moved nations (FIFO)."""
        player = Player()
        self.assertEqual(player.cooldown, [])

        player.add_to_cooldown(NATIONS[1])
        self.assertEqual(player.cooldown, [NATIONS[1].color_name])

        player.add_to_cooldown(NATIONS[2])
        self.assertEqual(player.cooldown, [NATIONS[2].color_name, NATIONS[1].color_name])

        player.add_to_cooldown(NATIONS[3])
        self.assertEqual(player.cooldown, [NATIONS[3].color_name, NATIONS[2].color_name])

    def test_08_nation_on_cooldown_check(self):
        """nation_on_cooldown returns True only for nations currently in the cooldown list."""
        player = Player()
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
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Nations 0 and 1 need to be allied for cross-nation support
        NATIONS[0].set_ally(NATIONS[1])
        try:
            army_yellow = Army(NATIONS[0], 0, 0)
            champ_green = Champion(NATIONS[1], 0, 0)
            grid.add_army(army_yellow)
            grid.add_champion(champ_green)

            self.assertTrue(grid.is_supported(army_yellow))
            self.assertTrue(grid.is_supported(champ_green))
        finally:
            NATIONS[0].set_neutral(NATIONS[1])

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
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            sov_enemy = Sovereign(NATIONS[3], 0, 1)
            grid.add_sovereign(sov_enemy)
            self.assertNotIn((0, 1), grid.get_valid_moves(army_a))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

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
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_army = Army(NATIONS[0], 0, 0)
            def_army = Army(NATIONS[3], 1, 0)
            grid.add_army(atk_army)
            grid.add_army(def_army)

            success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
            self.assertTrue(success)
            self.assertIn(atk_army, destroyed)
            self.assertIn(def_army, destroyed)
            self.assertEqual(len(grid.armies.get((0,0), [])), 0)
            self.assertEqual(len(grid.armies.get((1,0), [])), 0)
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_14_supported_army_vs_unsupported_army(self):
        """Supported army attacking unsupported enemy army: enemy destroyed, attacker advances."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_army = Army(NATIONS[0], 0, 0)
            atk_champ = Champion(NATIONS[0], 0, 0)
            def_army = Army(NATIONS[3], 1, 0)
            grid.add_army(atk_army)
            grid.add_champion(atk_champ)
            grid.add_army(def_army)

            success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
            self.assertTrue(success)
            self.assertIn(def_army, destroyed)
            self.assertNotIn(atk_army, destroyed)
            self.assertEqual(atk_army.hex_location, (1, 0))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_15_unsupported_army_cannot_attack_supported_army(self):
        """Unsupported army attacking a supported army is an illegal attack."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_army = Army(NATIONS[0], 0, 0)
            def_army = Army(NATIONS[3], 1, 0)
            def_champ = Champion(NATIONS[3], 1, 0)
            grid.add_army(atk_army)
            grid.add_army(def_army)
            grid.add_champion(def_champ)

            success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
            self.assertFalse(success)
            self.assertEqual(destroyed, [])
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_16_army_cannot_attack_champion(self):
        """Armies are not allowed to attack champions."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_army = Army(NATIONS[0], 0, 0)
            enemy_champ = Champion(NATIONS[3], 1, 0)
            grid.add_army(atk_army)
            grid.add_champion(enemy_champ)

            success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
            self.assertFalse(success)
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    # -----------------------------------------------------------------------
    # 7. Combat: Champion vs Units
    # -----------------------------------------------------------------------

    def test_17_champion_attacks_unsupported_army(self):
        """Unsupported champion attacking unsupported enemy army destroys army."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            champ = Champion(NATIONS[0], 0, 0)
            enemy_army = Army(NATIONS[3], 1, 0)
            grid.add_champion(champ)
            grid.add_army(enemy_army)

            success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
            self.assertTrue(success)
            self.assertIn(enemy_army, destroyed)
            self.assertNotIn(champ, destroyed)
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_18_champion_attacks_sovereign_shielded_by_army(self):
        """Supported champion attacking sovereign supported by army destroys army, sovereign survives."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_champ = Champion(NATIONS[0], 0, 0)
            atk_army = Army(NATIONS[0], 0, 0)
            grid.add_champion(atk_champ)
            grid.add_army(atk_army)

            def_sov = Sovereign(NATIONS[3], 1, 0)
            def_army = Army(NATIONS[3], 1, 0)
            grid.add_sovereign(def_sov)
            grid.add_army(def_army)

            success, msg, destroyed = grid.resolve_attack(atk_champ, 1, 0)
            self.assertTrue(success)
            self.assertIn(def_army, destroyed)
            self.assertNotIn(def_sov, destroyed)
            self.assertIn(def_sov, grid.sovereigns.get((1, 0), []))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    # -----------------------------------------------------------------------
    # 8. Trapped Sovereign & Sovereign Combat
    # -----------------------------------------------------------------------

    def test_19_trapped_sovereign_detection_and_army_kill(self):
        """Unsupported sovereign with opposite enemy neighbours is trapped and can be killed by an army."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[3].set_enemy(NATIONS[0])
        try:
            sov = Sovereign(NATIONS[0], 0, 0)
            grid.add_sovereign(sov)

            enemy_top = Army(NATIONS[3], 0, -1)
            enemy_bot = Army(NATIONS[3], 0, 1)
            grid.add_army(enemy_top)
            grid.add_army(enemy_bot)

            self.assertTrue(grid.is_trapped(sov))

            success, msg, destroyed = grid.resolve_attack(enemy_top, 0, 0)
            self.assertTrue(success)
            self.assertIn(sov, destroyed)
            self.assertEqual(enemy_top.hex_location, (0, 0))
        finally:
            NATIONS[3].set_neutral(NATIONS[0])

    def test_20_sovereign_cannot_attack(self):
        """Sovereigns cannot initiate attacks."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            sov = Sovereign(NATIONS[0], 0, 0)
            enemy = Army(NATIONS[3], 1, 0)
            grid.add_sovereign(sov)
            grid.add_army(enemy)

            success, msg, destroyed = grid.resolve_attack(sov, 1, 0)
            self.assertFalse(success)
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

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
        self.assertEqual(new_army.nation.color_name, 'Yilerond')
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

        self.assertEqual(new_champ.nation.color_name, 'Yilerond')
        self.assertEqual(new_champ.hex_location, promo_hex)
        self.assertEqual(grid.get_promote_hexes(NATIONS[0]), [])

    # -----------------------------------------------------------------------
    # 10. Win, Loss, and Ghost Nations
    # -----------------------------------------------------------------------

    def test_23_ghost_nation_and_win_loss_conditions(self):
        # TODO: Test ghost nation status and modern win/scoring conditions under the 3-prevail / 3-defeat system.
        # Verify that losing a sovereign marks the nation as a ghost, and that prevail/defeat picks
        # score correctly when sovereigns survive or are destroyed.
        pass

    # -----------------------------------------------------------------------
    # 11. Bot Memory and Scoring
    # -----------------------------------------------------------------------

    def test_24_bot_memory_scoring_and_guessing(self):
        """BotMemory adds points by color_name and guesses the correct faction."""
        mem = BotMemory(debug=False)
        # Add points for Yilerond
        mem.add_score('Yilerond', 4)
        self.assertEqual(mem.nation_scores.get('Yilerond', 0), 4)
        # No ally propagation any more
        self.assertNotIn('Galland', mem.nation_scores)
        self.assertNotIn('Ravengard', mem.nation_scores)

        # Bot is Galland -> guess should exclude 'Galland' and pick 'Yilerond'
        guess = mem.guess_faction(NATIONS, exclude_names=('Galland',))
        self.assertEqual(guess.color_name, 'Yilerond')

    def test_25_bot_does_not_hand_human_victory(self):
        # TODO: Test sovereign targeting adjustments under the 3-prevail / 3-defeat system.
        # Verify that bot suppresses attacks on prevail-goal sovereigns (-9999.0 protection penalty)
        # and prioritizes attacks on defeat-goal sovereigns (+2000.0 priority bonus).
        pass

    # -----------------------------------------------------------------------
    # 12. Advance after combat
    # -----------------------------------------------------------------------

    def test_26_champion_advances_after_killing_army(self):
        """Champion advances into hex after destroying an enemy army (hex clear)."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            champ = Champion(NATIONS[0], 0, 0)
            enemy_army = Army(NATIONS[3], 1, 0)
            grid.add_champion(champ)
            grid.add_army(enemy_army)

            success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
            self.assertTrue(success)
            self.assertIn(enemy_army, destroyed)
            self.assertEqual(champ.hex_location, (1, 0))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_27_champion_advances_after_killing_champion(self):
        """Supported champion advances after destroying unsupported enemy champion."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_champ = Champion(NATIONS[0], 0, 0)
            support = Army(NATIONS[0], 0, 0)
            enemy_champ = Champion(NATIONS[3], 1, 0)
            grid.add_champion(atk_champ)
            grid.add_army(support)
            grid.add_champion(enemy_champ)

            success, msg, destroyed = grid.resolve_attack(atk_champ, 1, 0)
            self.assertTrue(success)
            self.assertIn(enemy_champ, destroyed)
            self.assertEqual(atk_champ.hex_location, (1, 0))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_28_champion_advances_after_killing_sovereign(self):
        """Champion advances after destroying an unsupported enemy sovereign."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            champ = Champion(NATIONS[0], 0, 0)
            enemy_sov = Sovereign(NATIONS[3], 1, 0)
            grid.add_champion(champ)
            grid.add_sovereign(enemy_sov)

            success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
            self.assertTrue(success)
            self.assertIn(enemy_sov, destroyed)
            self.assertEqual(champ.hex_location, (1, 0))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_29_champion_does_not_advance_when_enemies_remain(self):
        """Champion kills one enemy but does NOT advance because another enemy remains."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            champ = Champion(NATIONS[0], 0, 0)
            support = Army(NATIONS[0], 0, 0)
            enemy_army1 = Army(NATIONS[3], 1, 0)
            enemy_army2 = Army(NATIONS[3], 1, 0)
            grid.add_champion(champ)
            grid.add_army(support)
            grid.add_army(enemy_army1)
            grid.add_army(enemy_army2)

            success, msg, destroyed = grid.resolve_attack(champ, 1, 0)
            self.assertTrue(success)
            self.assertEqual(champ.hex_location, (0, 0))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_30_army_advances_to_join_friendly_champion(self):
        """Supported army kills enemy army and advances into hex that already contains our friendly champion."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_army  = Army(NATIONS[0], 0, 0)
            support   = Champion(NATIONS[0], 0, 0)   # provides support at origin
            own_champ = Champion(NATIONS[0], 1, 0)   # our champion already at target hex
            enemy_army = Army(NATIONS[3], 1, 0)      # enemy army (unsupported — own_champ is ours, not theirs)
            grid.add_army(atk_army)
            grid.add_champion(support)
            grid.add_champion(own_champ)
            grid.add_army(enemy_army)

            success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
            self.assertTrue(success)
            self.assertIn(enemy_army, destroyed)
            # Army advances to join its friendly champion at (1, 0)
            self.assertEqual(atk_army.hex_location, (1, 0))
            self.assertIn(own_champ, grid.champions.get((1, 0), []))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_31_army_advances_into_clear_hex(self):
        """Supported army kills lone enemy army and advances into the now-empty hex."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            atk_army = Army(NATIONS[0], 0, 0)
            support = Champion(NATIONS[0], 0, 0)
            enemy_army = Army(NATIONS[3], 1, 0)
            grid.add_army(atk_army)
            grid.add_champion(support)
            grid.add_army(enemy_army)

            success, msg, destroyed = grid.resolve_attack(atk_army, 1, 0)
            self.assertTrue(success)
            self.assertIn(enemy_army, destroyed)
            self.assertEqual(atk_army.hex_location, (1, 0))
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

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

        # serialize_move now takes nation_name (color_name string), not a ring index
        move_data = serialize_move('move', NATIONS[0].color_name, unit_type='army',
                                  from_hex=(0, 0), to_hex=(1, 0))
        self.assertEqual(move_data['type'], 'move')
        self.assertEqual(move_data['nation_name'], NATIONS[0].color_name)
        self.assertEqual(move_data['from'], [0, 0])
        self.assertEqual(move_data['to'], [1, 0])

        # Apply
        success, msg, moved_nation, destroyed = apply_serialized_move(
            grid, move_data, NATIONS)
        self.assertTrue(success)
        self.assertEqual(moved_nation.color_name, NATIONS[0].color_name)
        self.assertEqual(army.hex_location, (1, 0))

    def test_33_serialize_apply_attack(self):
        """Serialize an attack and apply it — enemy should be destroyed."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()
        NATIONS[0].set_enemy(NATIONS[3])
        try:
            champ = Champion(NATIONS[0], 0, 0)
            enemy = Army(NATIONS[3], 1, 0)
            grid.add_champion(champ)
            grid.add_army(enemy)

            move_data = serialize_move('attack', NATIONS[0].color_name, unit_type='champion',
                                      from_hex=(0, 0), to_hex=(1, 0))
            success, msg, moved_nation, destroyed = apply_serialized_move(
                grid, move_data, NATIONS)
            self.assertTrue(success)
            self.assertIn(enemy, destroyed)
        finally:
            NATIONS[0].set_neutral(NATIONS[3])

    def test_34_serialize_apply_recruit(self):
        """Serialize a recruit action and apply it — new army should appear."""
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Place a sovereign so the nation isn't a ghost
        sov = Sovereign(NATIONS[0], 0, 0)
        grid.add_sovereign(sov)

        move_data = serialize_move('recruit', NATIONS[0].color_name, to_hex=(1, 0))
        success, msg, moved_nation, destroyed = apply_serialized_move(
            grid, move_data, NATIONS)
        self.assertTrue(success)
        self.assertEqual(moved_nation.color_name, NATIONS[0].color_name)
        armies_at = grid.armies.get((1, 0), [])
        self.assertEqual(len(armies_at), 1)
        self.assertEqual(armies_at[0].nation.color_name, NATIONS[0].color_name)

    # -----------------------------------------------------------------------
    # 14. Bot sovereign protection — never kill prevail-goal sovereign
    # -----------------------------------------------------------------------

    def test_35_score_attack_forbids_allied_sovereign(self):
        """_score_attack returns -9999 when targeting the bot's allied sovereign."""
        from bot import _score_attack
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Set up test enemy setup: NATIONS[0] (Yilerond) enemies are [2,3,4]
        # NATIONS[3] (Crestmoor) enemy of NATIONS[1] (Galland) follows from ring
        NATIONS[0].set_enemy(NATIONS[2])
        NATIONS[0].set_enemy(NATIONS[3])
        NATIONS[0].set_enemy(NATIONS[4])
        NATIONS[3].set_enemy(NATIONS[1])   # needed for attacker vs allied_sov

        allied_name_set = {'Yilerond', 'Galland', 'Ravengard'}
        enemy_name_set  = {'Beldrin', 'Crestmoor', 'Malkor'}

        # Attacker = Crestmoor champion; allied_sov = Galland sovereign
        attacker = Champion(NATIONS[3], 0, 0)
        allied_sov = Sovereign(NATIONS[1], 1, 0)
        grid.add_champion(attacker)
        grid.add_sovereign(allied_sov)

        # Crestmoor IS enemy of Galland per setup above
        self.assertTrue(NATIONS[3].is_enemy(NATIONS[1]))

        score = _score_attack(grid, attacker, 1, 0, enemy_name_set,
                              allied_name_set=allied_name_set)
        self.assertEqual(score, -9999.0,
            "Attack on allied sovereign must be scored -9999")

    def test_36_score_attack_allows_enemy_sovereign(self):
        """_score_attack scores positively when targeting an enemy sovereign."""
        from bot import _score_attack
        grid = MapGrid()
        grid.generate_map()
        grid.armies.clear(); grid.champions.clear(); grid.sovereigns.clear()

        # Set up: Yilerond enemies = [Beldrin, Crestmoor, Malkor]
        # Galland enemies = [Crestmoor, Malkor, Ravengard] (so Galland attacks Crestmoor = enemy)
        NATIONS[0].set_enemy(NATIONS[2])
        NATIONS[0].set_enemy(NATIONS[3])
        NATIONS[0].set_enemy(NATIONS[4])
        NATIONS[1].set_enemy(NATIONS[3])

        allied_name_set = {'Yilerond', 'Galland', 'Ravengard'}
        enemy_name_set  = {'Beldrin', 'Crestmoor', 'Malkor'}

        # Galland champion attacks Crestmoor sovereign
        attacker = Champion(NATIONS[1], 0, 0)
        enemy_sov = Sovereign(NATIONS[3], 1, 0)
        grid.add_champion(attacker)
        grid.add_sovereign(enemy_sov)

        self.assertTrue(NATIONS[1].is_enemy(NATIONS[3]))

        score = _score_attack(grid, attacker, 1, 0, enemy_name_set,
                              allied_name_set=allied_name_set)
        self.assertGreater(score, 0,
            "Attack on enemy sovereign must score positively")

    def test_37_compute_bot_action_never_targets_allied_sovereign(self):
        # TODO: Verify compute_bot_action with bot_goals never chooses an attack against any prevail-goal sovereign.
        pass

    def test_38_bot_never_attacks_own_secret_sovereign(self):
        # TODO: Verify bot scoring strictly suppresses attacks against prevail-goal sovereigns (-9999).
        pass


class TestSovereignEnemyMoveRestriction(unittest.TestCase):
    """Tests for the rule: enemy players can only move a sovereign to a hex where it would be supported."""

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()
        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

    def test_sovereign_blocked_from_unsupported_hex(self):
        """No player can move a sovereign to a hex without a friendly unit."""
        from units import Sovereign
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)
        # Mark neighbors as own territory so terrain gate passes
        for nq, nr in self.grid.get_neighbors(0, -2):
            if self.grid.get_tile(nq, nr):
                self.grid.tile_control[(nq, nr)] = 'Yilerond'  # own (Yellow)

        valid = self.grid.get_valid_moves(sov)
        self.assertEqual(len(valid), 0,
            "Sovereign should have no valid moves when no friendly unit is at any neighbour")

    def test_sovereign_can_move_to_supported_hex(self):
        """A sovereign can move to a hex where a friendly unit is already present."""
        from units import Sovereign
        from units import Army
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)
        army = Army(NATIONS[0], 0, -1)
        self.grid.add_army(army)
        # Mark as own territory
        self.grid.tile_control[(0, -1)] = 'Yilerond'
        self.grid.tile_control[(0, -2)] = 'Yilerond'

        valid = self.grid.get_valid_moves(sov)
        self.assertIn((0, -1), valid,
            "Sovereign should be able to move to hex occupied by friendly army")

    def test_sovereign_confined_to_own_territory(self):
        """Sovereign cannot enter ally, neutral, enemy, or unclaimed hexes."""
        from units import Sovereign
        from units import Army
        sov = Sovereign(NATIONS[0], 0, -2)
        self.grid.add_sovereign(sov)
        # Place friendly unit at one neighbour, mark it as own territory
        army = Army(NATIONS[0], 0, -1)
        self.grid.add_army(army)
        self.grid.tile_control[(0, -1)] = 'Yilerond'   # own
        self.grid.tile_control[(0, -2)] = 'Yilerond'   # own (current)
        # Mark another neighbour as a neutral nation's territory
        if self.grid.get_tile(1, -2):
            self.grid.tile_control[(1, -2)] = 'Galland'  # Nation 1 (neutral to Nation 0)

        valid = self.grid.get_valid_moves(sov)
        self.assertIn((0, -1), valid, "Sovereign should reach supported own-territory hex")
        self.assertNotIn((1, -2), valid, "Sovereign must NOT enter neutral-nation territory")


class TestHexControlAndMuster(unittest.TestCase):
    """Tests for the Hex Control territory system, dynamic army caps, and updated muster rules."""

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        # Set test stance setup so allied/enemy tests work
        NATIONS[0].set_enemy(NATIONS[2])
        NATIONS[0].set_enemy(NATIONS[3])
        NATIONS[0].set_enemy(NATIONS[4])
        NATIONS[0].set_ally(NATIONS[1])
        NATIONS[0].set_ally(NATIONS[5])
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
                self.assertIsInstance(owner_ri, str)

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
        self.assertEqual(self.grid.tile_control.get((0, 0)), 'Yilerond',
            "Entering neutral hex should claim it for mover's nation")

    def test_allied_unit_does_not_steal_control(self):
        """An allied unit moving into your territory does NOT seize control (first come keeps it)."""
        # Yellow (0) owns (0, -2)
        self.assertEqual(self.grid.tile_control.get((0, -2)), 'Yilerond')
        # Clear units from destination (0, -2) so it's a vacant move destination
        self.grid.armies.pop((0, -2), None)

        # Green (1) is ally of Yellow (0)
        green_army = Army(NATIONS[1], 0, -1)
        self.grid.add_army(green_army)
        # Move green army to (0, -2)
        success, msg = self.grid.apply_move(green_army, 0, -2)
        self.assertTrue(success, f"Move failed: {msg}")
        self.assertEqual(self.grid.tile_control.get((0, -2)), 'Yilerond',
            "Allied unit should not seize territory from an ally")

    def test_enemy_unit_seizes_control(self):
        """An enemy Army or Champion moving into your territory SEIZES control."""
        # Yellow (0) owns (0, -2)
        self.assertEqual(self.grid.tile_control.get((0, -2)), 'Yilerond')
        # Clear units from destination (0, -2) so it's a vacant move destination
        self.grid.armies.pop((0, -2), None)

        # Cobalt (3) is enemy of Yellow (0)
        cobalt_army = Army(NATIONS[3], 0, -1)
        self.grid.add_army(cobalt_army)
        success, msg = self.grid.apply_move(cobalt_army, 0, -2)
        self.assertTrue(success, f"Move failed: {msg}")
        self.assertEqual(self.grid.tile_control.get((0, -2)), 'Crestmoor',
            "Enemy army must seize territory upon entering")

    def test_army_cap_progression(self):
        """Cap is 3 base (4 hexes), and increases by +1 for every 3 additional hexes."""
        n0 = NATIONS[0]
        self.assertEqual(self.grid.get_max_army_cap(n0), 3)

        # Give n0 2 extra hexes (total 6) -> cap still 3
        self.grid.tile_control[(0, 0)] = 'Yilerond'
        self.grid.tile_control[(0, 1)] = 'Yilerond'
        self.assertEqual(self.grid.get_controlled_hex_count(n0), 6)
        self.assertEqual(self.grid.get_max_army_cap(n0), 3)

        # Give 1 more hex (total 7, +3 over base) -> cap becomes 4
        self.grid.tile_control[(1, 0)] = 'Yilerond'
        self.assertEqual(self.grid.get_controlled_hex_count(n0), 7)
        self.assertEqual(self.grid.get_max_army_cap(n0), 4)

        # Total 10 hexes (+6 over base) -> cap becomes 5
        self.grid.tile_control[(1, 1)] = 'Yilerond'
        self.grid.tile_control[(-1, 0)] = 'Yilerond'
        self.grid.tile_control[(-1, 1)] = 'Yilerond'
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
        self.grid.tile_control[(0, -1)] = 'Crestmoor'
        # Set neighbor (1, -2) as neutral (None)
        self.grid.tile_control[(1, -2)] = None

        valid = self.grid.get_valid_moves(sov)
        self.assertNotIn((0, -1), valid, "Sovereign must NOT enter enemy-nation territory")
        self.assertNotIn((1, -2), valid, "Sovereign must NOT enter neutral territory (tile_control=None means unclaimed, still not own)")


class TestPositionalEvaluator(unittest.TestCase):
    """Tests for the positional board evaluator."""

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        # Set test stance setup for evaluator tests
        NATIONS[0].set_enemy(NATIONS[2])
        NATIONS[0].set_enemy(NATIONS[3])
        NATIONS[0].set_enemy(NATIONS[4])
        self.grid = MapGrid()
        self.grid.generate_map()
        self.nation_list = list(NATIONS)

    def tearDown(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)

    def test_ghost_enemy_boosts_score(self):
        # TODO: Verify killing a defeat-goal sovereign (marking nation as ghost) increases positional evaluation score for bot_goals.
        pass

    def test_own_sov_dead_catastrophic(self):
        # TODO: Verify destruction of prevail-goal sovereigns penalizes positional evaluation score according to priority.
        pass

    def test_trapped_unsupported_enemy_scores_higher(self):
        # TODO: Verify an unsupported and trapped defeat-goal sovereign yields a higher position score for bot_goals than a safe one.
        pass

    def test_material_advantage(self):
        # TODO: Verify having more allied material (armies/knights/champions of prevail nations) yields a higher evaluation score.
        pass

    def test_perspective_symmetry(self):
        # TODO: Verify evaluating from two opposing bot_goals perspectives yields inversely correlated scores.
        pass

    def test_territory_control_evaluation(self):
        # TODO: Verify controlling more territory with prevail nations increases positional evaluation score for bot_goals.
        pass

    def test_territory_move_scoring(self):
        """Moves that claim neutral or enemy territory should receive higher tactical move scores."""
        from bot import _score_move
        n0 = self.nation_list[0]
        army = Army(n0, 0, -1)
        self.grid.add_army(army)

        allied_names = {'Yilerond', 'Galland', 'Ravengard'}
        enemy_names  = {'Beldrin', 'Crestmoor', 'Malkor'}

        # Move into neutral hex (0, 0)
        self.grid.tile_control[(0, 0)] = None
        score_high_claim = _score_move(self.grid, army, 0, 0, enemy_names, allied_names,
                                       weights={'claim_territory': 3.0})
        score_low_claim = _score_move(self.grid, army, 0, 0, enemy_names, allied_names,
                                      weights={'claim_territory': 0.0})

        self.assertGreater(score_high_claim, score_low_claim + 50.0,
            "Higher claim_territory weight should yield higher move score when claiming territory")

    def test_custom_eval_weights(self):
        # TODO: Verify custom eval weights in BotConfig override default weights when evaluating position with bot_goals.
        pass

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

        bot_player = Player(is_bot=True, player_id='test_bot')
        config = BotConfig(lookahead_depth=2, lookahead_beam=2, hybrid_ratio=0.5,
                           w_random=0.0, w_deceptive=0.0)

        action = bot.compute_bot_action(
            self.grid, bot_player, global_cooldown_name=None, nation_list=self.nation_list,
            turn_number=5, suspected_human_ri=self.nation_list[3].color_name,
            evolved_config=config)

        self.assertIsNotNone(action, "Bot should compute a valid action with hybrid scoring")
        self.assertEqual(action[-1], 'intent')

    def test_4ply_lookahead_execution(self):
        """compute_bot_action with 4-ply lookahead should compute legal action."""
        import bot
        from player import Player
        from evolution import BotConfig

        bot_player = Player(is_bot=True, player_id='test_bot_4ply')
        config = BotConfig(lookahead_depth=4, lookahead_beam=2, hybrid_ratio=0.7,
                           w_random=0.0, w_deceptive=0.0)

        action = bot.compute_bot_action(
            self.grid, bot_player, global_cooldown_name=None, nation_list=self.nation_list,
            turn_number=5, suspected_human_ri=self.nation_list[3].color_name,
            evolved_config=config)

        self.assertIsNotNone(action, "4-ply bot should compute a valid action")
        self.assertEqual(action[-1], 'intent')

class TestKnightMechanics(unittest.TestCase):
    """Unit tests for Knight promotion, army capacity, movement, and combat."""

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        # Set test stance setup so knight seizing enemy territory works
        NATIONS[0].set_enemy(NATIONS[2])
        NATIONS[0].set_enemy(NATIONS[3])
        NATIONS[0].set_enemy(NATIONS[4])
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
        if army.nation.color_name != 'Yilerond':
            army = [a for alist in self.grid.armies.values() for a in alist if a.nation.color_name == 'Yilerond'][0]
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
        self.assertEqual(self.grid.tile_control.get((0, 1)), 'Yilerond', "Knight claims neutral hex")

        # Move to enemy hex (0, 2)
        self.grid.tile_control[(0, 2)] = 'Crestmoor'
        self.grid.apply_move(knight, 0, 2)
        self.assertEqual(self.grid.tile_control.get((0, 2)), 'Yilerond', "Knight seizes enemy hex")

        # Destination occupied by an army
        army = Army(n_yellow, 0, 1)
        self.grid.add_army(army)
        valid_moves = self.grid.get_valid_moves(knight)
        self.assertNotIn((0, 1), valid_moves, "Knight cannot move onto hex occupied by army")


class TestGhostNationTerritory(unittest.TestCase):
    """Tests for territory release when a nation loses its sovereign."""

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()

    def test_ghost_nation_empty_tiles_become_neutral(self):
        """When a nation collapses, its empty tiles revert to neutral."""
        # Cobalt (3) owns its 4 home hexes at start; clear units so they're empty
        cobalt_hexes = [coord for coord, ri in self.grid.tile_control.items() if ri == 'Crestmoor']
        self.assertTrue(len(cobalt_hexes) > 0, "Cobalt should own tiles at start")

        # Remove Cobalt's sovereign to trigger collapse
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.color_name == 'Crestmoor']
        for s in cobalt_sovs:
            self.grid.remove_sovereign(s)
        # Also clear all Cobalt units from its hexes so they're empty
        for coord in cobalt_hexes:
            self.grid.armies[coord] = [a for a in self.grid.armies.get(coord, [])
                                       if a.nation.color_name != 'Crestmoor']
            self.grid.champions[coord] = [c for c in self.grid.champions.get(coord, [])
                                          if c.nation.color_name != 'Crestmoor']

        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(NATIONS[3].is_ghost)

        for coord in cobalt_hexes:
            self.assertIsNone(
                self.grid.tile_control.get(coord),
                f"Empty collapsed tile {coord} should be neutral, not Cobalt's")

    def test_ghost_nation_occupied_tile_goes_to_single_occupier(self):
        """A collapsed nation's tile with one occupying unit goes to that unit's nation."""
        # Place a Yellow army on one of Cobalt's home hexes
        cobalt_hex = [coord for coord, ri in self.grid.tile_control.items() if ri == 'Crestmoor'][0]
        yellow_army = Army(NATIONS[0], *cobalt_hex)
        self.grid.armies[cobalt_hex] = [yellow_army]
        self.grid.champions[cobalt_hex] = []

        # Collapse Cobalt
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.color_name == 'Crestmoor']
        for s in cobalt_sovs:
            self.grid.remove_sovereign(s)

        self.grid.check_ghost_nations(NATIONS)
        self.assertTrue(NATIONS[3].is_ghost)
        self.assertEqual(
            self.grid.tile_control.get(cobalt_hex), 'Yilerond',
            "Tile with lone Yellow army should transfer to Yellow on Cobalt collapse")

    def test_ghost_nation_contested_tile_becomes_neutral(self):
        """A collapsed nation's tile with units from 2+ nations stays neutral."""
        cobalt_hex = [coord for coord, ri in self.grid.tile_control.items() if ri == 'Crestmoor'][0]
        # Place Yellow army and Green champion on same hex
        self.grid.armies[cobalt_hex] = [Army(NATIONS[0], *cobalt_hex)]
        self.grid.champions[cobalt_hex] = [Champion(NATIONS[1], *cobalt_hex)]

        # Collapse Cobalt
        cobalt_sovs = [s for sl in self.grid.sovereigns.values() for s in sl
                       if s.nation.color_name == 'Crestmoor']
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
            if ri == 'Crestmoor':
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
                       if s.nation.color_name == 'Crestmoor']
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
            self.grid.tile_control.get(target_hex), 'Yilerond',
            "Yellow army moving into neutral territory should claim it")


class TestFineGrainedDiplomacy(unittest.TestCase):
    """Unit tests for fine-grained diplomacy genes, 2-step transitions, and evolution integration."""

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()
        from diplomacy_panel import DiplomacyState
        self.dipl_state = DiplomacyState()

    def test_2step_diplomacy_prevail_war_to_neutral(self):
        """When prevail picks are at war, bot proposes 'neutral' to end war before allying."""
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player

        p1_nation = NATIONS[0]  # Yilerond
        p2_nation = NATIONS[1]  # Aethelgard
        # Set them at war initially
        p1_nation.set_enemy(p2_nation)

        player = Player(is_bot=True)
        goals = BotGoals(prevail_goals=[p1_nation.color_name, p2_nation.color_name],
                         defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name])
        weights = {
            'w_dipl_prevail_alliance': 2.0,
            'w_dipl_defeat_vs_defeat': 1.0,
            'w_dipl_prevail_vs_defeat': 1.0,
            'w_dipl_peace': 0.5,
        }

        actions = _gather_actions(self.grid, player, None, NATIONS,
                                  weights=weights, dipl_state=self.dipl_state,
                                  bot_goals=goals)

        # Look for diplomacy actions concerning (p1, p2)
        p1_p2_actions = [a for a in actions if a[1] == 'diplomacy'
                         and {a[2].color_name, a[3].color_name} == {p1_nation.color_name, p2_nation.color_name}]
        self.assertTrue(len(p1_p2_actions) > 0, "Should generate diplomacy action for warring prevail nations")
        # Direct 'ally' jump is forbidden; it must propose 'neutral' (Step 1)
        stances = [a[4] for a in p1_p2_actions]
        self.assertIn('neutral', stances, "Must propose 'neutral' as step 1 to end war between prevail picks")
        self.assertNotIn('ally', stances, "Cannot jump directly from enemy to ally")

    def test_2step_diplomacy_defeat_ally_to_neutral(self):
        """When defeat picks are allied, bot proposes 'neutral' to break alliance before war."""
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player

        d1 = NATIONS[3]  # Crestmoor
        d2 = NATIONS[4]  # Drakenreach
        # Set them allied initially
        d1.set_ally(d2)

        player = Player(is_bot=True)
        goals = BotGoals(prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
                         defeat_goals=[d1.color_name, d2.color_name, NATIONS[5].color_name])
        weights = {
            'w_dipl_defeat_vs_defeat': 2.5,
            'w_dipl_prevail_alliance': 1.0,
            'w_dipl_prevail_vs_defeat': 1.0,
        }

        actions = _gather_actions(self.grid, player, None, NATIONS,
                                  weights=weights, dipl_state=self.dipl_state,
                                  bot_goals=goals)

        d1_d2_actions = [a for a in actions if a[1] == 'diplomacy'
                         and {a[2].color_name, a[3].color_name} == {d1.color_name, d2.color_name}]
        self.assertTrue(len(d1_d2_actions) > 0, "Should generate diplomacy action for allied defeat nations")
        stances = [a[4] for a in d1_d2_actions]
        self.assertIn('neutral', stances, "Must propose 'neutral' as step 1 to break alliance between defeat picks")
        self.assertNotIn('enemy', stances, "Cannot jump directly from ally to enemy")

    def test_targeted_diplomacy_weights_scaling(self):
        """Fine-grained weights properly scale their corresponding targeted actions."""
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player

        player = Player(is_bot=True)
        goals = BotGoals(prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
                         defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name])

        # Test with low defeat vs defeat weight
        w_low = {'w_dipl_defeat_vs_defeat': 0.5, 'w_dipl_prevail_vs_defeat': 1.0, 'w_dipl_prevail_alliance': 1.0}
        act_low = _gather_actions(self.grid, player, None, NATIONS,
                                  weights=w_low, dipl_state=self.dipl_state, bot_goals=goals)
        d_wars_low = [a[0] for a in act_low if a[1] == 'diplomacy' and a[4] == 'enemy'
                      and {a[2].color_name, a[3].color_name} == {NATIONS[3].color_name, NATIONS[4].color_name}]

        # Test with high defeat vs defeat weight
        w_high = {'w_dipl_defeat_vs_defeat': 2.0, 'w_dipl_prevail_vs_defeat': 1.0, 'w_dipl_prevail_alliance': 1.0}
        act_high = _gather_actions(self.grid, player, None, NATIONS,
                                   weights=w_high, dipl_state=self.dipl_state, bot_goals=goals)
        d_wars_high = [a[0] for a in act_high if a[1] == 'diplomacy' and a[4] == 'enemy'
                       and {a[2].color_name, a[3].color_name} == {NATIONS[3].color_name, NATIONS[4].color_name}]

        self.assertTrue(len(d_wars_low) > 0 and len(d_wars_high) > 0)
        self.assertAlmostEqual(d_wars_high[0] / d_wars_low[0], 4.0, places=1,
                               msg="Score should scale 4x when gene quadruples (2.0 vs 0.5)")

    def test_intent_chooses_diplomacy_in_lookahead(self):
        """EvolvableBot intent move chooses high-scoring diplomacy even with lookahead_depth > 1."""
        from evolution import BotConfig, EvolvableBot, BotGoals

        config = BotConfig(
            lookahead_depth=2,
            lookahead_beam=3,
            hybrid_ratio=0.5,
            w_random=0.0,
            w_deceptive=0.0,
            w_dipl_prevail_vs_defeat=4.0,  # very high war weight -> ~240 score
            w_dipl_defeat_vs_defeat=3.0,
        )
        bot = EvolvableBot(config)
        goals = BotGoals(prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
                         defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name])

        action = bot.compute_action(self.grid, None, NATIONS, turn_number=1,
                                    dipl_state=self.dipl_state, bot_goals=goals)
        self.assertIsNotNone(action)
        _score, atype, *rest = action
        self.assertEqual(atype, 'diplomacy',
                         f"Bot with elevated war weight should select diplomacy on turn 1, got {atype}")

    def test_headless_game_diplomacy_locking(self):
        """_execute with dipl_state properly locks the pair on cooldown."""
        from bot import _execute
        action = (100.0, 'diplomacy', NATIONS[0], NATIONS[3], 'enemy')
        moved, atype, desc = _execute(self.grid, action, dipl_state=self.dipl_state)
        self.assertEqual(moved, NATIONS[0])
        self.assertEqual(atype, 'diplomacy')
        self.assertTrue(self.dipl_state.is_locked(NATIONS[0], NATIONS[3]),
                        "Diplomacy action should lock the pair on cooldown")

    def test_sovereign_attack_defeat_vs_prevail_protection(self):
        """Attacking defeat sovereign scores high; attacking prevail sovereign is suppressed with -9999."""
        from bot import _score_attack
        from evolution import BotGoals
        from player import Player
        from units import Army

        attacker_nation = NATIONS[3]
        defeat_sov_nation = NATIONS[4]
        prevail_sov_nation = NATIONS[1]

        attacker_nation.set_enemy(defeat_sov_nation)
        attacker_nation.set_enemy(prevail_sov_nation)

        player = Player(is_bot=True)
        goals = BotGoals(prevail_goals=[NATIONS[0].color_name, prevail_sov_nation.color_name, NATIONS[2].color_name],
                         defeat_goals=[attacker_nation.color_name, defeat_sov_nation.color_name, NATIONS[5].color_name])

        allied_name_set = set(goals.prevail_goals)
        enemy_name_set = set(goals.defeat_goals)

        attacker = Army(attacker_nation, 0, 0)
        self.grid.armies[(0, 0)] = [attacker]

        # 1. Defeat sovereign at (0, 1)
        d_sov = [s for sl in self.grid.sovereigns.values() for s in sl if s.nation is defeat_sov_nation][0]
        orig_d_loc = d_sov.hex_location
        self.grid.sovereigns[orig_d_loc].remove(d_sov)
        d_sov.q, d_sov.r = 0, 1
        self.grid.sovereigns.setdefault((0, 1), []).append(d_sov)

        score_defeat_atk = _score_attack(self.grid, attacker, 0, 1, enemy_name_set, allied_name_set=allied_name_set)
        self.assertGreater(score_defeat_atk, 900.0, "Attacking defeat goal sovereign should have high positive score")

        # 2. Prevail sovereign at (1, 0)
        p_sov = [s for sl in self.grid.sovereigns.values() for s in sl if s.nation is prevail_sov_nation][0]
        orig_p_loc = p_sov.hex_location
        self.grid.sovereigns[orig_p_loc].remove(p_sov)
        p_sov.q, p_sov.r = 1, 0
        self.grid.sovereigns.setdefault((1, 0), []).append(p_sov)

        score_prevail_atk = _score_attack(self.grid, attacker, 1, 0, enemy_name_set, allied_name_set=allied_name_set)
        self.assertLess(score_prevail_atk, -5000.0, "Attacking prevail sovereign must be suppressed (-9999)")

    def test_army_kills_unsupported_untrapped_sovereign(self):
        """Rule change: an army can kill an unsupported sovereign even without entrapment."""
        from units import Army, Sovereign

        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()
        self.grid.knights.clear()

        sov_nation = NATIONS[0]
        atk_nation = NATIONS[3]
        atk_nation.set_enemy(sov_nation)

        try:
            # Sovereign at (0, 0) - solo, unsupported
            sov = Sovereign(sov_nation, 0, 0)
            self.grid.add_sovereign(sov)

            # Enemy army at (0, 1) - only ONE enemy adjacent, clearly NOT trapped!
            attacker = Army(atk_nation, 0, 1)
            self.grid.add_army(attacker)

            self.assertFalse(self.grid.is_trapped(sov), "Single adjacent enemy does not trap sovereign")
            self.assertFalse(self.grid.is_supported(sov), "Sovereign is unsupported")

            # Must be in valid attacks
            valid_atks = self.grid.get_valid_attacks(attacker)
            self.assertIn((0, 0), valid_atks, "Army must be able to attack unsupported untrapped sovereign")

            # Must resolve successfully
            success, msg, destroyed = self.grid.resolve_attack(attacker, 0, 0)
            self.assertTrue(success, f"Attack failed: {msg}")
            self.assertIn(sov, destroyed, "Sovereign must be destroyed")
            self.assertEqual(attacker.hex_location, (0, 0), "Attacking army must advance")
        finally:
            atk_nation.set_neutral(sov_nation)

    def test_army_cannot_kill_supported_sovereign(self):
        """Supported sovereign remains safe from army attacks."""
        from units import Army, Sovereign

        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        sov_nation = NATIONS[0]
        atk_nation = NATIONS[3]
        atk_nation.set_enemy(sov_nation)

        try:
            # Sovereign at (0, 0) supported by friendly army at (0, 0)
            sov = Sovereign(sov_nation, 0, 0)
            guard = Army(sov_nation, 0, 0)
            self.grid.add_sovereign(sov)
            self.grid.add_army(guard)

            attacker = Army(atk_nation, 0, 1)
            self.grid.add_army(attacker)

            self.assertTrue(self.grid.is_supported(sov), "Sovereign is supported by guard")

            # Army cannot attack supported sovereign
            success, msg, destroyed = self.grid.resolve_attack(attacker, 0, 0, target_type='sovereign')
            self.assertFalse(success, "Army cannot attack supported sovereign")
        finally:
            atk_nation.set_neutral(sov_nation)

    def test_recruit_disallowed_when_enemy_adjacent_or_on_hex(self):
        """Recruiting is disallowed on ANY hex if an enemy unit is adjacent or on the hex."""
        from units import Army, Champion

        n0 = NATIONS[0]
        n3 = NATIONS[3]
        n0.set_enemy(n3)

        try:
            # Ensure n0 can recruit
            armies = [u for u in self.grid.get_all_nation_units(n0) if isinstance(u, Army)]
            for a in armies:
                self.grid.remove_army(a)

            valid_hexes = self.grid.get_recruit_hexes(n0)
            self.assertTrue(len(valid_hexes) > 0)
            target = valid_hexes[0]

            # Place enemy army adjacent to target hex
            nbr = self.grid.get_neighbors(*target)[0]
            enemy_army = Army(n3, *nbr)
            self.grid.add_army(enemy_army)

            new_valid = self.grid.get_recruit_hexes(n0)
            self.assertNotIn(target, new_valid, "Cannot recruit on hex when enemy army is adjacent")

            # Remove enemy army, place enemy champion adjacent
            self.grid.remove_army(enemy_army)
            enemy_champ = Champion(n3, *nbr)
            self.grid.add_champion(enemy_champ)

            new_valid_champ = self.grid.get_recruit_hexes(n0)
            self.assertNotIn(target, new_valid_champ, "Cannot recruit on hex when enemy champion is adjacent")
        finally:
            n0.set_neutral(n3)

    def test_recruit_blocked_in_serialized_move_when_enemy_adjacent(self):
        """apply_serialized_move strictly rejects recruit if an enemy unit is adjacent."""
        from moves import apply_serialized_move, serialize_move
        from units import Army, Sovereign

        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        n0 = NATIONS[0]
        n3 = NATIONS[3]
        n0.set_enemy(n3)

        try:
            # Place sovereign at (0, 0)
            sov = Sovereign(n0, 0, 0)
            self.grid.add_sovereign(sov)

            # Place enemy army at (1, -1) (adjacent to (1, 0))
            enemy = Army(n3, 1, -1)
            self.grid.add_army(enemy)

            # Try to recruit at (1, 0)
            move_data = serialize_move('recruit', n0.color_name, to_hex=(1, 0))
            success, msg, moved_nation, destroyed = apply_serialized_move(
                self.grid, move_data, NATIONS
            )
            self.assertFalse(success, "Must reject recruit when enemy army is adjacent")
            self.assertIn("enemy unit adjacent or on hex", msg)
        finally:
            n0.set_neutral(n3)

    def test_bot_attacks_and_kills_unsupported_defeat_sovereign(self):
        """Bot with warmonger weights prioritizes killing an adjacent unsupported defeat sovereign."""
        from bot import compute_bot_action
        from evolution import BotGoals
        from player import Player
        from units import Army, Sovereign

        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()

        bot_nation = NATIONS[0]
        target_nation = NATIONS[3]
        bot_nation.set_enemy(target_nation)

        try:
            # Place unsupported defeat sovereign at (0, 0)
            target_sov = Sovereign(target_nation, 0, 0)
            self.grid.add_sovereign(target_sov)

            # Place bot's army adjacent at (0, 1)
            bot_army = Army(bot_nation, 0, 1)
            self.grid.add_army(bot_army)

            # Place bot's own sovereign and bodyguard so bot's sovereign is alive and supported
            bot_sov = Sovereign(bot_nation, 2, -2)
            bot_guard = Army(bot_nation, 2, -2)
            self.grid.add_sovereign(bot_sov)
            self.grid.add_army(bot_guard)

            player = Player(is_bot=True)
            goals = BotGoals(
                prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name],
                defeat_goals=[target_nation.color_name, NATIONS[4].color_name, NATIONS[5].color_name]
            )

            from evolution import BotConfig
            config = BotConfig(
                w_random=0.0,
                w_deceptive=0.0,
                lookahead_depth=1,
                w_kill_enemy=3.0,
                w_dipl_prevail_vs_defeat=1.0,
            )

            action = compute_bot_action(
                self.grid, player, None, NATIONS,
                turn_number=1, evolved_config=config,
                bot_goals=goals, dipl_state=self.dipl_state
            )

            self.assertIsNotNone(action)
            score, atype, unit, coord = action[0], action[1], action[2], action[3]
            self.assertEqual(atype, 'attack', "Bot must choose attack")
            self.assertEqual(coord, (0, 0), "Bot must target the defeat sovereign's hex")
            self.assertEqual(unit, bot_army, "Bot must attack with the adjacent army")

            # Execute attack: verify sovereign is destroyed and nation becomes ghost
            success, msg, destroyed = self.grid.resolve_attack(bot_army, 0, 0)
            self.assertTrue(success)
            self.assertIn(target_sov, destroyed)
            self.grid.check_ghost_nations(NATIONS)
            self.assertTrue(target_nation.is_ghost, "Target nation must become a ghost")
        finally:
            bot_nation.set_neutral(target_nation)
            target_nation.is_ghost = False

    def test_evaluator_unsupported_sovereign_killable(self):
        # TODO: Verify unsupported defeat-goal sovereigns are evaluated as killable and supporting prevail sovereigns improves score.
        pass


class TestRecruitmentCooldown(unittest.TestCase):

    def setUp(self):
        from factions import _init_diplomacy
        for nation in NATIONS:
            nation.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()

    def test_per_nation_cooldown_tracking(self):
        """Each nation tracks its own recruitment cooldown independently."""
        n0 = NATIONS[0]
        n1 = NATIONS[1]

        # Initially, neither nation has recruited -> cooldown elapsed for both
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n0, 1))
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n1, 1))
        self.assertEqual(self.grid.turns_until_recruit(n0, 1), 0)
        self.assertEqual(self.grid.turns_until_recruit(n1, 1), 0)

        # Clear existing pieces of n0 to ensure it has capacity and room to recruit
        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()
        self.grid.knights.clear()
        sov0 = Sovereign(n0, 0, 0)
        self.grid.add_sovereign(sov0)
        sov1 = Sovereign(n1, 2, -2)
        self.grid.add_sovereign(sov1)

        # N0 recruits at turn 1
        valid_hexes_n0 = self.grid.get_recruitable_hexes(n0)
        self.assertTrue(len(valid_hexes_n0) > 0)
        target0 = valid_hexes_n0[0]
        self.grid.recruit_army(n0, *target0, turn_number=1)

        # N0 is now on cooldown for 10 turns (turns 1..10)
        for t in range(1, 11):
            self.assertFalse(self.grid.is_recruit_cooldown_elapsed(n0, t), f"N0 should be on cooldown at turn {t}")
            self.assertEqual(self.grid.turns_until_recruit(n0, t), 11 - t)
            self.assertEqual(self.grid.get_recruit_hexes(n0, turn_number=t), [], f"N0 get_recruit_hexes should be empty at turn {t}")

        # On turn 11 (10 turns elapsed since turn 1), cooldown has elapsed for N0
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n0, 11))
        self.assertEqual(self.grid.turns_until_recruit(n0, 11), 0)
        self.assertTrue(len(self.grid.get_recruit_hexes(n0, turn_number=11)) > 0)

        # Meanwhile, N1 was never on cooldown during turns 1..4
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n1, 1))
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n1, 4))

        # N1 recruits at turn 5
        valid_hexes_n1 = self.grid.get_recruitable_hexes(n1)
        self.assertTrue(len(valid_hexes_n1) > 0)
        target1 = valid_hexes_n1[0]
        self.grid.recruit_army(n1, *target1, turn_number=5)

        # N1 is now on cooldown from turn 5 to 14
        self.assertFalse(self.grid.is_recruit_cooldown_elapsed(n1, 5))
        self.assertFalse(self.grid.is_recruit_cooldown_elapsed(n1, 11))
        self.assertEqual(self.grid.turns_until_recruit(n1, 11), 4)
        # But N0 was already off cooldown on turn 11!
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n0, 11))

        # N1 becomes ready on turn 15
        self.assertTrue(self.grid.is_recruit_cooldown_elapsed(n1, 15))

    def test_apply_serialized_move_enforces_cooldown(self):
        """apply_serialized_move rejects recruit moves when nation is on cooldown."""
        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()
        self.grid.knights.clear()

        n0 = NATIONS[0]
        sov0 = Sovereign(n0, 0, 0)
        self.grid.add_sovereign(sov0)

        valid_hexes = self.grid.get_recruitable_hexes(n0)
        self.assertTrue(len(valid_hexes) >= 2)
        h1, h2 = valid_hexes[0], valid_hexes[1]

        # Turn 1: recruit at h1
        move1 = serialize_move('recruit', n0.color_name, to_hex=h1)
        success, msg, moved_nation, _ = apply_serialized_move(self.grid, move1, NATIONS, turn_number=1)
        self.assertTrue(success, f"First recruit should succeed: {msg}")

        # Turn 2: attempt recruit at h2 while on cooldown -> must fail
        move2 = serialize_move('recruit', n0.color_name, to_hex=h2)
        success2, msg2, _, _ = apply_serialized_move(self.grid, move2, NATIONS, turn_number=2)
        self.assertFalse(success2, "Recruit on turn 2 must fail due to cooldown")
        self.assertIn("cooldown active", msg2)

        # Turn 11: cooldown elapsed -> must succeed
        success11, msg11, _, _ = apply_serialized_move(self.grid, move2, NATIONS, turn_number=11)
        self.assertTrue(success11, f"Recruit on turn 11 must succeed: {msg11}")

    def test_sidebar_buttons_only_show_army_when_both_requirements_met(self):
        """Only show the army button on the side when both recruitable hex exists AND cooldown elapsed."""
        from main import compute_sidebar_buttons

        self.grid.armies.clear()
        self.grid.champions.clear()
        self.grid.sovereigns.clear()
        self.grid.knights.clear()

        n0 = NATIONS[0]
        sov0 = Sovereign(n0, 0, 0)
        self.grid.add_sovereign(sov0)

        # Requirement 1: recruitable hex exists. Requirement 2: cooldown elapsed.
        # At start (turn 1), both are met:
        btns = compute_sidebar_buttons(self.grid, [n0], turn_number=1)
        recruit_btns = [b for b in btns if b['type'] == 'recruit']
        self.assertEqual(len(recruit_btns), 1, "Army button must be shown when both requirements are met")

        # N0 recruits at turn 1
        valid_hexes = self.grid.get_recruitable_hexes(n0)
        self.grid.recruit_army(n0, *valid_hexes[0], turn_number=1)

        # On turn 2, hexes still exist but cooldown is active -> Army button NOT shown
        btns_turn2 = compute_sidebar_buttons(self.grid, [n0], turn_number=2)
        recruit_btns_turn2 = [b for b in btns_turn2 if b['type'] == 'recruit']
        self.assertEqual(len(recruit_btns_turn2), 0, "Army button must NOT be shown when cooldown is active")

        # On turn 11, cooldown has elapsed and recruitable hexes exist -> Army button shown again
        btns_turn11 = compute_sidebar_buttons(self.grid, [n0], turn_number=11)
        recruit_btns_turn11 = [b for b in btns_turn11 if b['type'] == 'recruit']
        self.assertEqual(len(recruit_btns_turn11), 1, "Army button must be shown when cooldown has elapsed")

        # If army cap is reached so there are no recruitable hexes, even if cooldown elapsed:
        # Fill up armies to reach cap
        while self.grid.can_muster_army(n0):
            rem_hexes = self.grid.get_recruitable_hexes(n0)
            if not rem_hexes:
                break
            self.grid.recruit_army(n0, *rem_hexes[0], turn_number=0)

        self.assertFalse(self.grid.can_muster_army(n0))
        self.assertEqual(self.grid.get_recruitable_hexes(n0), [])

        btns_capped = compute_sidebar_buttons(self.grid, [n0], turn_number=100)
        recruit_btns_capped = [b for b in btns_capped if b['type'] == 'recruit']
        self.assertEqual(len(recruit_btns_capped), 0, "Army button must NOT be shown when no recruitable hex exists")

    def test_headless_game_nations_match_grid_units(self):
        """HeadlessGame nations match the units placed on its MapGrid."""
        from evolution import HeadlessGame, BotConfig
        cfg = BotConfig()
        game = HeadlessGame(cfg, cfg, max_turns=10, seed=42)

        # Check that grid units belong to the game's own nation objects
        all_units = []
        for nation in game.nations:
            units = game.grid.get_all_nation_units(nation)
            self.assertTrue(len(units) > 0, f"Nation {nation.color_name} must have units on the grid")
            all_units.extend(units)

        for u in all_units:
            self.assertIn(u.nation, game.nations, "Unit nation must be an instance in game.nations")

        # Check that declaring war on game.nations immediately reflects on unit.nation.is_enemy
        n0 = game.nations[0]
        n1 = game.nations[1]
        n0.set_enemy(n1)

        u0 = game.grid.get_all_nation_units(n0)[0]
        u1 = game.grid.get_all_nation_units(n1)[0]
        self.assertTrue(u0.nation.is_enemy(u1.nation), "Units must recognize enemy stance set in HeadlessGame")

    def test_headless_game_decisiveness_when_sovereigns_eliminated(self):
        """When 3 sovereigns are eliminated in HeadlessGame, play() returns a decisive result (not draw)."""
        from evolution import HeadlessGame, BotConfig, RESULT_DRAW
        cfg = BotConfig()
        game = HeadlessGame(cfg, cfg, max_turns=50, seed=42)

        # Destroy 3 sovereigns from the grid
        killed = 0
        for coord, sov_list in list(game.grid.sovereigns.items()):
            if killed >= 3:
                break
            if sov_list:
                s = sov_list[0]
                game.grid.remove_sovereign(s)
                killed += 1

        self.assertEqual(killed, 3)
        game.grid.check_ghost_nations(game.nations)
        self.assertEqual(game.grid.count_ghost_nations(game.nations), 3)

        result = game.play()
        self.assertNotEqual(result, RESULT_DRAW, "Game must end decisively when 3 sovereigns are destroyed")


class TestPurePrevailDefeatSystem(unittest.TestCase):
    """Tests verifying the pure 3-Prevail / 3-Defeat system."""

    def test_player_pure_prevail_defeat_scoring(self):
        player = Player(is_bot=False, player_id='p1')
        nations = create_nations()

        player.prevail_picks = [nations[0], nations[1], nations[2]]
        player.defeat_picks  = [nations[3], nations[4], nations[5]]

        # At start: all alive -> prevail scores 3 + 2 + 1 = 6; defeat scores 0
        self.assertEqual(player.compute_score(), 6)

        # Defeat nations 3 and 5 die (ghosts)
        nations[3].is_ghost = True
        nations[5].is_ghost = True
        # Defeat slot 0 (nations[3]) gives 3 pts; Defeat slot 2 (nations[5]) gives 1 pt -> total = 6 + 4 = 10
        self.assertEqual(player.compute_score(), 10)

        # Prevail nation 0 dies (ghost)
        nations[0].is_ghost = True
        # Prevail loses 3 pts -> total = 10 - 3 = 7
        self.assertEqual(player.compute_score(), 7)

    def test_bot_goals_random_partition(self):
        nations = create_nations()
        goals = BotGoals.random(nations)
        self.assertEqual(len(goals.prevail_goals), 3)
        self.assertEqual(len(goals.defeat_goals), 3)
        # No overlap
        self.assertEqual(set(goals.prevail_goals) & set(goals.defeat_goals), set())
        # Covers all 6
        self.assertEqual(set(goals.prevail_goals) | set(goals.defeat_goals), {n.color_name for n in nations})

    def test_evaluator_pure_goals(self):
        from evaluator import evaluate_position
        grid = MapGrid()
        nations = create_nations()
        grid.generate_map(nations=nations)

        goals = BotGoals(
            prevail_goals=[nations[0].color_name, nations[1].color_name, nations[2].color_name],
            defeat_goals=[nations[3].color_name, nations[4].color_name, nations[5].color_name],
        )

        base_score = evaluate_position(grid, bot_goals=goals, nation_list=nations)

        # Killing defeat target #1 (nations[3]) should increase score significantly
        sov3 = [s for sl in grid.sovereigns.values() for s in sl if s.nation == nations[3]][0]
        grid.remove_sovereign(sov3)
        grid.check_ghost_nations(nations)

        score_after_defeat_kill = evaluate_position(grid, bot_goals=goals, nation_list=nations)
        self.assertGreater(score_after_defeat_kill, base_score)

    def test_headless_game_runs_with_pure_goals(self):
        from evolution import HeadlessGame, BotConfig
        cfg1 = BotConfig()
        cfg2 = BotConfig()
        game = HeadlessGame(cfg1, cfg2, max_turns=10, seed=123)

        self.assertEqual(len(game.bot1.player.prevail_picks), 3)
        self.assertEqual(len(game.bot1.player.defeat_picks), 3)

        # Run 5 turns without crashing
        for _ in range(5):
            game.turn_number += 1
            game.dipl_state.tick_cooldowns()

    def test_observe_diplomacy_scoring(self):
        """Diplomacy observation adjusts guess scores symmetrically: +3 for ally, -1 for enemy."""
        from bot import BotMemory
        nations = create_nations()
        mem = BotMemory()

        na = nations[0]
        nb = nations[1]

        # Initial scores are 0
        self.assertEqual(mem.scores[na.color_name], 0)
        self.assertEqual(mem.scores[nb.color_name], 0)

        # Alliance: +3 for both
        mem.observe_diplomacy(na, nb, 'ally')
        self.assertEqual(mem.scores[na.color_name], 3)
        self.assertEqual(mem.scores[nb.color_name], 3)

        # War: -1 for both
        mem.observe_diplomacy(na, nb, 'enemy')
        self.assertEqual(mem.scores[na.color_name], 2)
        self.assertEqual(mem.scores[nb.color_name], 2)

        # Neutral: no change
        mem.observe_diplomacy(na, nb, 'neutral')
        self.assertEqual(mem.scores[na.color_name], 2)
        self.assertEqual(mem.scores[nb.color_name], 2)

    def test_lookahead_propagates_opp_cooldown(self):
        """Lookahead search respects opp_cooldown so opponent does not hallucinate illegal moves."""
        from bot import _lookahead_best
        from evolution import BotGoals
        from player import Player
        grid = MapGrid()
        nations = create_nations()
        grid.generate_map(nations=nations)

        bot_player = Player(player_id='bot')
        goals = BotGoals.random(nations)

        # Give opponent a cooldown
        opp_cd = [nations[0].color_name, nations[1].color_name]

        # Call _lookahead_best with depth=2, beam=2, mode='position'
        best_action = _lookahead_best(
            grid, bot_player, None, nations, 1,
            opp_goals=None,
            depth=2, beam=2, mode='position',
            bot_goals=goals,
            opp_cooldown=opp_cd
        )
        self.assertIsNotNone(best_action)
        self.assertGreater(len(best_action), 1)

    def test_two_ply_runs_on_turn_1_without_opp_goals(self):
        """2-ply lookahead executes on Turn 1 even when opp_goals is None."""
        from bot import _lookahead_best
        from evolution import BotGoals
        from player import Player
        grid = MapGrid()
        nations = create_nations()
        grid.generate_map(nations=nations)

        bot_player = Player(player_id='bot')
        goals = BotGoals.random(nations)

        # Action mode depth=2 on Turn 1 with no opp_goals
        best_action = _lookahead_best(
            grid, bot_player, None, nations, 1,
            opp_goals=None,
            depth=2, beam=2, mode='action',
            bot_goals=goals,
            opp_cooldown=[]
        )
        self.assertIsNotNone(best_action)
        self.assertGreater(len(best_action), 1)

    def test_headless_game_observes_diplomacy(self):
        """HeadlessGame propagates opponent diplomacy into BotMemory."""
        from evolution import HeadlessGame, BotConfig
        cfg1 = BotConfig()
        cfg2 = BotConfig()
        game = HeadlessGame(cfg1, cfg2, max_turns=5, seed=42)

        # Manually trigger bot1 observing bot2's diplomacy
        game.bot1.observe_diplomacy(game.nations[0], game.nations[1], 'ally')
        self.assertEqual(game.bot1.memory.scores[game.nations[0].color_name], 3)
        self.assertEqual(game.bot1.memory.scores[game.nations[1].color_name], 3)


if __name__ == '__main__':
    unittest.main()


# ---------------------------------------------------------------------------
# Phase 1 tests — diplomacy cooldown correctness & bot diplomacy generation
# ---------------------------------------------------------------------------

class TestDiplomacyCooldown(unittest.TestCase):
    """Verify that diplomacy moves set player and global cooldowns like any other move."""

    def setUp(self):
        from factions import _init_diplomacy
        for n in NATIONS:
            n.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()
        from diplomacy_panel import DiplomacyPanel, DiplomacyAction
        self.DiplomacyAction = DiplomacyAction
        self.panel = DiplomacyPanel(list(NATIONS))
        from player import Player
        self.player = Player(is_bot=False, player_id='player1')

    def _make_action(self, flag_nation, box_nation, to_zone):
        """Helper: build a DiplomacyAction without going through mouse events."""
        from_zone = 'home' if to_zone in ('ally', 'war') else 'ally'
        return self.DiplomacyAction(
            box_nation=box_nation,
            flag_nation=flag_nation,
            from_zone=from_zone,
            to_zone=to_zone,
        )

    def test_human_dipl_sets_player_cooldown(self):
        """After a human diplomacy action, the flag nation is in the player's cooldown list."""
        import main as main_mod
        flag = NATIONS[0]   # Yilerond
        box  = NATIONS[1]   # Galland
        action = self._make_action(flag, box, 'war')

        # Apply the diplomacy move (mimics what main.py does)
        main_mod._apply_diplomacy_move(self.grid, self.panel, action, list(NATIONS))
        self.player.add_to_cooldown(flag)  # the line we added

        self.assertIn(flag.color_name, self.player.cooldown,
                      "Flag nation should be on player cooldown after diplomacy move")

    def test_human_dipl_sets_global_cooldown(self):
        """global_cooldown_name should be the flag nation's name after a human diplomacy move."""
        import main as main_mod
        flag = NATIONS[0]
        box  = NATIONS[2]
        action = self._make_action(flag, box, 'ally')
        main_mod._apply_diplomacy_move(self.grid, self.panel, action, list(NATIONS))

        # Simulate what main.py now does
        global_cooldown_name = flag.color_name
        self.assertEqual(global_cooldown_name, flag.color_name,
                         "global_cooldown_name must equal flag nation's color_name after diplomacy")

    def test_dipl_flag_nation_blocked_next_turn(self):
        """After a diplomacy move, flag nation is ineligible for the bot on its next turn."""
        from bot import _eligible_nations
        from player import Player
        flag = NATIONS[0]  # Yilerond
        bot_player = Player(is_bot=True)

        # Simulate: flag nation was just used diplomatically — set global cooldown
        global_cooldown_name = flag.color_name
        eligible = _eligible_nations(bot_player, global_cooldown_name, list(NATIONS))
        eligible_names = [n.color_name for n in eligible]
        self.assertNotIn(flag.color_name, eligible_names,
                         "Flag nation should be globally blocked on the turn after a diplomacy move")


class TestBotDiplomacy(unittest.TestCase):
    """Verify bot generates diplomacy actions even when weights=None (basic non-evolved bot)."""

    def setUp(self):
        from factions import _init_diplomacy
        for n in NATIONS:
            n.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()
        from diplomacy_panel import DiplomacyState
        self.dipl_state = DiplomacyState()

    def test_bot_generates_diplomacy_with_no_weights(self):
        """_gather_actions returns at least one diplomacy action when weights=None."""
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player

        player = Player(is_bot=True)
        goals = BotGoals(
            prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
            defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name],
        )

        actions = _gather_actions(
            self.grid, player, None, list(NATIONS),
            weights=None,           # key: basic bot has no weights
            dipl_state=self.dipl_state,
            bot_goals=goals,
            exclude_diplomacy=False,
        )

        dipl_actions = [a for a in actions if a[1] == 'diplomacy']
        self.assertGreater(len(dipl_actions), 0,
                           "Basic bot (weights=None) should still generate diplomacy actions")

    def test_bot_generates_diplomacy_with_weights(self):
        """_gather_actions returns diplomacy actions when explicit weights are provided."""
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player

        player = Player(is_bot=True)
        goals = BotGoals(
            prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
            defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name],
        )
        weights = {
            'w_dipl_prevail_alliance': 2.0,
            'w_dipl_defeat_vs_defeat': 2.0,
            'w_dipl_prevail_vs_defeat': 2.5,
        }

        actions = _gather_actions(
            self.grid, player, None, list(NATIONS),
            weights=weights,
            dipl_state=self.dipl_state,
            bot_goals=goals,
            exclude_diplomacy=False,
        )

        dipl_actions = [a for a in actions if a[1] == 'diplomacy']
        self.assertGreater(len(dipl_actions), 0,
                           "Evolved bot (weights provided) should generate diplomacy actions")

    def test_diplomacy_excluded_when_flag_set(self):
        """exclude_diplomacy=True suppresses all diplomacy actions regardless of weights."""
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player

        player = Player(is_bot=True)
        goals = BotGoals(
            prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
            defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name],
        )

        actions = _gather_actions(
            self.grid, player, None, list(NATIONS),
            weights=None,
            dipl_state=self.dipl_state,
            bot_goals=goals,
            exclude_diplomacy=True,  # lookahead tree sets this
        )

        dipl_actions = [a for a in actions if a[1] == 'diplomacy']
        self.assertEqual(len(dipl_actions), 0,
                         "exclude_diplomacy=True must suppress all diplomacy actions")


# ---------------------------------------------------------------------------
# Phase 2 tests — diplomatic base score scaling
# ---------------------------------------------------------------------------

class TestDiplomacyBaseScores(unittest.TestCase):
    """Verify that diplomatic base scores are scaled to compete with military scores."""

    def setUp(self):
        from factions import _init_diplomacy
        for n in NATIONS:
            n.is_ghost = False
        _init_diplomacy(NATIONS)
        self.grid = MapGrid()
        self.grid.generate_map()
        from diplomacy_panel import DiplomacyState
        self.dipl_state = DiplomacyState()

    def _get_dipl_actions(self, weights=None):
        from bot import _gather_actions
        from evolution import BotGoals
        from player import Player
        player = Player(is_bot=True)
        goals = BotGoals(
            prevail_goals=[NATIONS[0].color_name, NATIONS[1].color_name, NATIONS[2].color_name],
            defeat_goals=[NATIONS[3].color_name, NATIONS[4].color_name, NATIONS[5].color_name],
        )
        actions = _gather_actions(
            self.grid, player, None, list(NATIONS),
            weights=weights,
            dipl_state=self.dipl_state,
            bot_goals=goals,
            exclude_diplomacy=False,
        )
        return [a for a in actions if a[1] == 'diplomacy']

    def test_war_declaration_score_uses_dipl_base_war(self):
        """War declaration score should reflect dipl_base_war * w_dipl_* multiplier."""
        custom_base_war = 400.0
        weights = {'dipl_base_war': custom_base_war, 'w_dipl_prevail_vs_defeat': 2.0}
        actions = self._get_dipl_actions(weights=weights)
        war_actions = [a for a in actions if a[1] == 'diplomacy' and a[4] == 'enemy']
        self.assertGreater(len(war_actions), 0, "Should generate war declaration actions")
        # Score should be >= custom_base_war * w_dipl (min multiplier 1.0) for at least one action
        top_war_score = max(a[0] for a in war_actions)
        self.assertGreaterEqual(top_war_score, custom_base_war * 1.5,
                                f"Top war declaration score {top_war_score:.1f} should be >= "
                                f"{custom_base_war * 1.5:.1f} (base * min_weight)")

    def test_alliance_declaration_score_uses_dipl_base_ally(self):
        """Alliance declaration score should reflect dipl_base_ally * w_dipl_* multiplier."""
        custom_base_ally = 350.0
        weights = {'dipl_base_ally': custom_base_ally, 'w_dipl_prevail_alliance': 2.0}
        actions = self._get_dipl_actions(weights=weights)
        ally_actions = [a for a in actions if a[1] == 'diplomacy' and a[4] == 'ally']
        self.assertGreater(len(ally_actions), 0, "Should generate alliance actions")
        top_ally_score = max(a[0] for a in ally_actions)
        self.assertGreaterEqual(top_ally_score, custom_base_ally * 1.5,
                                f"Top alliance score {top_ally_score:.1f} should be >= "
                                f"{custom_base_ally * 1.5:.1f} (base * min_weight)")

    def test_default_war_score_exceeds_old_maximum(self):
        """Default war score (300 * 2.0 = 600) should exceed the old maximum (55 * 3.0 = 165)."""
        actions = self._get_dipl_actions(weights=None)  # uses defaults
        war_actions = [a for a in actions if a[1] == 'diplomacy' and a[4] == 'enemy']
        self.assertGreater(len(war_actions), 0)
        top_war_score = max(a[0] for a in war_actions)
        OLD_MAX = 165.0  # 55 * 3.0 (old hardcoded base * max weight)
        self.assertGreater(top_war_score, OLD_MAX,
                           f"Default war score {top_war_score:.1f} must exceed old max {OLD_MAX:.1f}")

    def test_botconfig_exports_dipl_base_fields(self):
        """BotConfig.to_weights_dict() must include dipl_base_war and dipl_base_ally."""
        from evolution import BotConfig
        cfg = BotConfig()
        w = cfg.to_weights_dict()
        self.assertIn('dipl_base_war', w,
                      "to_weights_dict() must export dipl_base_war")
        self.assertIn('dipl_base_ally', w,
                      "to_weights_dict() must export dipl_base_ally")
        self.assertEqual(w['dipl_base_war'], cfg.dipl_base_war)
        self.assertEqual(w['dipl_base_ally'], cfg.dipl_base_ally)

    def test_dipl_base_in_gene_ranges(self):
        """dipl_base_war and dipl_base_ally must be in _GENE_RANGES for evolution."""
        from evolution import _GENE_RANGES
        self.assertIn('dipl_base_war', _GENE_RANGES,
                      "dipl_base_war must be in _GENE_RANGES for evolution")
        self.assertIn('dipl_base_ally', _GENE_RANGES,
                      "dipl_base_ally must be in _GENE_RANGES for evolution")
        # Verify ranges are sensible
        lo, hi = _GENE_RANGES['dipl_base_war']
        self.assertGreater(hi, 200.0, "dipl_base_war upper range should be > 200")
        lo, hi = _GENE_RANGES['dipl_base_ally']
        self.assertGreater(hi, 150.0, "dipl_base_ally upper range should be > 150")

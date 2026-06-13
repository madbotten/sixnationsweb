import unittest
from factions import Faction, FACTIONS, FACTIONS_BY_RING

class TestFactionDiplomacy(unittest.TestCase):
    def test_diplomatic_distances(self):
        f0 = FACTIONS_BY_RING[0]  # Humans (0)
        f1 = FACTIONS_BY_RING[1]  # Elves (1)
        f2 = FACTIONS_BY_RING[2]  # Dwarves (2)
        f5 = FACTIONS_BY_RING[5]  # Kuotoa (5)
        f9 = FACTIONS_BY_RING[9]  # Nomads (9)

        # Self-alignment
        self.assertEqual(f0.diplomatic_distance(f0), 0)
        self.assertTrue(f0.isFullyAligned(f0))
        self.assertFalse(f0.isStronglyAligned(f0))
        self.assertFalse(f0.isLooselyAligned(f0))
        self.assertFalse(f0.isOpposed(f0))

        # Adjacent alignments (Strongly Aligned)
        self.assertEqual(f0.diplomatic_distance(f1), 1)
        self.assertEqual(f0.diplomatic_distance(f9), 1)
        self.assertTrue(f0.isStronglyAligned(f1))
        self.assertTrue(f0.isStronglyAligned(f9))
        self.assertFalse(f0.isFullyAligned(f1))
        self.assertFalse(f0.isLooselyAligned(f1))
        self.assertFalse(f0.isOpposed(f1))

        # Loosely Aligned (distances 2 and 3)
        self.assertEqual(f0.diplomatic_distance(f2), 2)
        self.assertTrue(f0.isLooselyAligned(f2))
        self.assertFalse(f0.isStronglyAligned(f2))
        self.assertFalse(f0.isOpposed(f2))

        # Opposed (distances 4 and 5)
        self.assertEqual(f0.diplomatic_distance(f5), 5)
        self.assertTrue(f0.isOpposed(f5))
        self.assertFalse(f0.isFullyAligned(f5))
        self.assertFalse(f0.isStronglyAligned(f5))
        self.assertFalse(f0.isLooselyAligned(f5))

    def test_all_alignments_counts(self):
        # Each Faction on the ring is:
        # - Fully Aligned with itself (1)
        # - Strongly Aligned with 2 adjacent Factions
        # - Loosely Aligned with 4 Factions
        # - Opposed to 3 distant Factions
        for f in FACTIONS:
            fully_aligned_count = sum(1 for other in FACTIONS if f.isFullyAligned(other))
            strongly_aligned_count = sum(1 for other in FACTIONS if f.isStronglyAligned(other))
            loosely_aligned_count = sum(1 for other in FACTIONS if f.isLooselyAligned(other))
            opposed_count = sum(1 for other in FACTIONS if f.isOpposed(other))

            self.assertEqual(fully_aligned_count, 1)
            self.assertEqual(strongly_aligned_count, 2)
            self.assertEqual(loosely_aligned_count, 4)
    def test_faction_gold(self):
        for f in FACTIONS:
            self.assertEqual(f.gold, 0)
            f.gold = 5
            self.assertEqual(f.gold, 5)
            with self.assertRaises(ValueError):
                f.gold = -1
            with self.assertRaises(ValueError):
                f.gold = "many"
            f.gold = 0

from map import MapGrid
import settings

class TestMapGeneration(unittest.TestCase):
    def test_map_structure(self):
        grid = MapGrid()
        grid.generate_map()
        
        # Test map has exactly 37 hexes
        self.assertEqual(len(grid.tiles), 37)
        
        # Test center 7 hexes have artifacts and unique terrain
        center_coords = grid.get_ring_coords(0) + grid.get_ring_coords(1)
        self.assertEqual(len(center_coords), 7)
        
        unique_lower = [t.lower() for t in settings.UNIQUE_TILES]
        for coord in center_coords:
            tile = grid.tiles[coord]
            self.assertTrue(tile.has_artifact)
            self.assertTrue(tile.terrain_type.lower() in unique_lower)
            self.assertEqual(tile.owner, "system")
            self.assertFalse(tile.is_stronghold)
            
        # Test outer 30 hexes
        outer_coords = grid.get_ring_coords(2) + grid.get_ring_coords(3)
        self.assertEqual(len(outer_coords), 30)
        
        # Track faction tile counts and strongholds
        faction_tiles = {}
        stronghold_counts = {}
        
        for coord in outer_coords:
            tile = grid.tiles[coord]
            self.assertFalse(tile.has_artifact)
            from factions import Faction
            self.assertTrue(isinstance(tile.owner, Faction))
            faction = tile.owner
            
            # Home terrain check
            self.assertEqual(tile.terrain_type.lower(), faction.home_terrain.lower())
            
            faction_tiles[faction.ring_number] = faction_tiles.get(faction.ring_number, 0) + 1
            if tile.is_stronghold:
                stronghold_counts[faction.ring_number] = stronghold_counts.get(faction.ring_number, 0) + 1
                # Strongholds must be in Ring 3
                dist = max(abs(coord[0]), abs(coord[1]), abs(coord[0] + coord[1]))
                self.assertEqual(dist, 3)
                
        # Each of the 10 factions must have exactly 3 tiles and 1 stronghold
        self.assertEqual(len(faction_tiles), 10)
        for ring_num in range(10):
            self.assertEqual(faction_tiles[ring_num], 3)
            self.assertEqual(stronghold_counts.get(ring_num, 0), 1)

from player import Player
from factions import FACTIONS_BY_RING

class TestPlayerNextFaction(unittest.TestCase):
    def test_choose_next_faction_distribution(self):
        player = Player(faction=FACTIONS_BY_RING[0])
        selections = []
        for _ in range(1000):
            selections.append(player.choose_next_faction())
            
        group_a_rings = {0, 1, 9}
        group_b_rings = {2, 3, 7, 8}
        
        count_a = sum(1 for f in selections if f.ring_number in group_a_rings)
        count_b = sum(1 for f in selections if f.ring_number in group_b_rings)
        
        self.assertTrue(400 <= count_a <= 600)
        self.assertTrue(400 <= count_b <= 600)
        self.assertEqual(count_a + count_b, 1000)
        
    def test_choose_next_faction_exception(self):
        player = Player(faction=FACTIONS_BY_RING[0])
        previous_faction = FACTIONS_BY_RING[1]
        
        for _ in range(100):
            chosen = player.choose_next_faction(previous_faction=previous_faction)
            self.assertNotEqual(chosen.ring_number, 1)

class TestArmyMusteringAndMovement(unittest.TestCase):
    def test_army_images_exist(self):
        import os
        import util
        from factions import FACTIONS
        from armies import Army
        
        for faction in FACTIONS:
            army = Army(faction, 0, 0)
            filename = army.image_filename
            filepath = os.path.join(util.ARMIES_DIR, filename)
            self.assertTrue(os.path.isfile(filepath), f"Image file {filepath} does not exist for faction {faction.race}!")

    def test_can_muster_army(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        faction_1 = FACTIONS_BY_RING[1]
        
        # Place a tile owned by faction_0
        grid.place_tile(0, 0, "Plains", faction_0)
        
        # Faction 0 should be able to muster
        self.assertTrue(grid.can_muster_army(faction_0, 0, 0))
        # Faction 1 should NOT be able to muster
        self.assertFalse(grid.can_muster_army(faction_1, 0, 0))
        # Cannot muster on non-existent hex
        self.assertFalse(grid.can_muster_army(faction_0, 0, 1))

    def test_muster_army(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        grid.place_tile(0, 0, "Plains", faction_0)
        
        army = grid.muster_army(faction_0, 0, 0, strength=2)
        self.assertEqual(army.faction, faction_0)
        self.assertEqual(army.hex_location, (0, 0))
        self.assertEqual(army.strength, 2)
        self.assertEqual(army.index, 1)
        
        # Test index incrementing for second army on same tile/for same faction
        army2 = grid.muster_army(faction_0, 0, 0, strength=1)
        self.assertEqual(army2.index, 2)
        
        # Test exception on mustering in unowned hex
        with self.assertRaises(ValueError):
            grid.muster_army(faction_0, 0, 1)

    def test_can_move_army(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        grid.place_tile(0, 0, "Plains", faction_0)
        grid.place_tile(1, 0, "Plains", faction_0)
        grid.place_tile(2, 0, "Plains", faction_0)
        
        army = grid.muster_army(faction_0, 0, 0)
        
        # Can move to adjacent tile (1, 0)
        self.assertTrue(grid.can_move_army(army, 1, 0))
        # Cannot move to non-adjacent tile (2, 0)
        self.assertFalse(grid.can_move_army(army, 2, 0))
        # Cannot move to empty hex with no tile (0, 1)
        self.assertFalse(grid.can_move_army(army, 0, 1))

    def test_move_army(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        grid.place_tile(0, 0, "Plains", faction_0)
        grid.place_tile(1, 0, "Plains", faction_0)
        
        army = grid.muster_army(faction_0, 0, 0)
        grid.move_army(army, 1, 0)
        
        self.assertEqual(army.hex_location, (1, 0))
        # Verify grid registries
        self.assertNotIn((0, 0), grid.armies)
        self.assertIn((1, 0), grid.armies)
        self.assertIn(army, grid.armies[(1, 0)])
        
        # Test exception on invalid move
        with self.assertRaises(ValueError):
            grid.move_army(army, 3, 0)

class TestTurnFlowAndIncome(unittest.TestCase):
    def test_income_calculations(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        
        # Test 0 controlled tiles (minimum 1 gold)
        self.assertEqual(grid.calculate_faction_income(faction_0), 1)
        
        # Test 1 controlled tile
        grid.place_tile(0, 0, "Plains", faction_0)
        self.assertEqual(grid.calculate_faction_income(faction_0), 1)
        
        # Test 2 controlled tiles
        grid.place_tile(1, 0, "Plains", faction_0)
        self.assertEqual(grid.calculate_faction_income(faction_0), 1)
        
        # Test 3 controlled tiles (1 gold)
        grid.place_tile(2, 0, "Plains", faction_0)
        self.assertEqual(grid.calculate_faction_income(faction_0), 1)
        
        # Test 5 controlled tiles (1 gold)
        grid.place_tile(3, 0, "Plains", faction_0)
        grid.place_tile(4, 0, "Plains", faction_0)
        self.assertEqual(grid.calculate_faction_income(faction_0), 1)
        
        # Test 6 controlled tiles (2 gold)
        grid.place_tile(5, 0, "Plains", faction_0)
        self.assertEqual(grid.calculate_faction_income(faction_0), 2)
        
        # Test 9 controlled tiles (3 gold)
        grid.place_tile(6, 0, "Plains", faction_0)
        grid.place_tile(0, 1, "Plains", faction_0)
        grid.place_tile(0, 2, "Plains", faction_0)
        self.assertEqual(grid.calculate_faction_income(faction_0), 3)

    def test_turn_startup_and_phase_progression_logic(self):
        import settings
        from factions import FACTIONS_BY_RING
        from player import Player
        
        human_player = Player(faction=FACTIONS_BY_RING[0])
        bot_player = Player(faction=FACTIONS_BY_RING[1])
        
        players = [human_player, bot_player]
        previous_faction_by_player = [None, None]
        
        state = {
            'current_player_idx': 0,
            'current_faction': None,
            'current_turn_phase': None,
            'log': []
        }
        
        def mock_start_player_turn(player_index):
            state['current_player_idx'] = player_index
            player = players[player_index]
            
            prev_f = previous_faction_by_player[player_index]
            chosen_f = player.choose_next_faction(previous_faction=prev_f)
            previous_faction_by_player[player_index] = chosen_f
            state['current_faction'] = chosen_f
            state['current_turn_phase'] = settings.TURN_PHASE_INCOME
            
            chosen_f.gold = 1
            chosen_f.gold += 1
            state['log'].append(f"player_{player_index}_start")

        def mock_advance_turn_phase():
            p = state['current_turn_phase']
            if p == settings.TURN_PHASE_INCOME:
                state['current_turn_phase'] = settings.TURN_PHASE_MOVE
            elif p == settings.TURN_PHASE_MOVE:
                state['current_turn_phase'] = settings.TURN_PHASE_COMBAT
            elif p == settings.TURN_PHASE_COMBAT:
                state['current_turn_phase'] = settings.TURN_PHASE_CONTROL
            elif p == settings.TURN_PHASE_CONTROL:
                state['current_turn_phase'] = settings.TURN_PHASE_VICTORY
            elif p == settings.TURN_PHASE_VICTORY:
                next_p_idx = 1 - state['current_player_idx']
                mock_start_player_turn(next_p_idx)

        # 1. Start human turn
        mock_start_player_turn(0)
        self.assertEqual(state['current_player_idx'], 0)
        self.assertIsNotNone(state['current_faction'])
        self.assertEqual(state['current_faction'].gold, 2)
        self.assertEqual(state['current_turn_phase'], settings.TURN_PHASE_INCOME)
        
        # 2. Advance phases
        mock_advance_turn_phase()
        self.assertEqual(state['current_turn_phase'], settings.TURN_PHASE_MOVE)
        mock_advance_turn_phase()
        self.assertEqual(state['current_turn_phase'], settings.TURN_PHASE_COMBAT)
        mock_advance_turn_phase()
        self.assertEqual(state['current_turn_phase'], settings.TURN_PHASE_CONTROL)
        mock_advance_turn_phase()
        self.assertEqual(state['current_turn_phase'], settings.TURN_PHASE_VICTORY)
        
        # 3. Advance victory checks -> starts bot turn!
        mock_advance_turn_phase()
        self.assertEqual(state['current_player_idx'], 1)
        self.assertEqual(state['current_turn_phase'], settings.TURN_PHASE_INCOME)
        self.assertEqual(state['current_faction'].gold, 2)
        self.assertEqual(len(state['log']), 2)

    def test_stronghold_centering_and_lookup(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        
        # Place a stronghold for faction_0 at (2, 2)
        grid.place_tile(2, 2, "Plains", faction_0)
        grid.tiles[(2, 2)].is_stronghold = True
        
        # Lookup coord
        coord = grid.find_stronghold_coord(faction_0)
        self.assertEqual(coord, (2, 2))
        
        # Center camera on (2, 2)
        grid.center_on_hex(2, 2)
        lx, ly = grid.get_hex_center(2, 2)
        self.assertEqual(grid.camera_x, -lx)
        self.assertEqual(grid.camera_y, -ly)

class TestControlPhase(unittest.TestCase):
    def test_destroy_stronghold(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        from armies import Army
        from champions import Champion
        
        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        faction_1 = FACTIONS_BY_RING[1]
        
        # Setup stronghold tile for faction_0
        grid.place_tile(2, 2, "Plains", faction_0)
        grid.tiles[(2, 2)].is_stronghold = True
        
        # Setup normal tile owned by faction_0
        grid.place_tile(1, 1, "Plains", faction_0)
        
        # Setup tile owned by faction_1
        grid.place_tile(0, 0, "Woods", faction_1)
        
        # Place armies and champions
        grid.muster_army(faction_0, 2, 2)
        grid.muster_army(faction_0, 1, 1)
        grid.muster_army(faction_1, 0, 0)
        
        champ_0 = Champion(faction=faction_0, q=2, r=2)
        champ_1 = Champion(faction=faction_1, q=0, r=0)
        grid.champions[(2, 2)] = [champ_0]
        grid.champions[(0, 0)] = [champ_1]
        
        # Verify initial state
        self.assertEqual(grid.find_stronghold_coord(faction_0), (2, 2))
        self.assertTrue(grid.tiles[(2, 2)].is_stronghold)
        self.assertEqual(grid.tiles[(2, 2)].owner, faction_0)
        self.assertEqual(grid.tiles[(1, 1)].owner, faction_0)
        self.assertEqual(grid.tiles[(0, 0)].owner, faction_1)
        
        self.assertEqual(len(grid.armies.get((2, 2), [])), 1)
        self.assertEqual(len(grid.armies.get((1, 1), [])), 1)
        self.assertEqual(len(grid.armies.get((0, 0), [])), 1)
        self.assertEqual(len(grid.champions.get((2, 2), [])), 1)
        self.assertEqual(len(grid.champions.get((0, 0), [])), 1)
        
        # Destroy faction_0's stronghold
        grid.destroy_stronghold(faction_0)
        
        # Verify faction_0 elements are cleaned up
        self.assertIsNone(grid.find_stronghold_coord(faction_0))
        self.assertFalse(grid.tiles[(2, 2)].is_stronghold)
        self.assertIsNone(grid.tiles[(2, 2)].owner)
        self.assertIsNone(grid.tiles[(1, 1)].owner)
        
        # Faction 1 should be unaffected
        self.assertEqual(grid.tiles[(0, 0)].owner, faction_1)
        self.assertEqual(len(grid.armies.get((0, 0), [])), 1)
        self.assertEqual(len(grid.champions.get((0, 0), [])), 1)
        
        # Faction 0 units should be completely gone
        self.assertNotIn((2, 2), grid.armies)
        self.assertNotIn((1, 1), grid.armies)
        self.assertNotIn((2, 2), grid.champions)

class TestCombatPhase(unittest.TestCase):
    def test_combat_phase_skipping(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        from armies import Army
        from champions import Champion

        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        faction_1 = FACTIONS_BY_RING[1]
        faction_5 = FACTIONS_BY_RING[5]

        # Initially, no units -> no combat
        self.assertFalse(grid.has_combat_for_faction(faction_0))

        # Place faction_0 army at (0, 0) and faction_1 army at (0, 0)
        grid.add_army(Army(faction_0, 0, 0))
        grid.add_army(Army(faction_1, 0, 0))
        # faction_0 and faction_1 are allied/not opposed -> no combat
        self.assertFalse(grid.has_combat_for_faction(faction_0))

        # Place faction_5 army at (0, 0)
        # Now we have faction_0 and faction_5 at (0, 0). They are opposed.
        grid.add_army(Army(faction_5, 0, 0))
        self.assertTrue(grid.has_combat_for_faction(faction_0))
        self.assertTrue(grid.has_combat_for_faction(faction_5))

        # Test champions
        grid_2 = MapGrid()
        champ_0 = Champion(faction=faction_0, q=1, r=1)
        champ_5 = Champion(faction=faction_5, q=1, r=1)
        grid_2.add_champion(champ_0)
        grid_2.add_champion(champ_5)
        self.assertTrue(grid_2.has_combat_for_faction(faction_0))
        self.assertTrue(grid_2.has_combat_for_faction(faction_5))

class TestArtifacts(unittest.TestCase):
    def test_artifact_claiming(self):
        from map import MapGrid
        from factions import FACTIONS_BY_RING
        from champions import Champion
        from artifacts import Artifact

        grid = MapGrid()
        faction_0 = FACTIONS_BY_RING[0]
        
        # Setup tile with an artifact
        grid.place_tile(0, 0, "Plains", faction_0)
        grid.tiles[(0, 0)].has_artifact = True
        art = Artifact("Flame Sword", "flamesword.jpg")
        grid.tiles[(0, 0)].artifact = art

        # Place champion at (0, 1) on an existing tile
        grid.place_tile(0, 1, "Plains", faction_0)
        champ = Champion(faction=faction_0, q=0, r=1)
        grid.add_champion(champ)

        # Champion should have no artifact initially, and artifact is undiscovered
        self.assertIsNone(champ.artifact)
        self.assertFalse(art.discovered)

        # Move champion to (0, 0)
        grid.move_champion(champ, 0, 0)

        # Champion should now possess the artifact, which is discovered
        self.assertIsNotNone(champ.artifact)
        self.assertEqual(champ.artifact.name, "Flame Sword")
        self.assertTrue(champ.artifact.discovered)

        # Tile should no longer have the artifact
        self.assertFalse(grid.tiles[(0, 0)].has_artifact)
        self.assertIsNone(grid.tiles[(0, 0)].artifact)

if __name__ == "__main__":
    unittest.main()


# Six Nations — Implementation Plan (Updated)

## Summary of Decisions

- **Players**: 1 human vs 1 bot (random moves). Turn order: human → bot → human → ...
- **Secret faction visibility**: Human player's secret faction always shown at top of screen.
- **Diplomacy ring**: Use the existing `DiplomacyRing.jpg` image, displayed top-right.
- **Map**: No zoom or scroll. All 37 hexes always fully visible, statically sized to fit the 2000×1400 window.
- **Trapped sovereign**: Geometrically opposite — enemy units must be in hex directions that are exactly opposite (direction 0 ↔ direction 3, direction 1 ↔ direction 4, direction 2 ↔ direction 5).

---

## Files Involved

| File | Action |
|---|---|
| `settings.py` | Rewrite — Six Nations constants |
| `factions.py` | Rewrite — 6 nations, ring adjacency |
| `armies.py` | Simplify — remove artifact/strength |
| `champions.py` | Simplify + add `Sovereign` class |
| `player.py` | Rewrite — human/bot player logic |
| `map.py` | Major edit — keep geometry, rewrite game logic & draw |
| `main.py` | Full rewrite — game loop, phases, UI |
| `util.py` | Keep mostly as-is (font/image loading) |

---

## Phase 1 — Draw the Game Screen

**Goal**: Launch the app, see a correctly laid-out static screen with the board drawn, the diplomacy ring image top-right, a placeholder for the faction display at top, and cooldown panel at lower-left. No units, no interaction.

### Changes

#### [MODIFY] settings.py
- `SCREEN_WIDTH = 2000`, `SCREEN_HEIGHT = 1400`
- `WINDOW_TITLE = "Six Nations"`
- Nation colors: Yellow `(230,200,50)`, Green `(60,180,80)`, Sky Blue `(80,180,220)`, Cobalt `(50,80,190)`, Magenta `(200,50,160)`, Crimson `(200,40,60)`
- Light tints for starting hex fills (30% opacity equivalents)
- `HEX_SIZE` — computed so 37-hex board fills the screen (approximately 100px radius)
- Remove all old tile/artifact/phase constants

#### [MODIFY] factions.py
- Replace with 6 `Nation` objects (ring indices 0–5)
- `is_ally(other)` — adjacent on ring
- `is_enemy(other)` — not ally and not same
- `color_rgb`, `color_name`, `color_light` properties

#### [MODIFY] map.py
- Keep all geometry methods unchanged
- Rewrite `generate_map()`: place 37 hexes with correct axial coords, assign 4 starting hexes per nation
- Rewrite `draw()`: flat-topped hexes with nation color fills, dark neutral hexes, borders. No units yet.

#### [MODIFY] main.py
- Minimal: init pygame, create `MapGrid`, draw loop, show `DiplomacyRing.jpg` top-right, static top-bar, static lower-left panel.

**Verification**: Run app → see complete board, ring image, panels. No crash.

---

## Phase 2 — Draw Initial Setup (Units on Board)

**Goal**: Starting units are placed and rendered on the board. Each nation's corner hex has a Sovereign + Champion icon; the 3 adjacent hexes each have one Army icon. Unit icons are white background with nation-color symbol (shield / cross-sword / crown).

### Changes

#### [MODIFY] armies.py
- Strip to bare minimum: `faction`, `q`, `r`. No strength/artifact.

#### [MODIFY] champions.py
- Simplify `Champion`: `faction`, `q`, `r`.
- Add `Sovereign` class: `faction`, `q`, `r`.

#### [MODIFY] map.py
- Add `sovereigns` dict alongside `armies` and `champions`.
- Add `add_sovereign`, `remove_sovereign`, `get_sovereigns_at`.
- `generate_map()`: place starting Sovereign, Champion, and 3 Armies per nation.
- `draw()`: render unit icons. Each unit = small white circle. Inside the circle, draw the nation-color symbol:
  - Army → shield outline
  - Champion → cross/sword
  - Sovereign → crown
- Support rendering multiple units in the same hex (stacked/offset layout).
- Human player's secret nation shown at top of screen.

**Verification**: Run app → see all 24 starting units drawn correctly on the board with correct symbols and colors.

---

## Phase 3 — Full Game State & Code Structure

**Goal**: All game state is properly initialized and represented in code. All rule logic functions exist (even if not yet hooked to UI). All data structures are complete.

### Changes

#### [MODIFY] player.py
- `Player(secret_nation, is_bot)` — holds the assigned nation.
- `cooldown: list[int]` — last 2 nation ring indices moved (max 2 entries).
- `add_to_cooldown(nation_index)` — prepend, keep only 2.

#### [MODIFY] map.py
- `is_supported(unit)` → has allied unit in same hex.
- `is_trapped(sovereign)` → unsupported + has enemy units in geometrically opposite neighbor pairs.
- `get_valid_moves(unit)` → returns list of valid (q,r) targets per move rules.
- `get_valid_attacks(unit)` → returns list of valid target hexes per attack rules.
- `apply_move(unit, q, r)` → move unit, enforce rules.
- `apply_attack(attacker, target_q, target_r, target_nation, target_type)` → resolve attack.
- `check_ghost_nations()` → mark nations missing their sovereign.
- `check_win_condition(player)` → True if player's enemies (3 opposite nations) have 2+ destroyed sovereigns.

#### [MODIFY] main.py
- Full game state: `players = [human, bot]`, `current_player_idx`, `global_cooldown`.
- Turn state machine: awaiting move → move made → check win → next player.
- `get_valid_nations_for_player(player)` → nations not on player cooldown or global cooldown.
- Error message state: message + expiry time.

**Verification**: Code review — all classes and functions exist. No runtime import errors. Can print board state to console.

---

## Phase 4 — Human Player UI (Drag-and-Drop)

**Goal**: The human player can drag units. Valid drop targets are highlighted. Illegal moves show an error message. Moves are applied and the board updates.

### Changes

#### [MODIFY] main.py
- Mouse button down: detect which unit is under cursor → begin drag.
- Mouse motion: show ghost (semi-transparent unit icon) under cursor.
- Mouse button up: compute target hex → validate move/attack → apply or reject.
- Error message: displayed upper-left, fades after 3 seconds.
- After human move: update cooldown, set global cooldown, advance to bot turn.
- Highlight valid hexes on drag start (green border = valid move, red = invalid).
- Indicate which nations are on cooldown (lower-left badges, grayed out).
- Nations on cooldown: their units are not draggable.
- **"Peek" secret nation**: Human's secret nation always visible at top of screen (since 1 human).
- After human move, display a "Bot is thinking…" message and trigger bot turn.

**Verification**: Drag a unit → see highlights → drop on valid hex → unit moves. Drop on invalid hex → unit snaps back + error message. Cooldown badges update.

---

## Phase 5 — Game Mechanics

**Goal**: All attack/move rules from the spec are fully implemented and enforced.

### Move rules (non-attack):
- Army: adjacent hex with no army and no enemy units.
- Sovereign: adjacent hex with no enemy unit.
- Champion: adjacent hex with no enemy unit.
- Recruit army: place new army on one of 4 starting hexes (if < 3 armies, hex free).
- Promote champion: promote army on starting hex to champion (if champion lost).

### Attack resolution:
- Army vs unsupported army: both destroyed.
- Army vs supported army (unsupported attacker): illegal.
- Supported army vs unsupported army: enemy destroyed, attacker advances.
- Supported army vs supported army: both destroyed.
- Army cannot attack champion.
- Army vs unsupported trapped sovereign: sovereign destroyed, attacker advances.
- Champion vs army: per support rules (see spec).
- Champion vs champion: per support rules (see spec).
- Champion vs sovereign: per support rules (see spec, including support-by-champion shield).
- Forward movement after attack: attacker moves into vacated hex unless blocked.

### Ghost nation rules:
- Cannot recruit armies or promote champions.
- Units still playable.

### Win/loss detection:
- Win: 2 of player's 3 enemy sovereigns destroyed.
- Lose: player's own secret nation's sovereign destroyed.
- Tie: two players simultaneously meet win condition (both had adjacent secret nations).

### Changes

#### [MODIFY] map.py
- Fully implement all validation and resolution logic.
- `is_nation_on_cooldown(nation, player, global_cooldown)`.

#### [MODIFY] main.py
- After each move: run `check_ghost_nations()`, `check_win_condition()`.
- Display game-over screen with winner/loser info.

**Verification**: Play through multiple scenarios manually. Verify that illegal moves are blocked, legal attacks resolve correctly, ghost nations work, win/loss triggers.

---

## Phase 6 — Bot Player

**Goal**: Bot makes valid random moves on its turn.

### Changes

#### [MODIFY] player.py or main.py (bot logic)
- `run_bot_turn(bot_player, map_grid, global_cooldown)`:
  1. Find all nations not on bot cooldown or global cooldown.
  2. For each eligible nation, collect all units.
  3. For each unit, collect all valid moves and attacks.
  4. Randomly pick one from the full pool of legal actions.
  5. Apply it.
  6. If no legal actions available: skip turn (or attempt recruit/promote).

**Verification**: Let the bot play several turns — confirm it never makes an illegal move, cooldowns update correctly, the game can reach a win/loss state.

---

## Map Layout Reference

37 hexes in flat-top axial layout. Ring 3 has 18 hexes; its 6 corners are:

```
(3,0)  (0,3)  (-3,3)  (-3,0)  (0,-3)  (3,-3)
```

These are the Sovereign/Champion start hexes for nations 0–5. Each nation's 3 army hexes are the adjacent hexes (within ring 2 or ring 3) that are closest to that corner.

Nations are placed in ring order: Yellow(0)=`(3,0)`, Green(1)=`(0,3)`, SkyBlue(2)=`(-3,3)`, Cobalt(3)=`(-3,0)`, Magenta(4)=`(0,-3)`, Crimson(5)=`(3,-3)`.

---

## Verification Plan

Each phase has its own manual check noted above. To run:
```
.venv/bin/python main.py
```

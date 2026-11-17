# Wedgie Snake — Specification v0.3

## Goal
A minimal Nokia-inspired Snake game for Wedgie, with green snake, red apple, and incremental screen updates.

## Platform
- Wedgie RP2040, MicroPython, 240x240 16-color LCD.
- `LCD.fill_rect` edits the framebuffer; `LCD.show_rect` flushes only changed tiles.
- `Keys.pressed()` sampled continuously; `time.sleep_ms()` yields to firmware.
- `save.load('best', None)` and `save.store('best', value)` persist best length.

## Rules and screen
- 20 columns x 19 rows of 12px cells, plus a 12px bottom score strip.
- Score strip displays LEN and BEST; refresh only after eating an apple.
- Starts with length 3, facing right, moving every 250ms.
- One red apple on an empty cell. Each apple adds one segment.
- Bright green head, darker green body, dark background.
- Joystick directions only during play; Y toggles pause/resume.
- Wall or body collision ends the round. Moving into a tail cell vacated on the same tick is legal.
- A on the standard game-over page starts another round.
- Filling the board ends in a win.

## Storage
- Best is the highest snake length, not apples eaten.
- Read once at app initialization, detecting whether a save exists.
- Write only on death/win, and only if no existing save or finished length exceeds the persisted best.
- Never write on each tick, apple, pause, or restart.
- Save is managed by Wedgie's save API; no manual file writes.
- If saving fails, gameplay still works; print a diagnostic.

## Memory and rendering
- Preallocate a fixed ring buffer of 380 unsigned 16-bit cell IDs and a 380-byte occupancy map.
- Every tick updates head/tail and occupancy; body is not redrawn.
- When head is visually distinct, recolor the previous head tile too; flush at most three snake tiles on an ordinary move.
- On apple consumption, retain tail, add apple in a free cell, refresh score strip.
- Full lcd.show() on new round and after resuming from pause page, not ordinary movement.
- No per-pixel Python loops, no growing lists during gameplay, no network or secure-chip access.

## Acceptance tests
- Initial length 3 and correct orientation.
- Apples spawn on empty cells; each grows exactly one cell.
- No 180-degree reversal; one queued turn per tick.
- Legal entry into vacating tail cell; collision with other occupied cells.
- No horizontal wrap; walls end game.
- No full-screen flush on ordinary moves; HUD changes only on growth.
- First completed round creates a save; equal/lower scores do not write; higher score writes once.
- Y pauses and resumes; clock resets on resume.
- Best persists across rounds and restarts.
- Test in wedgie.dev/code, then virtual Wedgie, then hardware.

## Source
Derived from the user-supplied wedgie-code and wedgie-virtual documents.

## Wall-turn grace (v0.4)

- If the next movement would cross a wall, hold the snake at its current cell for up to 120 ms.
- A legal perpendicular joystick turn during that window moves the snake immediately, without moving into the wall.
- If the window expires, the round ends normally.
- This applies only to walls, not collisions with the snake's own body.
- A pause freezes the game; resuming starts a fresh 120 ms grace window if one was active.
- No display update or save write is needed during the grace period.
- This is a playability choice inspired by accounts of the original Nokia game, not a verified Nokia timing value.
- Hardware acceptance tests: late turn succeeds, no turn dies, reversal fails, self-collision still kills, pause/resume works at a wall.

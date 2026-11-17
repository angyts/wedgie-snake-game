"""Minimal partial-refresh Snake for Wedgie MicroPython."""
import time
import random
from array import array
from lcd import LCD, Keys, color
import ui
import save

WIDTH = 20
HEIGHT = 19
CELLS = WIDTH * HEIGHT
TILE = 12
HUD_Y = HEIGHT * TILE
# Milliseconds per move. Five apples unlock each faster level.
# These are Wedgie tuning values, not measured Nokia firmware timings.
SPEED_MS = (230, 210, 190, 170, 150, 135, 120, 110, 100, 90)
FRAME_MS = 25
GOLD_CHANCE = 10
GOLD_LIFETIME_MS = 6000
GOLD_GROWTH = 5
WALL_GRACE_MS = 100  # Allow a last-second 90-degree turn at a wall.
BG = color(13, 23, 15)
HEAD = color(110, 255, 75)
BODY = color(35, 195, 65)
APPLE = color(245, 65, 55)
APPLE_SHADE = color(180, 28, 35)
APPLE_SHINE = color(255, 220, 180)
APPLE_LEAF = color(35, 195, 65)
APPLE_STEM = color(95, 60, 30)
GOLD = color(255, 205, 35)
GOLD_SHADE = color(180, 125, 20)
GOLD_SHINE = color(255, 245, 185)
HUD_BG = color(8, 10, 24)
EYE = color(8, 20, 10)
TONGUE = color(255, 100, 135)

UP, RIGHT, DOWN, LEFT = -WIDTH, 1, WIDTH, -1
DIRECTIONS = {"up": UP, "right": RIGHT, "down": DOWN, "left": LEFT}


class Game:
    def __init__(self):
        self.cells = array('H', [0] * CELLS)
        self.occupied = bytearray(CELLS)
        stored = save.load('best', None)
        self.has_save = stored is not None
        self.best = max(3, int(stored)) if self.has_save else 3
        self.saved_best = self.best
        self.reset()

    def reset(self):
        for i in range(CELLS):
            self.occupied[i] = 0
        y = HEIGHT // 2
        self.length = 3
        self.tail_index = 0
        self.head_index = 2
        for i in range(3):
            cell = y * WIDTH + 8 + i
            self.cells[i] = cell
            self.occupied[cell] = 1
        self.direction = RIGHT
        self.pending = None
        self.over = False
        self.won = False
        self.apple = self.new_apple()
        self.gold = -1
        self.gold_deadline = None
        self.growth_pending = 0
        self.red_eaten = 0

    def new_apple(self, exclude=-1):
        available = CELLS - self.length
        if exclude >= 0 and not self.occupied[exclude]:
            available -= 1
        if available == 0:
            return -1
        target = random.randrange(available)
        for cell in range(CELLS):
            if not self.occupied[cell] and cell != exclude:
                if target == 0:
                    return cell
                target -= 1
        return -1

    def turn(self, key):
        proposed = DIRECTIONS.get(key)
        if proposed is not None and self.pending is None and proposed != -self.direction and proposed != self.direction:
            self.pending = proposed

    def step(self):
        """Return (old_tail_or_None, old_head, new_head, ate, over)."""
        if self.over:
            return (None, None, None, False, True)
        if self.pending is not None:
            self.direction = self.pending
            self.pending = None
        old_head = self.cells[self.head_index]
        x = old_head % WIDTH
        y = old_head // WIDTH
        nx = x + (1 if self.direction == RIGHT else -1 if self.direction == LEFT else 0)
        ny = y + (1 if self.direction == DOWN else -1 if self.direction == UP else 0)
        if nx < 0 or nx >= WIDTH or ny < 0 or ny >= HEIGHT:
            self.over = True
            return (None, old_head, None, False, True)
        next_cell = ny * WIDTH + nx
        ate = next_cell == self.apple
        ate_gold = next_cell == self.gold
        growing = ate or ate_gold or self.growth_pending > 0
        old_tail = self.cells[self.tail_index]
        if self.occupied[next_cell] and (growing or next_cell != old_tail):
            self.over = True
            return (None, old_head, None, False, True)
        removed = None
        if not growing:
            removed = old_tail
            self.occupied[old_tail] = 0
            self.tail_index = (self.tail_index + 1) % CELLS
        else:
            self.length += 1
            if self.growth_pending:
                self.growth_pending -= 1
        self.head_index = (self.head_index + 1) % CELLS
        self.cells[self.head_index] = next_cell
        self.occupied[next_cell] = 1
        if ate and self.growth_pending:
            # Red food adds one more future growth when already growing.
            self.growth_pending += 1
        if ate_gold:
            self.gold = -1
            self.growth_pending += GOLD_GROWTH - 1
        if ate:
            self.red_eaten += 1
            self.apple = self.new_apple(self.gold)
            if self.apple < 0:
                self.won = True
                self.over = True
        if self.length == CELLS:
            self.won = True
            self.over = True
        return (removed, old_head, next_cell, growing, self.over)


def speed_level(length):
    """Speed level 1-10, increasing every five apples."""
    return min((length - 3) // 5, len(SPEED_MS) - 1) + 1


def move_interval(length):
    """Return the movement interval for this snake length."""
    return SPEED_MS[speed_level(length) - 1]


def hits_wall(game, direction):
    """Would the next movement leave the board?"""
    head = game.cells[game.head_index]
    x = head % WIDTH
    y = head // WIDTH
    return ((direction == LEFT and x == 0)
            or (direction == RIGHT and x == WIDTH - 1)
            or (direction == UP and y == 0)
            or (direction == DOWN and y == HEIGHT - 1))


def tile(lcd, cell, ink):
    lcd.fill_rect((cell % WIDTH) * TILE, (cell // WIDTH) * TILE, TILE, TILE, ink)


def head(lcd, cell, direction):
    """Draw the face and the base of the forked tongue inside the head."""
    tile(lcd, cell, HEAD)
    x = (cell % WIDTH) * TILE
    y = (cell // WIDTH) * TILE

    if direction == RIGHT:
        eyes = ((7, 2), (7, 8))
        base = (10, 5, 2, 2)
    elif direction == LEFT:
        eyes = ((3, 2), (3, 8))
        base = (0, 5, 2, 2)
    elif direction == UP:
        eyes = ((2, 3), (8, 3))
        base = (5, 0, 2, 2)
    else:
        eyes = ((2, 7), (8, 7))
        base = (5, 10, 2, 2)

    for ex, ey in eyes:
        lcd.fill_rect(x + ex, y + ey, 2, 2, EYE)
    lcd.fill_rect(x + base[0], y + base[1], base[2], base[3], TONGUE)


def tongue_tip(lcd, game):
    """Fork one pixel into the free cell ahead. Return that cell or None.

    Do not paint over the apple, body, walls, or the score strip.
    """
    cell = game.cells[game.head_index]
    direction = game.direction
    if hits_wall(game, direction):
        return None

    ahead = cell + direction
    if game.occupied[ahead] or ahead == game.apple:
        return None

    x = (ahead % WIDTH) * TILE
    y = (ahead // WIDTH) * TILE
    if direction == RIGHT:
        tips = ((0, 4), (0, 7))
    elif direction == LEFT:
        tips = ((11, 4), (11, 7))
    elif direction == UP:
        tips = ((4, 11), (7, 11))
    else:
        tips = ((4, 0), (7, 0))

    for tx, ty in tips:
        lcd.fill_rect(x + tx, y + ty, 1, 1, TONGUE)
    return ahead


def tail(lcd, cell, neighbor):
    """Draw a tapered tail pointing away from the next body segment."""
    tile(lcd, cell, BG)
    x = (cell % WIDTH) * TILE
    y = (cell // WIDTH) * TILE
    dx = (neighbor % WIDTH) - (cell % WIDTH)
    dy = (neighbor // WIDTH) - (cell // WIDTH)

    if dx == 1:  # Body continues to the right.
        lcd.fill_rect(x + 5, y + 3, 7, 6, BODY)
        lcd.fill_rect(x + 2, y + 5, 3, 2, BODY)
    elif dx == -1:
        lcd.fill_rect(x, y + 3, 7, 6, BODY)
        lcd.fill_rect(x + 7, y + 5, 3, 2, BODY)
    elif dy == 1:
        lcd.fill_rect(x + 3, y + 5, 6, 7, BODY)
        lcd.fill_rect(x + 5, y + 2, 2, 3, BODY)
    else:
        lcd.fill_rect(x + 3, y, 6, 7, BODY)
        lcd.fill_rect(x + 5, y + 7, 2, 3, BODY)


def draw_apple(lcd, cell):
    """Draw a tiny red apple with a leaf, stem and highlight."""
    tile(lcd, cell, BG)
    x = (cell % WIDTH) * TILE
    y = (cell // WIDTH) * TILE
    lcd.fill_rect(x + 3, y + 4, 7, 7, APPLE_SHADE)
    lcd.fill_rect(x + 2, y + 5, 8, 5, APPLE)
    lcd.fill_rect(x + 4, y + 3, 5, 7, APPLE)
    lcd.fill_rect(x + 5, y + 1, 2, 3, APPLE_STEM)
    lcd.fill_rect(x + 7, y + 1, 3, 2, APPLE_LEAF)
    lcd.fill_rect(x + 4, y + 5, 2, 2, APPLE_SHINE)


def draw_gold(lcd, cell):
    """Draw a golden apple, matching the red apple's silhouette."""
    tile(lcd, cell, BG)
    x = (cell % WIDTH) * TILE
    y = (cell // WIDTH) * TILE
    lcd.fill_rect(x + 3, y + 4, 7, 7, GOLD_SHADE)
    lcd.fill_rect(x + 2, y + 5, 8, 5, GOLD)
    lcd.fill_rect(x + 4, y + 3, 5, 7, GOLD)
    lcd.fill_rect(x + 5, y + 1, 2, 3, APPLE_STEM)
    lcd.fill_rect(x + 7, y + 1, 3, 2, APPLE_LEAF)
    lcd.fill_rect(x + 4, y + 5, 2, 2, GOLD_SHINE)


def push(lcd, cell):
    lcd.show_rect((cell % WIDTH) * TILE, (cell // WIDTH) * TILE, TILE, TILE)


def draw_hud(lcd, game):
    """Draw the status strip into the framebuffer."""
    lcd.fill_rect(0, HUD_Y, 240, 12, HUD_BG)
    lcd.text('LENGTH %03d' % game.length, 3, HUD_Y + 2, ui.WHITE)
    lcd.text('LV%d' % speed_level(game.length), 130, HUD_Y + 2, ui.WHITE)
    lcd.text('BEST %03d' % game.best, 170, HUD_Y + 2, ui.WHITE)


def hud(lcd, game):
    draw_hud(lcd, game)
    lcd.show(HUD_Y, 240)


def initial_draw(lcd, game):
    lcd.fill(BG)
    for i in range(game.length):
        cell = game.cells[(game.tail_index + i) % CELLS]
        if i == 0:
            neighbor = game.cells[(game.tail_index + 1) % CELLS]
            tail(lcd, cell, neighbor)
        elif i == game.length - 1:
            head(lcd, cell, game.direction)
        else:
            tile(lcd, cell, BODY)
    if game.apple >= 0:
        draw_apple(lcd, game.apple)
    if game.gold >= 0:
        draw_gold(lcd, game.gold)
    tongue_tip(lcd, game)
    draw_hud(lcd, game)
    lcd.show()


def finish(lcd, keys, game):
    if not game.has_save or game.length > game.saved_best:
        game.best = game.length
        try:
            save.store('best', game.best)
            game.saved_best = game.best
            game.has_save = True
        except OSError as exc:
            print('Could not save best length:', exc)
    ui.page(lcd, 'You Win' if game.won else 'Game Over',
            [('Length %d' % game.length, ui.INK),
             ('Best %d' % game.best, ui.MUTED)], '{g} play again')
    while True:
        for key in keys.pressed():
            if key == 'A':
                return
        time.sleep_ms(FRAME_MS)


def run():
    lcd = LCD()
    keys = Keys()
    game = Game()
    while True:
        game.reset()
        initial_draw(lcd, game)
        last_move = time.ticks_ms()
        paused = False
        wall_deadline = None
        gold_paused_at = None
        previous_tip = None
        # The initial full draw includes the protruding tongue.
        if not hits_wall(game, game.direction):
            ahead = game.cells[game.head_index] + game.direction
            if not game.occupied[ahead] and ahead != game.apple:
                previous_tip = ahead
        while not game.over:
            for key in keys.pressed():
                if key == 'Y':
                    paused = not paused
                    if paused:
                        gold_paused_at = time.ticks_ms()
                        ui.page(lcd, 'PAUSED',
                                [('Snake length %d' % game.length, ui.INK)],
                                '{r} resume', show=False)
                        # Keep the standard Wedgie page, but make PAUSED red.
                        ui.title(lcd, 'PAUSED', 72, c=ui.RED)
                        lcd.show()
                    else:
                        if game.gold >= 0 and gold_paused_at is not None:
                            elapsed = time.ticks_diff(time.ticks_ms(), gold_paused_at)
                            game.gold_deadline = time.ticks_add(game.gold_deadline, elapsed)
                        gold_paused_at = None
                        initial_draw(lcd, game)
                        previous_tip = None
                        if not hits_wall(game, game.direction):
                            ahead = game.cells[game.head_index] + game.direction
                            if not game.occupied[ahead] and ahead != game.apple:
                                previous_tip = ahead
                        last_move = time.ticks_ms()
                        if wall_deadline is not None:
                            wall_deadline = time.ticks_add(last_move, WALL_GRACE_MS)
                elif not paused:
                    game.turn(key)
            if paused:
                time.sleep_ms(FRAME_MS)
                continue
            now = time.ticks_ms()
            if game.gold >= 0 and time.ticks_diff(now, game.gold_deadline) >= 0:
                expired = game.gold
                game.gold = -1
                game.gold_deadline = None
                tile(lcd, expired, BG)
                if previous_tip == expired:
                    previous_tip = tongue_tip(lcd, game)
                push(lcd, expired)
            if wall_deadline is not None:
                # A wall is imminent. Give the player one last chance to turn.
                if game.pending is not None and not hits_wall(game, game.pending):
                    wall_deadline = None
                elif time.ticks_diff(now, wall_deadline) >= 0:
                    game.over = True
                    continue
                else:
                    time.sleep_ms(FRAME_MS)
                    continue
            elif time.ticks_diff(now, last_move) >= move_interval(game.length):
                direction = game.pending if game.pending is not None else game.direction
                if hits_wall(game, direction):
                    wall_deadline = time.ticks_add(now, WALL_GRACE_MS)
                    time.sleep_ms(FRAME_MS)
                    continue
            else:
                time.sleep_ms(FRAME_MS)
                continue

            last_move = now
            old_gold = game.gold
            old_red = game.apple
            removed, old_head, new_head, grew, _ = game.step()
            if new_head is not None:
                # Remove the previous tongue's two outside pixels first.
                # It may be in a different cell if the snake just turned.
                old_tip = previous_tip
                if old_tip is not None:
                    tile(lcd, old_tip, BG)

                # Update the framebuffer, then send each changed tile once.
                tile(lcd, old_head, BODY)
                if removed is not None and removed != new_head:
                    tile(lcd, removed, BG)

                # The tail's tapered shape must follow the new tail position.
                tail_cell = game.cells[game.tail_index]
                next_body = game.cells[(game.tail_index + 1) % CELLS]
                tail(lcd, tail_cell, next_body)
                head(lcd, new_head, game.direction)

                if old_gold >= 0 and game.gold < 0:
                    game.gold_deadline = None
                if game.apple >= 0 and game.apple != old_red:
                    draw_apple(lcd, game.apple)
                    if game.gold < 0 and random.randrange(100) < GOLD_CHANCE:
                        game.gold = game.new_apple(game.apple)
                        if game.gold == old_tip:
                            # Avoid covering the forked tongue in front of the head.
                            game.gold = -1
                        if game.gold >= 0:
                            game.gold_deadline = time.ticks_add(now, GOLD_LIFETIME_MS)
                            draw_gold(lcd, game.gold)

                # The new tongue may reach one pixel into the next free cell.
                previous_tip = tongue_tip(lcd, game)

                # Flush only changed tiles, including the old/new tongue cells.
                changed = (old_head, removed, tail_cell, new_head, old_tip, previous_tip,
                           game.apple if game.apple != old_red else None,
                           game.gold if game.gold >= 0 and game.gold != old_gold else None)
                for i, cell in enumerate(changed):
                    if cell is not None and cell not in changed[:i]:
                        push(lcd, cell)
                if grew:
                    if game.length > game.best:
                        game.best = game.length
                    hud(lcd, game)
            time.sleep_ms(FRAME_MS)
        finish(lcd, keys, game)

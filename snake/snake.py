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
STEP_MS = 250
FRAME_MS = 25
BG = color(13, 23, 15)
HEAD = color(110, 255, 75)
BODY = color(35, 195, 65)
APPLE = color(245, 65, 55)
HUD_BG = color(8, 10, 24)

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

    def new_apple(self):
        available = CELLS - self.length
        if available == 0:
            return -1
        target = random.randrange(available)
        for cell in range(CELLS):
            if not self.occupied[cell]:
                if target == 0:
                    return cell
                target -= 1
        return -1

    def turn(self, key):
        proposed = DIRECTIONS.get(key)
        if proposed is not None and self.pending is None and proposed != -self.direction:
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
        old_tail = self.cells[self.tail_index]
        if self.occupied[next_cell] and (ate or next_cell != old_tail):
            self.over = True
            return (None, old_head, None, False, True)
        removed = None
        if not ate:
            removed = old_tail
            self.occupied[old_tail] = 0
            self.tail_index = (self.tail_index + 1) % CELLS
        else:
            self.length += 1
        self.head_index = (self.head_index + 1) % CELLS
        self.cells[self.head_index] = next_cell
        self.occupied[next_cell] = 1
        if ate:
            self.apple = self.new_apple()
            if self.apple < 0:
                self.won = True
                self.over = True
        return (removed, old_head, next_cell, ate, self.over)


def tile(lcd, cell, ink):
    lcd.fill_rect((cell % WIDTH) * TILE, (cell // WIDTH) * TILE, TILE, TILE, ink)


def push(lcd, cell):
    lcd.show_rect((cell % WIDTH) * TILE, (cell // WIDTH) * TILE, TILE, TILE)


def hud(lcd, game):
    lcd.fill_rect(0, HUD_Y, 240, 12, HUD_BG)
    lcd.text('LEN %03d' % game.length, 2, HUD_Y + 2, ui.WHITE)
    lcd.text('BEST %03d' % game.best, 137, HUD_Y + 2, ui.WHITE)
    lcd.show(HUD_Y, 240)


def initial_draw(lcd, game):
    lcd.fill(BG)
    for i in range(game.length):
        cell = game.cells[(game.tail_index + i) % CELLS]
        tile(lcd, cell, HEAD if i == game.length - 1 else BODY)
    tile(lcd, game.apple, APPLE)
    lcd.fill_rect(0, HUD_Y, 240, 12, HUD_BG)
    lcd.text('LEN %03d' % game.length, 2, HUD_Y + 2, ui.WHITE)
    lcd.text('BEST %03d' % game.best, 137, HUD_Y + 2, ui.WHITE)
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
        while not game.over:
            for key in keys.pressed():
                if key == 'Y':
                    paused = not paused
                    if paused:
                        ui.page(lcd, 'Paused', [('Length %d' % game.length, ui.INK)], '{r} resume')
                    else:
                        initial_draw(lcd, game)
                        last_move = time.ticks_ms()
                elif not paused:
                    game.turn(key)
            if paused:
                time.sleep_ms(FRAME_MS)
                continue
            now = time.ticks_ms()
            if time.ticks_diff(now, last_move) >= STEP_MS:
                last_move = now
                removed, old_head, new_head, ate, _ = game.step()
                if new_head is not None:
                    tile(lcd, old_head, BODY)
                    if removed is not None and removed != new_head:
                        tile(lcd, removed, BG)
                    tile(lcd, new_head, HEAD)
                    push(lcd, old_head)
                    if removed is not None and removed != new_head and removed != old_head:
                        push(lcd, removed)
                    if new_head != old_head:
                        push(lcd, new_head)
                    if ate:
                        if game.apple >= 0:
                            tile(lcd, game.apple, APPLE)
                            push(lcd, game.apple)
                        if game.length > game.best:
                            game.best = game.length
                        hud(lcd, game)
            time.sleep_ms(FRAME_MS)
        finish(lcd, keys, game)

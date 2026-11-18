"""Host-side regression tests for Wedgie Snake. Run: python -m unittest discover -s tests -v"""
import importlib.util
import pathlib
import random
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
lcd_module = types.ModuleType("lcd")
lcd_module.color = lambda *rgb: tuple(rgb)
lcd_module.LCD = object
lcd_module.Keys = object
ui_module = types.ModuleType("ui")
ui_module.WHITE = 1
ui_module.INK = 2
ui_module.MUTED = 3
save_module = types.ModuleType("save")
save_module.load = lambda *args: None
save_module.store = lambda *args: None
sys.modules.update({"lcd": lcd_module, "ui": ui_module, "save": save_module})
spec = importlib.util.spec_from_file_location("wedgie_snake_under_test", ROOT / "snake" / "snake.py")
snake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snake)


class FakeLCD:
    """Track the framebuffer tile touched by every fill_rect."""
    def __init__(self):
        self.pixels = {}

    def fill_rect(self, x, y, w, h, ink):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.pixels[(xx, yy)] = ink

    def show_rect(self, *args):
        pass


class SnakeTests(unittest.TestCase):
    def assert_consistent(self, game):
        body = [game.cells[(game.tail_index + i) % snake.CELLS]
                for i in range(game.length)]
        self.assertEqual(len(body), len(set(body)))
        self.assertEqual(set(body), {i for i, flag in enumerate(game.occupied) if flag})
        self.assertEqual(game.length, sum(game.occupied))
        if game.apple >= 0:
            self.assertLess(game.apple, snake.CELLS)
            self.assertFalse(game.occupied[game.apple])
            self.assertNotEqual(game.apple, game.gold)

    def test_100000_spawns(self):
        game = snake.Game()
        for _ in range(100000):
            game.apple = game.new_apple()
            self.assert_consistent(game)

    def test_excluded_gold_cell(self):
        game = snake.Game()
        for _ in range(1000):
            gold = game.new_apple()
            self.assertNotEqual(game.new_apple(gold), gold)

    def test_successive_apples(self):
        game = snake.Game()
        for _ in range(2):
            next_cell = game.cells[game.head_index] + snake.RIGHT
            game.apple = next_cell
            game.step()
            self.assert_consistent(game)
            self.assertGreaterEqual(game.apple, 0)
        self.assertEqual(game.length, 5)

    def test_tail_cell_is_legal_without_growth(self):
        game = snake.Game()
        # A four-cell square, head immediately before the tail.
        body = [21, 22, 42, 41]
        game.occupied[:] = bytes(snake.CELLS)
        for i, cell in enumerate(body):
            game.cells[i] = cell
            game.occupied[cell] = 1
        game.length = 4
        game.tail_index = 0
        game.head_index = 3
        game.direction = snake.UP
        game.apple = 100
        game.step()
        self.assertFalse(game.over)
        self.assert_consistent(game)

    def test_near_full_board_and_gold_exclusion(self):
        game = snake.Game()
        game.occupied[:] = bytes([1]) * snake.CELLS
        game.length = snake.CELLS - 2
        free = (12, 15)
        for cell in free:
            game.occupied[cell] = 0
        self.assertEqual(game.new_apple(12), 15)
        self.assertEqual(game.new_apple(15), 12)
        game.occupied[15] = 1
        game.length += 1
        self.assertEqual(game.new_apple(12), -1)
        self.assertEqual(game.new_apple(), 12)

    def test_ring_buffer_wrap(self):
        game = snake.Game()
        # Repeatedly walk a short straight path by relocating a valid
        # three-cell snake, while retaining advancing ring indices.
        for _ in range(snake.CELLS + 10):
            game.occupied[:] = bytes(snake.CELLS)
            game.length = 3
            game.tail_index = (game.head_index - 2) % snake.CELLS
            for offset, cell in enumerate((100, 101, 102)):
                game.cells[(game.tail_index + offset) % snake.CELLS] = cell
                game.occupied[cell] = 1
            game.direction = snake.RIGHT
            game.pending = None
            game.apple = 200
            game.over = False
            game.step()
            self.assert_consistent(game)

    def test_apple_draw_has_visible_pixels(self):
        lcd = FakeLCD()
        snake.draw_apple(lcd, 33)
        x, y = (33 % snake.WIDTH) * snake.TILE, (33 // snake.WIDTH) * snake.TILE
        self.assertEqual(lcd.pixels[(x + 4, y + 5)], snake.APPLE_SHINE)

    def test_random_gameplay_invariants(self):
        rng = random.Random(20261118)
        for _ in range(250):
            game = snake.Game()
            for _ in range(200):
                if game.over:
                    break
                game.turn(rng.choice(("up", "right", "down", "left")))
                game.step()
                self.assert_consistent(game)


if __name__ == "__main__":
    unittest.main()

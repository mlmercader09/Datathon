"""Cangur trainer as an App Lab app: the web page on port 7000, and the LED matrix.

The trainer's logic is the same code as trainer/ in the repository: applab/install.sh
copies it into python/trainer/, with the data and the images. Don't edit the copies:
edit trainer/ and run install.sh again.

What the matrix shows:
  * After an answer: a tick or a cross, for 1.5 seconds
  * Then: the student's level as a digit, with a bar along the bottom row
"""
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from arduino.app_bricks.web_ui import WebUI  # noqa: E402
from arduino.app_utils import App, Bridge  # noqa: E402

from trainer import led  # noqa: E402
from trainer.bank import Bank  # noqa: E402
from trainer.trainer import Trainer  # noqa: E402

DATA = os.path.join(HERE, "data")
IMAGES = os.path.join(os.path.dirname(HERE), "assets", "images")
RESULT_SECONDS = 1.5

# ---- the LED matrix (8 rows x 13 columns, brightness 0 to 7) ----------------

DIGITS = {
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
}

TICK = [
    ".............",
    "...........#.",
    "..........##.",
    ".........##..",
    "..#.....##...",
    "..##...##....",
    "...##.##.....",
    "....###......",
]

CROSS = [
    "...#.....#...",
    "....#...#....",
    ".....#.#.....",
    "......#......",
    ".....#.#.....",
    "....#...#....",
    "...#.....#...",
    ".............",
]


def draw(rows):
    grid = np.zeros((8, 13), dtype=np.uint8)
    for r, line in enumerate(rows):
        for c, pixel in enumerate(line):
            if pixel == "#":
                grid[r, c] = 7
    Bridge.call("draw", grid.tobytes())


def level_rows(level):
    """The level as a digit in the middle, and a bar on the bottom row: one more column per level."""
    rows = ["." * 13 for _ in range(8)]
    for r, line in enumerate(DIGITS.get(str(level), DIGITS["?"])):
        rows[r] = "...." + line + "...."
    filled = round((int(level) + 1) * 13 / 8) if str(level).isdigit() else 0
    rows[7] = "#" * filled + "." * (13 - filled)
    return rows


class Matrix:
    """Receives the trainer's led.send() calls and decides what to draw, and for how long."""

    def __init__(self):
        self.level = None
        self.timer = None
        self.lock = threading.Lock()

    def send(self, command, value):
        with self.lock:
            if command == "result":
                if self.timer:
                    self.timer.cancel()
                draw(TICK if value else CROSS)
                # Show the level again once the tick or cross has been seen
                self.timer = threading.Timer(RESULT_SECONDS, self._show_level)
                self.timer.daemon = True
                self.timer.start()
            elif command == "level":
                self.level = value
                if not (self.timer and self.timer.is_alive()):
                    draw(level_rows(value))

    def _show_level(self):
        with self.lock:
            self.timer = None
            if self.level is not None:
                draw(level_rows(self.level))


matrix = Matrix()
led.send = matrix.send  # the trainer now draws on the board instead of printing

# ---- the trainer and the web API --------------------------------------------

bank = Bank([os.path.join(DATA, "train.jsonl"), os.path.join(DATA, "val.jsonl")],
            index_db=os.path.join(DATA, "index.db"), images=IMAGES)
trainer = Trainer(bank, db_path=os.path.join(DATA, "students.db"))
print(f"{len(bank.ids)} problems, levels {bank.levels}, similarity: {bank.similarity_source}", flush=True)


# The path parameters arrive by name, so the handlers keep these exact argument names.
# They return an error message instead of crashing the app.
def start(name: str, language: str, level: str):
    try:
        return trainer.start(name, language, int(level))
    except (KeyError, ValueError, RuntimeError) as e:
        return {"error": str(e)}


def answer(name: str, choice: str, seconds: str):
    try:
        if choice not in ("A", "B", "C", "D", "E"):
            raise ValueError("choose A to E")
        return trainer.answer(name, choice, float(seconds))
    except (KeyError, ValueError, RuntimeError) as e:
        return {"error": str(e)}


ui = WebUI()
ui.expose_api("GET", "/api/start/{name}/{language}/{level}", start)
ui.expose_api("GET", "/api/answer/{name}/{choice}/{seconds}", answer)

draw(level_rows("?"))  # waiting for a student
App.run()

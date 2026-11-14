"""What the LED matrix shows. On a laptop it only prints.

On the board, inside an App Lab app, replace send() with a call over the Bridge
to the sketch that draws on the 8x13 matrix, for example:

    from arduino.app_utils import Bridge
    def send(command, value):
        Bridge.call(command, value)

and in sketch.ino register "result" (1 = tick, 0 = cross) and "level" (0 to 7).
The unoq-hardware-ui skill in .skills/ explains the Bridge and the sketch.
"""
import os

QUIET = os.environ.get("TRAINER_QUIET") == "1"


def send(command, value):
    if not QUIET:
        print(f"[LED] {command} = {value}")


def show_result(correct):
    send("result", 1 if correct else 0)


def show_level(level):
    send("level", int(level))

"""The adaptive trainer: which problem comes next, and which hint to show.

Rules (no language model in the loop, so every step takes well under a second):
  * Right answer -> a similar problem, one level up.
  * Wrong answer -> a hint (a similar, easier problem already solved),
                    then a similar problem one level down.
The student's profile lives in a SQLite file on the board. Nothing leaves the device.
"""
import json
import sqlite3
import time

from . import led

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    name TEXT PRIMARY KEY,
    level INTEGER NOT NULL,
    current TEXT,            -- id of the problem on screen
    language TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
    name TEXT, id TEXT, level INTEGER, choice TEXT, correct INTEGER,
    seconds REAL, at REAL
);
"""


class Trainer:
    def __init__(self, bank, db_path="results/students.db", start_level=0):
        self.bank = bank
        self.start_level = start_level
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    # ---- profile --------------------------------------------------------
    def student(self, name):
        row = self.db.execute("SELECT level, current, language FROM students WHERE name=?", (name,)).fetchone()
        return None if row is None else {"level": row[0], "current": row[1], "language": row[2]}

    def seen(self, name):
        return {r[0] for r in self.db.execute("SELECT id FROM answers WHERE name=?", (name,))}

    def history(self, name):
        rows = self.db.execute("SELECT id, level, correct FROM answers WHERE name=? ORDER BY at", (name,))
        return [{"id": i, "level": lvl, "correct": bool(c)} for i, lvl, c in rows]

    def _save(self, name, level, current, language):
        self.db.execute("INSERT OR REPLACE INTO students VALUES (?, ?, ?, ?)", (name, level, current, language))
        self.db.commit()

    # ---- the loop -------------------------------------------------------
    def start(self, name, language="cat", level=None):
        """Start (or resume) a student. Returns the first problem."""
        s = self.student(name)
        if s and s["current"]:
            led.show_level(s["level"])
            return self.view(s["current"], s["language"], s["level"])
        level = self.start_level if level is None else level
        first = self._first_at(level, language, exclude=self.seen(name))
        self._save(name, level, first, language)
        led.show_level(level)
        return self.view(first, language, level)

    def answer(self, name, choice, seconds=0.0):
        """Check the answer, update the level, and choose what comes next."""
        t0 = time.perf_counter()
        s = self.student(name)
        if not s or not s["current"]:
            raise ValueError("Call start() first")
        pid, language, level = s["current"], s["language"], s["level"]
        problem = self.bank.pick(pid, language)
        correct = choice == problem["label"]
        self.db.execute("INSERT INTO answers VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (name, pid, level, choice, int(correct), seconds, time.time()))

        levels = self.bank.levels
        exclude = self.seen(name) | {pid}
        hint = None
        if correct:
            led.show_result(True)
            new_level = min(level + 1, levels[-1])
        else:
            led.show_result(False)
            new_level = max(level - 1, levels[0])
            # The hint: the most similar problem at a lower level, shown solved
            found = self.bank.similar(pid, max(level - 1, levels[0]), language, exclude=exclude)
            if found:
                score, hid = found[0]
                exclude.add(hid)
                hint = {**self.view(hid, language, self.bank.level[hid], solved=True), "similarity": round(score, 3)}

        found = self.bank.similar(pid, new_level, language, exclude=exclude)
        if not found:  # The student has seen everything similar: start somewhere fresh
            nxt = self._first_at(new_level, language, exclude=exclude)
            score = 0.0
        else:
            score, nxt = found[0]
        self._save(name, new_level, nxt, language)
        led.show_level(new_level)
        return {
            "correct": correct,
            "label": problem["label"],
            "hint": hint,
            "level": new_level,
            "next": {**self.view(nxt, language, new_level), "similarity": round(score, 3)},
            "step_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    # ---- helpers --------------------------------------------------------
    def _first_at(self, level, language, exclude=()):
        for distance in range(len(self.bank.levels)):
            for lvl in (level - distance, level + distance) if distance else (level,):
                for pid in self.bank.ids:
                    if self.bank.level[pid] == lvl and pid not in exclude and self.bank.usable(pid, language):
                        return pid
        raise RuntimeError("No usable problems left")

    def view(self, pid, language, level, solved=False):
        """What the web page needs to show a problem. The label only when solved."""
        p = self.bank.pick(pid, language)
        shown = {
            "id": pid,
            "language": p["language"],
            "level": self.bank.level[pid],
            "student_level": level,
            "text": p["text"],
            "options": p.get("options") or {},
            "image": self.bank.has_image(pid, p["language"]),
        }
        if solved:
            shown["label"] = p["label"]
        return shown


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)

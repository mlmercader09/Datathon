"""Simulated students: does the trainer take each one to the right level, and stay on topic?

    python -m trainer.simulate                 # all the default students, 30 steps each
    python -m trainer.simulate --steps 50

A "threshold" student answers right every problem below their level and wrong
from their level up. A good trainer settles around that level. The report shows,
for each student: where they ended, the levels they moved through, how similar
each next problem was to the one before (staying on topic), and the time per step.
"""
import argparse
import os
import random
import statistics
import tempfile

os.environ.setdefault("TRAINER_QUIET", "1")  # don't print every LED update

from .bank import Bank  # noqa: E402
from .trainer import Trainer  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", nargs="+", default=["data/train.jsonl", "data/val.jsonl"])
    p.add_argument("--index", default="data/index.db")
    p.add_argument("--images", default="data/images")
    p.add_argument("--language", default="cat")
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def run(trainer, name, true_level, steps, language, noise, rng):
    p = trainer.start(name, language, level=0)
    path, sims, times, hints_easier = [p["student_level"]], [], [], []
    for _ in range(steps):
        right = trainer.bank.pick(p["id"], language)["label"]
        knows = trainer.bank.level[p["id"]] < true_level
        if rng.random() < noise:  # a careless mistake or a lucky guess
            knows = not knows
        choice = right if knows else next(l for l in "ABCDE" if l != right)
        r = trainer.answer(name, choice)
        path.append(r["level"])
        sims.append(r["next"]["similarity"])
        times.append(r["step_ms"])
        if r["hint"]:
            hints_easier.append(r["hint"]["level"] < trainer.bank.level[p["id"]])
        p = r["next"]
    return path, sims, times, hints_easier


def main():
    args = parse_args()
    bank = Bank(args.data, index_db=args.index, images=args.images)
    print(f"{len(bank.ids)} problems, levels {bank.levels}, similarity: {bank.similarity_source}\n")
    rng = random.Random(args.seed)
    students = [(f"nivell-{t}" + ("-soroll" if noise else ""), t, noise)
                for t in (1, 3, 5) for noise in (0.0, 0.15)]

    print(f"{'Student':<16}{'End':>5}{'Last 10 (mean)':>16}{'Similarity':>12}{'Easier hint':>13}{'ms/step':>9}  Path")
    for name, true_level, noise in students:
        with tempfile.TemporaryDirectory() as tmp:
            trainer = Trainer(bank, db_path=os.path.join(tmp, "s.db"))
            path, sims, times, easier = run(trainer, name, true_level, args.steps, args.language, noise, rng)
        last = statistics.mean(path[-10:])
        hint = f"{sum(easier)}/{len(easier)}" if easier else "-"
        print(f"{name:<16}{path[-1]:>5}{last:>16.1f}{statistics.mean(sims):>12.2f}{hint:>13}"
              f"{statistics.mean(times):>9.1f}  {''.join(map(str, path))}")
    print("\nA threshold-t student should end oscillating between t-1 and t.")


if __name__ == "__main__":
    main()

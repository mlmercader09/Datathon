#!/usr/bin/env python3
"""Measure the model's letter bias on training problems, to correct it in predict.py.

    python3 calibrate.py                 # 100 training problems, about 15 minutes
    python3 calibrate.py --rag 1         # the same with retrieval, as in predict.py --rag 1

It asks the model for the probability of each letter, and writes copilot/calibration.json:
the bias, the real frequency of each answer, and how much to trust the model.
It only reads training problems, so eval.py on the validation set stays honest.
See copilot/calibration.py for the formula.
"""
import argparse
import csv
import json
import os
import random
import time

from copilot import calibration
from copilot.llm import ask

LETTERS = calibration.LETTERS


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/train.jsonl")
    p.add_argument("--limit", type=int, default=100, help="0 means every problem")
    p.add_argument("--languages", default="", help="e.g. eng,cat")
    p.add_argument("--rag", type=int, default=0, metavar="K")
    p.add_argument("--index", default="data/index.db")
    p.add_argument("--min", type=int, default=20, help="fewest problems needed to calibrate a case")
    args = p.parse_args()

    with open(args.input) as f:
        problems = [json.loads(line) for line in f if line.strip()]
    languages = set(filter(None, args.languages.split(",")))
    if languages:
        problems = [x for x in problems if x["language"] in languages]
    labels = [x["label"] for x in problems]  # the prior uses every training label
    random.Random(42).shuffle(problems)
    if args.limit:
        problems = problems[:args.limit]

    index = None
    if args.rag:
        from copilot.rag import Index
        index = Index(args.index)

    os.makedirs("results", exist_ok=True)
    detail_path = f"results/calibration-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    rows = {}  # case -> [(logprobs, label, model's letter)]
    with open(detail_path, "w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["id", "language", "case", "label", "answer"] + [f"logprob_{l}" for l in LETTERS])
        for n, problem in enumerate(problems, 1):
            examples = []
            if index is not None:
                examples = [x for _score, x in index.search(problem, k=args.rag, exclude_id=problem["id"])]
            try:
                letter, logprobs, _timings = ask(problem, examples, timeout=60)
            except OSError as error:  # a timeout or a server that is down: skip this problem
                print(f"[{n}/{len(problems)}] {problem['id']}: skipped ({error})", flush=True)
                continue
            if logprobs is None:
                raise SystemExit("The server sent no letter probabilities, so there is nothing to calibrate. "
                                 "Check: curl http://127.0.0.1:8081/health")
            case = calibration.group(bool(problem.get("options")), bool(examples))
            rows.setdefault(case, []).append((logprobs, problem["label"], letter))
            writer.writerow([problem["id"], problem["language"], case, problem["label"], letter]
                            + [f"{logprobs[l]:.3f}" for l in LETTERS])
            out.flush()
            print(f"[{n}/{len(problems)}] {problem['id']} {problem['language']}: {letter} "
                  f"(truth {problem['label']})", flush=True)

    table = {"groups": {}}
    if os.path.exists(calibration.PATH):  # keep the cases measured in earlier runs
        with open(calibration.PATH) as f:
            table = json.load(f)
    print("\n" + "=" * 60)
    for case, found in sorted(rows.items()):
        if len(found) < args.min:
            print(f"{case}: only {len(found)} problems, not calibrated (needs {args.min})")
            continue
        entry = calibration.fit([(lp, label) for lp, label, _ in found], labels)
        table["groups"][case] = entry
        before = sum(letter == label for _, label, letter in found)
        counts = "  ".join(f"{l}:{sum(letter == l for _, _, letter in found)}" for l in LETTERS)
        print(f"{case}: {len(found)} problems")
        print(f"  the model answered  {counts}")
        print(f"  before: {before}/{len(found)} = {100 * before / len(found):.1f}%   "
              f"after: {entry['train_correct']}/{len(found)} = {100 * entry['train_correct'] / len(found):.1f}%   "
              f"(weight {entry['weight']})")
    print("These are training problems, so 'after' is optimistic. Measure on validation: python3 eval.py")
    with open(calibration.PATH, "w") as f:
        json.dump(table, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"\nWrote {calibration.PATH}\nDetails: {detail_path}")


if __name__ == "__main__":
    main()

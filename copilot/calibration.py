"""Correct the model's taste for one letter.

The small model answers the same letter far too often (B in 39 of 50 problems in
our first run). We measure how often it gives each letter on training problems
(its bias), and replace that with how often each letter is really the answer:

    score(letter) = weight * (log p_model(letter) - log bias(letter)) + log prior(letter)

calibrate.py measures bias, prior and weight on the board and writes
copilot/calibration.json. Without that file, or with CALIBRATION=0, the copilot
answers exactly as before.
"""
import json
import math
import os

LETTERS = "ABCDE"
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration.json")
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0)


def load(path=PATH):
    if os.environ.get("CALIBRATION", "1") == "0" or not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


TABLE = load()


def group(has_options, rag=False):
    """The bias changes with what the model reads, so each case has its own numbers."""
    return ("options" if has_options else "no_options") + ("+rag" if rag else "")


def scores(logprobs, entry):
    return {l: entry["weight"] * (logprobs[l] - entry["bias"][l]) + entry["prior"][l] for l in LETTERS}


def best(logprobs, entry, letter=""):
    """The letter with the highest score. A tie goes to the model's own letter, then to the alphabet."""
    s = scores(logprobs, entry)
    return max(LETTERS, key=lambda l: (round(s[l], 9), l == letter, -ord(l)))


def choose(letter, logprobs, has_options, rag=False, table=None):
    """The corrected letter, or the model's own letter when there is nothing to correct with."""
    table = TABLE if table is None else table
    if not table or logprobs is None:
        return letter
    groups = table.get("groups", {})
    entry = groups.get(group(has_options, rag)) or groups.get(group(has_options))
    return best(logprobs, entry, letter) if entry else letter


def fit(rows, labels):
    """rows: (logprobs, label) pairs from training problems. labels: every training label, for the prior."""
    mean = {l: sum(math.exp(lp[l]) for lp, _ in rows) / len(rows) for l in LETTERS}
    total = sum(mean.values())
    entry = {
        "bias": {l: math.log(mean[l] / total) for l in LETTERS},
        # +1 keeps a letter that never appears from scoring minus infinity
        "prior": {l: math.log((labels.count(l) + 1) / (len(labels) + len(LETTERS))) for l in LETTERS},
        "n": len(rows),
    }
    # weight 0 ignores the model and always answers the most common letter; 1 trusts it fully
    tried = {}
    for weight in WEIGHTS:
        entry["weight"] = weight
        tried[weight] = sum(best(lp, entry) == label for lp, label in rows)
    entry["weight"] = max(WEIGHTS, key=lambda w: (tried[w], -abs(w - 1.0)))
    entry["train_correct"] = tried[entry["weight"]]
    return entry

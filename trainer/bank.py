"""The problem bank: every M3Kang problem, grouped by id, with a way to find similar ones.

Similarity comes from one of two places:
  * data/index.db (built on the board with build_index.py): the bge-small vectors.
    The vectors are already stored, so finding neighbours costs no model call.
  * If there is no index (for example on a laptop), a simple word-overlap
    similarity (TF-IDF) on the English text. Good enough to develop and test.

Only the Python standard library is used, so this runs on the board as is.
"""
import json
import math
import os
import re
import sqlite3
from array import array
from collections import Counter, defaultdict

WORD = re.compile(r"[a-z]+")
# Similarity above this means "the same problem", not "a similar one"
DUPLICATE = 0.9

STOP = set("""a an the of to in on and or is are was were be by for with as at from that this
these those it its which what how many much there their they he she his her we you your
can do does if then than each one two three has have had not no all any into out up so""".split())


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Bank:
    def __init__(self, paths, index_db=None, images="data/images"):
        self.images = images
        # List the images once: checking the disk for every candidate is slow
        self.image_files = set(os.listdir(images)) if os.path.isdir(images) else set()
        # by_id[id][language] = problem
        self.by_id = defaultdict(dict)
        for path in paths:
            if os.path.exists(path):
                for p in read_jsonl(path):
                    self.by_id[p["id"]][p["language"]] = p
        if not self.by_id:
            raise SystemExit(f"No problems found in {paths}. Run laptop/prepare_m3kang.py first.")
        self.ids = sorted(self.by_id)
        self.level = {i: self.pick(i)["level"] for i in self.ids}
        self.levels = sorted(set(self.level.values()))
        self.vectors = self._load_vectors(index_db) if index_db and os.path.exists(index_db) else None
        if self.vectors is None:
            self.vectors = self._tfidf()
            self.similarity_source = "tf-idf (no index.db)"
        else:
            self.similarity_source = f"embeddings from {index_db}"
        self._cache = {}

    # ---- problems -------------------------------------------------------
    def pick(self, pid, language="eng"):
        """The problem in the asked language, or English, or whatever exists."""
        versions = self.by_id[pid]
        return versions.get(language) or versions.get("eng") or next(iter(versions.values()))

    def has_image(self, pid, language):
        return f"{pid}_{language}.png" in self.image_files

    def image_path(self, pid, language):
        return os.path.join(self.images, f"{pid}_{language}.png")

    def usable(self, pid, language):
        """A student can answer it if they can see the options: in the text or in the image."""
        return bool(self.pick(pid, language).get("options")) or self.has_image(pid, language)

    # ---- similarity -----------------------------------------------------
    def _load_vectors(self, db_path):
        """One unit vector per id, taken from the English row when there is one."""
        vectors = {}
        db = sqlite3.connect(db_path)
        for key, blob in db.execute("SELECT key, vec FROM problems"):
            pid, language = key.split("|", 1)
            if pid not in self.by_id or (pid in vectors and language != "eng"):
                continue
            vec = array("f")
            vec.frombytes(blob)
            vectors[pid] = list(vec)
        db.close()
        if len(vectors) < len(self.ids) * 0.5:
            print(f"index.db covers only {len(vectors)} of {len(self.ids)} problems: using TF-IDF instead")
            return None
        # Problems missing from the index get TF-IDF neighbours through a fallback in similar()
        self._missing = set(self.ids) - set(vectors)
        return vectors

    def _tfidf(self):
        docs = {}
        for pid in self.ids:
            words = [w for w in WORD.findall(self.pick(pid, "eng")["text"].lower()) if w not in STOP and len(w) > 2]
            docs[pid] = Counter(words)
        df = Counter(w for c in docs.values() for w in c)
        n = len(docs)
        vectors = {}
        for pid, counts in docs.items():
            vec = {w: (1 + math.log(c)) * math.log((1 + n) / (1 + df[w])) for w, c in counts.items()}
            norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
            vectors[pid] = {w: x / norm for w, x in vec.items()}
        self._missing = set()
        return vectors

    def score(self, a, b):
        va, vb = self.vectors.get(a), self.vectors.get(b)
        if va is None or vb is None:
            return 0.0
        if isinstance(va, dict):
            if len(va) > len(vb):
                va, vb = vb, va
            return sum(x * vb.get(w, 0.0) for w, x in va.items())
        return sum(x * y for x, y in zip(va, vb))

    def neighbours(self, pid):
        """Every other problem, most similar first. Cached: each id is ranked once."""
        if pid not in self._cache:
            ranked = sorted(((self.score(pid, o), o) for o in self.ids if o != pid), reverse=True)
            self._cache[pid] = ranked
        return self._cache[pid]

    def similar(self, pid, level, language, exclude=(), k=1):
        """Up to k (score, id) pairs similar to pid at the given level, skipping ids in exclude.

        If no problem is left at that level, it takes the closest level instead.
        """
        # Skip near-duplicates: Kangaroo repeats some problems in two categories,
        # and showing the same problem as a "hint" would give the answer away.
        candidates = [(s, o) for s, o in self.neighbours(pid)
                      if o not in exclude and s < DUPLICATE and self.usable(o, language)]
        for distance in range(len(self.levels)):
            for lvl in (level - distance, level + distance) if distance else (level,):
                found = [(s, o) for s, o in candidates if self.level[o] == lvl]
                if found:
                    return found[:k]
        return []

"""The trainer's web page, served from a laptop or the board without App Lab.

    python -m trainer.server                      # on a laptop: http://127.0.0.1:8000
    python3 -m trainer.server --host 0.0.0.0      # on the board, for the class's phones

The routes are the same as the App Lab app's (applab/cangur-trainer), so
trainer/index.html works with both:
    GET /api/start/<name>/<language>/<level>
    GET /api/answer/<name>/<choice>/<seconds>
    GET /images/<id>_<language>.png

Only the Python standard library.
"""
import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from .bank import Bank
from .trainer import Trainer

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE_KEY = re.compile(r"^[A-Za-z0-9_\-]+$")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", nargs="+", default=["data/train.jsonl", "data/val.jsonl"])
    p.add_argument("--index", default="data/trainer_index.db", help="embeddings of every problem (see trainer/README.md)")
    p.add_argument("--images", default="data/images")
    p.add_argument("--db", default="results/students.db")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    return p.parse_args()


def route(trainer, path):
    """The API, shared in spirit with applab/cangur-trainer/python/main.py."""
    parts = [unquote(p) for p in path.strip("/").split("/")]
    if parts[:2] == ["api", "start"] and len(parts) == 5:
        _, _, name, language, level = parts
        return trainer.start(name, language, int(level))
    if parts[:2] == ["api", "answer"] and len(parts) == 5:
        _, _, name, choice, seconds = parts
        return trainer.answer(name, choice, float(seconds))
    if parts[:2] == ["api", "history"] and len(parts) == 3:
        return trainer.history(parts[2])
    return None


def make_handler(trainer):
    page = open(os.path.join(HERE, "index.html"), encoding="utf-8").read().encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send(self, code, body, kind="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                return self.send(200, page, "text/html; charset=utf-8")
            if path.startswith("/images/") and path.endswith(".png"):
                key = path[len("/images/"):-len(".png")]
                file = os.path.join(trainer.bank.images, key + ".png")
                if SAFE_KEY.match(key) and os.path.exists(file):
                    with open(file, "rb") as f:
                        return self.send(200, f.read(), "image/png")
                return self.send(404, {"error": "no image"})
            try:
                result = route(trainer, path)
            except (KeyError, ValueError, RuntimeError) as e:
                return self.send(400, {"error": str(e)})
            if result is None:
                return self.send(404, {"error": "not found"})
            self.send(200, result)

    return Handler


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    bank = Bank(args.data, index_db=args.index, images=args.images)
    trainer = Trainer(bank, db_path=args.db)
    print(f"{len(bank.ids)} problems, levels {bank.levels}, similarity: {bank.similarity_source}")
    print(f"Open http://{args.host}:{args.port} (Ctrl+C to stop)")
    ThreadingHTTPServer((args.host, args.port), make_handler(trainer)).serve_forever()


if __name__ == "__main__":
    main()

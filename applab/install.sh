#!/usr/bin/env bash
# Install (or update) the Cangur trainer App Lab app on the board.
#
#   On the board, from the repository folder:
#     bash applab/install.sh
#     arduino-app-cli app start user:cangur-trainer
#
# It copies into ~/ArduinoApps/cangur-trainer:
#   * the app (app.yaml, python/main.py, sketch/)
#   * the trainer's code (trainer/*.py -> python/trainer/, trainer/index.html -> assets/)
#   * the data (data/train.jsonl, data/val.jsonl, data/trainer_index.db -> python/data/)
#   * the images (data/images -> assets/images, served by the web_ui brick)
# The student profiles (python/data/students.db) are kept between installs.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/applab/cangur-trainer"
APP="$HOME/ArduinoApps/cangur-trainer"

for f in data/train.jsonl data/val.jsonl; do
  [ -f "$REPO/$f" ] || { echo "Missing $f: copy the data to the board first (step 10)."; exit 1; }
done

if [ ! -d "$APP" ] && command -v arduino-app-cli >/dev/null; then
  arduino-app-cli app new "cangur-trainer" >/dev/null 2>&1 || true
fi
mkdir -p "$APP/python/trainer" "$APP/python/data" "$APP/assets/images" "$APP/sketch"

cp "$SRC/app.yaml" "$APP/"
cp "$SRC/python/main.py" "$APP/python/"
cp "$SRC/sketch/sketch.ino" "$SRC/sketch/sketch.yaml" "$APP/sketch/"
cp "$REPO"/trainer/__init__.py "$REPO"/trainer/bank.py "$REPO"/trainer/trainer.py "$REPO"/trainer/led.py "$APP/python/trainer/"
cp "$REPO/trainer/index.html" "$APP/assets/index.html"
cp "$REPO/data/train.jsonl" "$REPO/data/val.jsonl" "$APP/python/data/"

if [ -f "$REPO/data/trainer_index.db" ]; then
  cp "$REPO/data/trainer_index.db" "$APP/python/data/index.db"
  echo "Similar problems: embeddings (data/trainer_index.db)"
else
  echo "No data/trainer_index.db yet: similar problems use word overlap."
  echo "For better hints, build it (about 10 minutes, see trainer/README.md):"
  echo "  cat data/train.jsonl data/val.jsonl > data/all.jsonl"
  echo "  python3 build_index.py --input data/all.jsonl --db data/trainer_index.db --languages eng"
fi

if [ -d "$REPO/data/images" ]; then
  cp -ru "$REPO/data/images/." "$APP/assets/images/"
  echo "Images: $(ls "$APP/assets/images" | wc -l)"
else
  echo "No data/images: the page will show the text only. Copy the images to the board (see the explorer section of GUIA_REPTE.md)."
fi

echo
echo "Installed in $APP"
echo "Start it:   arduino-app-cli app start user:cangur-trainer"
echo "Logs:       arduino-app-cli app logs $APP --all"
echo "Open:       http://<board-ip>:7000"

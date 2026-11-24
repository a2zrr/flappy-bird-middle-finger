#!/usr/bin/env bash
# One command to play: sets up the Python environment, builds the Java game,
# starts the webcam tracker in the background and opens the game.
# When the game closes, the tracker is stopped too.
#
#   ./run.sh                  # play (the webcam image is shown beside the board)
#   ./run.sh --preview        # also open a separate OpenCV preview window
#   ./run.sh --debug          # print finger ratios, to tune the thresholds
#   ./run.sh --camera 1       # any other flags go to tracker/tracker.py
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
REQ="$ROOT/tracker/requirements.txt"
STAMP="$VENV/.requirements.sha256"
OUT="$ROOT/build/out"
TRACKER_PID=""

# --preview is handled here; everything else goes to the tracker.
# The separate OpenCV window stays off by default. The game shows the camera
# beside the board itself, so that window is not needed.
PREVIEW=0
TRACKER_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--preview" ]]; then
        PREVIEW=1
    else
        TRACKER_ARGS+=("$arg")
    fi
done
if [[ "$PREVIEW" -eq 0 ]]; then
    TRACKER_ARGS+=("--no-preview")
fi

die() {
    echo "ERROR: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$TRACKER_PID" ]] && kill -0 "$TRACKER_PID" 2>/dev/null; then
        echo "Stopping the tracker..."
        kill "$TRACKER_PID" 2>/dev/null || true
        wait "$TRACKER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# 1. Python environment. MediaPipe wheels are not available for the newest Python
#    releases yet (Fedora's default python3 may be one of them), so pin 3.12 via uv.
if [[ ! -x "$VENV/bin/python" ]]; then
    echo "Creating the Python environment in .venv (Python 3.12) ..."
    if command -v uv >/dev/null 2>&1; then
        uv venv --quiet --python 3.12 "$VENV"
    else
        PY=""
        for candidate in python3.12 python3.11; do
            if command -v "$candidate" >/dev/null 2>&1; then
                PY="$candidate"
                break
            fi
        done
        [[ -n "$PY" ]] || die "Python 3.11 or 3.12 is needed (MediaPipe has no wheels for newer versions yet).
Install one of them, or install uv (https://docs.astral.sh/uv/) and run again."
        "$PY" -m venv "$VENV"
    fi
fi

SHA="$(sha256sum "$REQ" | cut -d' ' -f1)"
if [[ ! -f "$STAMP" || "$(cat "$STAMP")" != "$SHA" ]]; then
    echo "Installing the tracker requirements ..."
    if command -v uv >/dev/null 2>&1; then
        uv pip install --quiet --python "$VENV/bin/python" -r "$REQ"
    else
        "$VENV/bin/python" -m pip install --quiet -r "$REQ"
    fi
    echo "$SHA" > "$STAMP"
fi

# 2. Build the Java game into build/out (javac and the images only).
command -v javac >/dev/null 2>&1 || die "javac not found. Install a JDK (Java 8 or newer)."
rm -rf "$OUT"
mkdir -p "$OUT"
javac -d "$OUT" "$ROOT"/game/src/*.java
cp "$ROOT"/game/src/*.png "$OUT"/

# 3. Start the tracker in the background.
#    The OpenCV window runs through XWayland on Wayland desktops; QT_QPA_PLATFORM=xcb
#    makes that explicit (see the README troubleshooting section).
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
echo "Starting the webcam tracker ..."
"$VENV/bin/python" "$ROOT/tracker/tracker.py" "${TRACKER_ARGS[@]}" &
TRACKER_PID=$!
sleep 1
if ! kill -0 "$TRACKER_PID" 2>/dev/null; then
    echo "WARNING: the tracker stopped (see the message above). The game will run with SPACE only." >&2
    TRACKER_PID=""
fi

# 4. Play. Closing the game ends the script, and the trap stops the tracker.
echo "Starting the game. Raise your middle finger, or press SPACE."
java -cp "$OUT" App

# Flappy Bird, Middle Finger Edition 🖕

**Flip off gravity. Literally.** The bird flies when you raise your middle finger at your webcam. Gravity has never been so offended.

> 🎞️ *GIF placeholder: record a short clip of a few jumps and save it as `docs/demo.gif`.*

## How it works

```
 ┌──────────┐   frames   ┌────────────────────────┐   21 landmarks   ┌──────────────────────┐
 │  Webcam  │ ─────────► │ MediaPipe Hand         │ ───────────────► │ gesture.py           │
 │ (OpenCV) │            │ Landmarker (per frame) │                  │ middle up, others    │
 └──────────┘            └────────────────────────┘                  │ folded? debounce,    │
                                                                      │ rising edge → FLAP   │
                                                                      └──────────┬───────────┘
                                                                                 │ UDP 127.0.0.1:5005
                                                                                 │ "FLAP" / "STATUS …"
                                                                                 ▼
                                                                      ┌──────────────────────┐
                                                                      │ Java Swing game      │
                                                                      │ FLAP = SPACE jump,   │
                                                                      │ HUD shows hand state │
                                                                      └──────────────────────┘
```

- `tracker/` (Python) reads the webcam, runs MediaPipe, works out the gesture and sends messages over UDP.
- `game/` (Java, Swing) is the original game. It listens for those messages and treats each `FLAP` exactly like pressing SPACE.

## Requirements

- Linux with a webcam (developed on Fedora, Wayland)
- A JDK, Java 8 or newer (`javac` and `java` on the PATH)
- Python 3.12 (see [Python version](#python-version)). `run.sh` gets it with [uv](https://docs.astral.sh/uv/) if it is missing, or uses `python3.12` / `python3.11` if you have one.
- Internet access on the first run: Python packages and the hand model (about 8 MB) are downloaded.

## Quick start

```bash
./run.sh
```

The first run creates `.venv/`, installs the tracker requirements, compiles the game into `build/out/`, starts the tracker in the background and opens the game. Closing the game also stops the tracker.

The game opens on a start screen. **Raise your middle finger (or press SPACE) to start.** The bird doesn't fall until then. The camera preview is hidden by default so it doesn't cover the game. Add `--preview` if you want to see it.

Any extra flags go to the tracker:

```bash
./run.sh --preview         # also show the camera preview window (hidden by default)
./run.sh --debug           # print finger ratios while you tune
./run.sh --camera 1        # use a different camera
```

## Manual start

Two terminals:

```bash
# Terminal 1: the tracker (creates the venv yourself, downloads the model on first run)
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r tracker/requirements.txt
.venv/bin/python tracker/tracker.py

# Terminal 2: the game
javac -d build/out game/src/*.java && cp game/src/*.png build/out/
java -cp build/out App
```

## Controls

| Action | Input |
| --- | --- |
| Jump | Raise your **middle finger** (index, ring and pinky folded). Each raise = one jump. |
| Jump again | Fold the finger back down, then raise it again. Holding it up does nothing. |
| Jump | **SPACE** still works, exactly as in the original game. |
| Start | Raise the middle finger, or press SPACE, on the start screen. |
| Restart after game over | Raise the middle finger again. It is ignored for the first 0.8 s after game over, so the jump that caused the crash doesn't restart the game at once. The **Restart** button still works. SPACE does not restart, as in the original game. |
| Quit the tracker | `q` or `ESC` in its preview window, or `Ctrl+C` |

The corner of the game shows what the webcam sees: **no hand**, **hand detected** or **finger UP**. It appears once the tracker is connected.

## Tuning

Run `./run.sh --debug`. For each hand it prints the ratio of each finger (tip distance from the wrist divided by PIP distance). Extended fingers are above `--extend-ratio` (1.15 by default), folded fingers below `--fold-ratio` (1.00 by default).

| Symptom | Try |
| --- | --- |
| Raising the finger doesn't register | Lower `--extend-ratio`, for example `1.05`. Check the middle ratio in `--debug`. |
| Finger down still counts as up | Raise `--extend-ratio`, for example `1.3`. |
| Gesture never turns ON, even with the middle finger up | Ring or pinky aren't "folded" enough. Raise `--fold-ratio`, for example `1.05`. |
| Flaps when you didn't raise anything | Raise `--on-frames` to `3`, or raise `--extend-ratio`. |
| Flap feels slow to register | Lower `--on-frames` to `1`. Higher values filter noise but add a few frames of delay. |
| Double jumps from one raise | Raise `--min-gap-ms` (default 120). |
| Wrong camera | `--camera 1` (or `2`, and so on). |

All values are also constants at the top of `tracker/gesture.py`.

## Troubleshooting

**Camera: "could not open camera"**
- Close anything else that uses the webcam (a browser tab with a video call, another app).
- Check the device exists and you can read it: `ls -l /dev/video*`. If you get "permission denied", add yourself to the `video` group (`sudo usermod -aG video $USER`) and log in again.
- Try another index with `--camera 1`.

**Python version**
- MediaPipe 1.2.3 (the version `tracker/requirements.txt` resolves to) installs from binary wheels on both Python 3.12 and 3.15 (tested on this machine with uv). `run.sh` uses 3.12 to keep the setup predictable and to not depend on your system Python.
- If an install stalls, use uv. On my first attempt, plain `pip` with the Fedora default Python 3.15 took a long time, and uv installed the same packages in seconds.

**Wayland and the preview window**
- The OpenCV window runs through XWayland. `run.sh` sets `QT_QPA_PLATFORM=xcb`, because the OpenCV wheels only ship the X11 Qt plugin.
- If the preview window doesn't appear, check that XWayland is running (`echo $DISPLAY` should print something like `:0`). Some compositors don't provide XWayland by default.
- The preview is hidden by default because a window can't be placed beside the game on Wayland, so it would cover the game. Use `./run.sh --preview` only when you want to see it.

**The game doesn't react**
- Test the game without the camera: `python3 tools/send_flap.py` should make the bird jump. If it doesn't, the game isn't listening. Check the terminal for `Gesture control: listening on UDP 127.0.0.1:5005`.
- The game prints a warning if port 5005 is busy (for example, a second game is open). Find the process with `ss -lunp | grep 5005`.
- Check the corner HUD while you raise the finger: it should change from "hand detected" to "finger UP".

**Model download failed**
- The tracker prints the URL and the target path. Download the file by hand and save it as `tracker/models/hand_landmarker.task`.

## Development

```bash
# Gesture unit tests (no camera needed)
cd tracker && ../.venv/bin/python -m pytest

# Game listener test (runs headless, no window)
javac -d build/test game/src/*.java game/test/*.java
java -Djava.awt.headless=true -cp build/test:game/src HeadlessFlapTest
```

Project layout:

```
game/src/           the Java game (original code, plus UdpGestureListener)
game/test/          headless UDP test for the game
tracker/tracker.py  webcam loop, MediaPipe, UDP sender, preview
tracker/gesture.py  pure gesture logic (no camera or MediaPipe imports)
tracker/tests/      pytest tests with fake landmarks
tools/send_flap.py  sends FLAP over UDP to test the game without a camera
run.sh              one command to set up, build and play
```

## Credits

Based on my original game: https://github.com/a2zrr/FlappyBird-Game-With-JAVA

Game design and implementation by EZZERBOUTI Abdel Hak.

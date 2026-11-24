#!/usr/bin/env python3
"""Webcam -> MediaPipe Hand Landmarker -> middle-finger gesture -> UDP to the Java game.

Sends to 127.0.0.1:<port> (default 5005):
  FLAP                          once per OFF -> ON edge of the gesture
  STATUS hand=0|1 gesture=0|1   about 10 times per second (drives the game's HUD)

Run it with ./run.sh (starts the game too) or on its own:
  tracker/.venv/bin/python tracker/tracker.py --debug
"""

import argparse
import os
import shutil
import socket
import sys
import time
import urllib.request

# Keep MediaPipe and TensorFlow Lite quiet in the terminal.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
# Wayland: the opencv wheel only ships the X11 (xcb) Qt plugin, so the preview
# window runs through XWayland. Harmless on X11.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2  # noqa: E402
import mediapipe as mp  # noqa: E402
from mediapipe.tasks.python import BaseOptions  # noqa: E402
from mediapipe.tasks.python.vision import (  # noqa: E402
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

from gesture import (  # noqa: E402
    EXTEND_RATIO,
    FOLD_RATIO,
    MIDDLE,
    MIN_FLAP_GAP_S,
    OFF_FRAMES,
    ON_FRAMES,
    MiddleFingerDetector,
    finger_ratios,
)

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_URL = (
    "https://huggingface.co/litert-community/MediaPipe-HandLandmarker-Full"
    "/resolve/main/hand_landmarker.task"
)
MODEL_PATH = os.path.join(HERE, "models", "hand_landmarker.task")

FRAME_W, FRAME_H = 640, 480
STATUS_PERIOD_S = 0.1   # STATUS messages per second: 10
FLASH_S = 0.5           # how long the "FLAP!" text stays on screen
WINDOW_NAME = "Flappy Bird: middle finger"

# Bones for drawing the hand (MediaPipe's standard 21-landmark skeleton).
HAND_BONES = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def fail(message):
    raise SystemExit("ERROR: " + message)


def ensure_model(path):
    """Download the hand model on first run. Fails with instructions if that is impossible."""
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("Downloading the hand model (about 8 MB), this only happens once ...", flush=True)
    part = path + ".part"
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, open(part, "wb") as out:
            shutil.copyfileobj(response, out)
        os.replace(part, path)
    except OSError as exc:  # URLError and HTTPError are subclasses of OSError
        if os.path.exists(part):
            os.remove(part)
        fail(
            f"could not download the hand model ({exc}).\n"
            f"Download it manually from:\n  {MODEL_URL}\n"
            f"and save it as:\n  {path}"
        )
    print(f"Saved the model to {path}", flush=True)


def make_landmarker():
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_hands=2,  # either hand can trigger a flap
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    try:
        return HandLandmarker.create_from_options(options)
    except Exception as exc:  # the model file is corrupt or incompatible
        fail(f"could not load the hand model from {MODEL_PATH}: {exc}\n"
             "Delete that file and run again to download it.")


def open_camera(source):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        cap.release()
        fail(
            f"could not open camera {source!r}.\n"
            "  - Is another app using it (browser tab, video call)? Close it and retry.\n"
            "  - Try another index, for example --camera 1.\n"
            "  - Check that /dev/video* exists and that your user can read it (group 'video')."
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # fewer stale frames means lower latency
    return cap


def draw_hand(frame, landmarks, highlight):
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_BONES:
        cv2.line(frame, pts[a], pts[b], (200, 200, 200), 2)
    for i, p in enumerate(pts):
        color = (0, 255, 255) if (highlight and i in MIDDLE) else (0, 200, 0)
        cv2.circle(frame, p, 4, color, -1)


def draw_hud(frame, gesture_on, hand_present, fps, flash):
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    state_color = (0, 255, 0) if gesture_on else (180, 180, 180)
    cv2.putText(frame, f"gesture: {'ON' if gesture_on else 'OFF'}", (10, 30), font, 0.8, state_color, 2)
    cv2.putText(frame, f"hand: {'yes' if hand_present else 'no'}", (10, 60), font, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"FPS: {fps:4.1f}", (w - 150, 30), font, 0.8, (255, 255, 255), 2)
    if flash:
        text = "FLAP!"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 3, 6)
        cv2.putText(frame, text, ((w - tw) // 2, (h + th) // 2), cv2.FONT_HERSHEY_DUPLEX, 3, (0, 255, 255), 6)


def fmt(value):
    return "n/a" if value is None else f"{value:.2f}"


def parse_args(argv):
    p = argparse.ArgumentParser(description="Middle-finger webcam tracker for the Flappy Bird game.")
    p.add_argument("--camera", default="0",
                   help="camera index (default 0). A video file path also works, for testing.")
    p.add_argument("--port", type=int, default=5005, help="UDP port of the game (default 5005)")
    p.add_argument("--no-preview", action="store_true", help="do not open the preview window")
    p.add_argument("--extend-ratio", type=float, default=EXTEND_RATIO,
                   help=f"finger is extended when tip/pip distance ratio > this (default {EXTEND_RATIO})")
    p.add_argument("--fold-ratio", type=float, default=FOLD_RATIO,
                   help=f"finger is folded when tip/pip distance ratio < this (default {FOLD_RATIO})")
    p.add_argument("--on-frames", type=int, default=ON_FRAMES,
                   help=f"matching frames in a row before the gesture turns ON (default {ON_FRAMES})")
    p.add_argument("--off-frames", type=int, default=OFF_FRAMES,
                   help=f"non-matching frames in a row before it turns OFF (default {OFF_FRAMES})")
    p.add_argument("--min-gap-ms", type=float, default=MIN_FLAP_GAP_S * 1000,
                   help=f"minimum time between two flaps in ms (default {MIN_FLAP_GAP_S * 1000:.0f})")
    p.add_argument("--debug", action="store_true",
                   help="print the finger ratios of each hand, to help tune the thresholds")
    args = p.parse_args(argv)
    if args.fold_ratio >= args.extend_ratio:
        p.error("--fold-ratio must be smaller than --extend-ratio")
    return args


def main(argv=None):
    args = parse_args(argv)
    ensure_model(MODEL_PATH)
    landmarker = make_landmarker()
    source = int(args.camera) if args.camera.isdigit() else args.camera
    cap = open_camera(source)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = ("127.0.0.1", args.port)
    aspect = FRAME_W / FRAME_H

    def make_detector():
        return MiddleFingerDetector(
            aspect=aspect,
            extend_ratio=args.extend_ratio,
            fold_ratio=args.fold_ratio,
            on_frames=args.on_frames,
            off_frames=args.off_frames,
            min_flap_gap=args.min_gap_ms / 1000.0,
        )

    def send(message):
        try:
            sock.sendto(message, target)
        except OSError:
            pass  # the game is not running yet, or was closed: nothing to do

    detectors = {}           # one detector per hand label ("Left"/"Right")
    start = time.monotonic()
    last_ts = -1             # MediaPipe needs strictly increasing timestamps
    last_status = 0.0
    last_debug = 0.0
    last_frame = time.monotonic()
    flash_until = 0.0
    fps = 0.0
    flaps = 0
    frames = 0
    failed_reads = 0

    if not args.no_preview:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    print(f"Tracking. Sending to 127.0.0.1:{args.port}. Raise your middle finger!", flush=True)
    if args.no_preview:
        print("Press Ctrl+C to quit.", flush=True)
    else:
        print("Press q or ESC in the preview window (or Ctrl+C) to quit.", flush=True)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if isinstance(source, str):  # a video file has ended
                    print("End of video file.", flush=True)
                    break
                failed_reads += 1
                if failed_reads > 100:
                    fail("the camera stopped delivering frames.")
                time.sleep(0.01)
                continue
            failed_reads = 0
            frames += 1

            frame = cv2.flip(frame, 1)  # mirror: selfie view
            now = time.monotonic()
            ts_ms = max(int((now - start) * 1000), last_ts + 1)
            last_ts = ts_ms
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, ts_ms)

            hands = {}
            for i, landmarks in enumerate(result.hand_landmarks):
                label = result.handedness[i][0].category_name if i < len(result.handedness) else "Hand"
                hands.setdefault(label, landmarks)

            gesture_on = False
            flap = False
            for label in set(detectors) | set(hands):
                if label not in detectors:
                    detectors[label] = make_detector()
                on, fired = detectors[label].update(hands.get(label), now)
                gesture_on = gesture_on or on
                flap = flap or fired

            if flap:
                flaps += 1
                send(b"FLAP")
                flash_until = now + FLASH_S
                print(f"FLAP #{flaps}", flush=True)

            if now - last_status >= STATUS_PERIOD_S:
                send(f"STATUS hand={int(bool(hands))} gesture={int(gesture_on)}".encode("ascii"))
                last_status = now

            if args.debug and hands and now - last_debug >= 0.2:
                last_debug = now
                for label, landmarks in hands.items():
                    r = finger_ratios(landmarks, aspect)
                    print(f"[{label}] index={fmt(r['index'])} middle={fmt(r['middle'])} "
                          f"ring={fmt(r['ring'])} pinky={fmt(r['pinky'])}  "
                          f"(extended > {args.extend_ratio}, folded < {args.fold_ratio})", flush=True)

            fps = 0.9 * fps + 0.1 / max(now - last_frame, 1e-6) if frames > 1 else 0.0
            last_frame = now

            if not args.no_preview:
                for landmarks in hands.values():
                    draw_hand(frame, landmarks, gesture_on)
                draw_hud(frame, gesture_on, bool(hands), fps, now < flash_until)
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if frames > 30 and cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break  # window closed with its own close button
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        landmarker.close()
        sock.close()
        if not args.no_preview:
            cv2.destroyAllWindows()
    print(f"Stopped. {flaps} flap(s) sent.", flush=True)


if __name__ == "__main__":
    sys.exit(main())

"""Middle-finger gesture logic. Pure Python: no OpenCV, no MediaPipe, no camera.

Input per frame: the 21 hand landmarks (normalised x/y, as MediaPipe gives them),
or None when no hand is visible. Output: whether the gesture is ON, and whether
a FLAP should be sent on this frame.

Gesture: middle finger EXTENDED while index, ring and pinky are FOLDED.
The thumb is ignored.

A finger is judged by distances from the wrist, not by y-coordinates, so it
works with either hand, palm or back of the hand to the camera, and when the
hand is tilted. For each finger, compare the tip with the PIP joint:

    ratio = dist(wrist, tip) / dist(wrist, pip)
    EXTENDED if ratio > EXTEND_RATIO
    FOLDED   if ratio < FOLD_RATIO
    otherwise UNCLEAR (counts as "not the gesture")

The ratio cancels out hand size, so no palm normalisation is needed. The palm
size (wrist to middle MCP) is only used to reject degenerate input.
"""

import math
import time

# MediaPipe landmark indices
WRIST = 0
# Each finger is (MCP, PIP, DIP, TIP).
INDEX = (5, 6, 7, 8)
MIDDLE = (9, 10, 11, 12)
RING = (13, 14, 15, 16)
PINKY = (17, 18, 19, 20)
FINGERS = {"index": INDEX, "middle": MIDDLE, "ring": RING, "pinky": PINKY}

# Tunable thresholds. tracker.py exposes the important ones as CLI flags.
EXTEND_RATIO = 1.15      # tip this much farther from the wrist than the PIP => extended
FOLD_RATIO = 1.00        # tip closer to the wrist than the PIP by this factor => folded
MIDDLE_LEAD = 0.20       # other fingers may read above FOLD_RATIO if the middle is this much longer
ON_FRAMES = 1            # matching frames in a row before the gesture turns ON (the camera runs ~8 fps here)
OFF_FRAMES = 2           # non-matching frames in a row before it turns OFF
MIN_FLAP_GAP_S = 0.120   # minimum time between two FLAPs, in seconds

EXTENDED = "extended"
FOLDED = "folded"
UNCLEAR = "unclear"


def _xy(point):
    """Accept MediaPipe landmarks (objects with .x/.y) or plain (x, y) tuples."""
    if hasattr(point, "x"):
        return point.x, point.y
    return point[0], point[1]


def _dist(a, b, aspect):
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return math.hypot((ax - bx) * aspect, ay - by)


def finger_ratio(points, finger, aspect=1.0):
    """dist(wrist, tip) / dist(wrist, pip), or None if the PIP is degenerate."""
    _mcp, pip, _dip, tip = finger
    wrist = points[WRIST]
    d_pip = _dist(wrist, points[pip], aspect)
    if d_pip <= 1e-9:
        return None
    return _dist(wrist, points[tip], aspect) / d_pip


def classify_finger(points, finger, extend_ratio=EXTEND_RATIO, fold_ratio=FOLD_RATIO, aspect=1.0):
    ratio = finger_ratio(points, finger, aspect)
    if ratio is None:
        return UNCLEAR
    if ratio > extend_ratio:
        return EXTENDED
    if ratio < fold_ratio:
        return FOLDED
    return UNCLEAR


def finger_ratios(points, aspect=1.0):
    """Ratios for the four fingers, used by --debug to help tune the thresholds."""
    return {name: finger_ratio(points, f, aspect) for name, f in FINGERS.items()}


def pattern_matches(points, extend_ratio=EXTEND_RATIO, fold_ratio=FOLD_RATIO, aspect=1.0,
                    lead=MIDDLE_LEAD):
    """True when this single frame shows middle up and index, ring and pinky down.

    A finger counts as down when it is FOLDED, or when the middle finger is clearly
    longer than it (at least `lead` in ratio). The second rule matters because a
    relaxed folded finger can read above fold_ratio on some hands.
    """
    if points is None or len(points) < 21:
        return False
    if _dist(points[WRIST], points[MIDDLE[0]], aspect) <= 1e-9:  # no palm, bad detection
        return False
    middle = finger_ratio(points, MIDDLE, aspect)
    if middle is None or middle <= extend_ratio:
        return False
    for name in ("index", "ring", "pinky"):
        other = finger_ratio(points, FINGERS[name], aspect)
        if other is None:
            return False
        if other >= fold_ratio and middle - other < lead:
            return False
    return True


class MiddleFingerDetector:
    """Turns a stream of per-frame landmarks into a debounced, edge-triggered FLAP.

    update(landmarks, now) -> (gesture_on, flap_fired)
      * landmarks: 21 landmarks, or None when no hand is visible (resets to OFF)
      * now: time in seconds (time.monotonic() if omitted)
      * flap_fired is True only on the OFF -> ON transition, and at most once
        per min_flap_gap seconds.
    """

    def __init__(
        self,
        aspect=1.0,
        extend_ratio=EXTEND_RATIO,
        fold_ratio=FOLD_RATIO,
        on_frames=ON_FRAMES,
        off_frames=OFF_FRAMES,
        min_flap_gap=MIN_FLAP_GAP_S,
    ):
        self.aspect = aspect
        self.extend_ratio = extend_ratio
        self.fold_ratio = fold_ratio
        self.on_frames = on_frames
        self.off_frames = off_frames
        self.min_flap_gap = min_flap_gap
        self._last_flap_time = None  # kept across reset() so a quick re-detect can't double-flap
        self.reset()

    def reset(self):
        """Back to OFF. Used when the hand disappears."""
        self.gesture_on = False
        self._match_run = 0
        self._miss_run = 0

    def update(self, landmarks, now=None):
        if now is None:
            now = time.monotonic()
        if landmarks is None:
            self.reset()
            return False, False

        if pattern_matches(landmarks, self.extend_ratio, self.fold_ratio, self.aspect):
            self._match_run += 1
            self._miss_run = 0
        else:
            self._miss_run += 1
            self._match_run = 0

        flap = False
        if not self.gesture_on and self._match_run >= self.on_frames:
            self.gesture_on = True
            if self._last_flap_time is None or now - self._last_flap_time >= self.min_flap_gap:
                flap = True
                self._last_flap_time = now
        elif self.gesture_on and self._miss_run >= self.off_frames:
            self.gesture_on = False
        return self.gesture_on, flap

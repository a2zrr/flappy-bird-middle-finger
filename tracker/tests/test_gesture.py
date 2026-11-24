"""Tests for the middle-finger detector, using fake hand landmarks (no camera needed)."""

import math

import pytest

from gesture import (
    FOLD_RATIO,
    EXTEND_RATIO,
    INDEX,
    MIDDLE,
    PINKY,
    RING,
    MiddleFingerDetector,
    finger_ratios,
    pattern_matches,
)

FRAME_DT = 1 / 30  # simulated 30 fps webcam

UP = {"index": False, "middle": True, "ring": False, "pinky": False}
OPEN = {"index": True, "middle": True, "ring": True, "pinky": True}
FIST = {"index": False, "middle": False, "ring": False, "pinky": False}


def make_hand(extended, wrist=(0.5, 0.8), tilt_deg=0.0):
    """Build 21 landmarks for a hand pointing up.

    extended: dict of finger name -> bool (thumb is always placed to the side).
    Extended tips sit 0.45 from the wrist (ratio 1.5), folded tips 0.2 (ratio 0.67),
    PIP joints 0.3 from the wrist, MCP joints 0.2 from the wrist.
    """
    wx, wy = wrist
    pts = [(wx, wy)] * 21
    for i in range(1, 5):  # thumb: must not affect the result
        pts[i] = (wx - 0.15, wy - 0.05 * i)

    offsets = {"index": -0.06, "middle": 0.0, "ring": 0.06, "pinky": 0.12}
    fingers = {"index": INDEX, "middle": MIDDLE, "ring": RING, "pinky": PINKY}
    for name, (mcp, pip, dip, tip) in fingers.items():
        x = wx + offsets[name]
        is_ext = extended[name]
        pts[mcp] = (x, wy - 0.2)
        pts[pip] = (x, wy - 0.3)
        pts[dip] = (x, wy - (0.35 if is_ext else 0.25))
        pts[tip] = (x, wy - (0.45 if is_ext else 0.2))

    if tilt_deg:
        pts = rotate(pts, wrist, math.radians(tilt_deg))
    return pts


def rotate(points, center, angle):
    cx, cy = center
    c, s = math.cos(angle), math.sin(angle)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return out


def run(detector, frames, start=0.0, dt=FRAME_DT):
    """Feed frames; return (list of gesture states, total flaps, flap frame indexes)."""
    states, flaps, flap_frames = [], 0, []
    t = start
    for i, frame in enumerate(frames):
        on, flap = detector.update(frame, t)
        states.append(on)
        if flap:
            flaps += 1
            flap_frames.append(i)
        t += dt
    return states, flaps, flap_frames


# ---- single-frame pattern -------------------------------------------------

def test_middle_finger_up_matches():
    assert pattern_matches(make_hand(UP))


def test_open_hand_does_not_match():
    assert not pattern_matches(make_hand(OPEN))


def test_fist_does_not_match():
    assert not pattern_matches(make_hand(FIST))


def test_no_hand_does_not_match():
    assert not pattern_matches(None)


def test_finger_ratios_are_reported_for_debugging():
    ratios = finger_ratios(make_hand(UP))
    assert ratios["middle"] > EXTEND_RATIO
    assert ratios["index"] < FOLD_RATIO


def test_tilted_hand_still_matches():
    assert pattern_matches(make_hand(UP, tilt_deg=35))
    assert pattern_matches(make_hand(UP, tilt_deg=-35))


def test_different_hand_position_still_matches():
    assert pattern_matches(make_hand(UP, wrist=(0.2, 0.9)))


def test_aspect_ratio_does_not_break_detection():
    # 640x480 frames: x is scaled by 4/3 when measuring distances in pixels.
    assert pattern_matches(make_hand(UP), aspect=640 / 480)


# ---- detector behaviour ---------------------------------------------------

def test_middle_finger_up_turns_gesture_on():
    det = MiddleFingerDetector()
    states, _, _ = run(det, [make_hand(UP)] * 3)
    assert states == [False, True, True]


def test_open_hand_stays_off():
    det = MiddleFingerDetector()
    states, flaps, _ = run(det, [make_hand(OPEN)] * 10)
    assert not any(states)
    assert flaps == 0


def test_fist_stays_off():
    det = MiddleFingerDetector()
    states, flaps, _ = run(det, [make_hand(FIST)] * 10)
    assert not any(states)
    assert flaps == 0


def test_holding_finger_up_gives_exactly_one_flap():
    det = MiddleFingerDetector()
    _, flaps, _ = run(det, [make_hand(UP)] * 60)
    assert flaps == 1


def test_up_down_up_gives_two_flaps():
    det = MiddleFingerDetector()
    frames = [make_hand(UP)] * 15 + [make_hand(FIST)] * 10 + [make_hand(UP)] * 15
    _, flaps, _ = run(det, frames)
    assert flaps == 2


def test_one_noisy_frame_while_holding_does_not_flap_or_drop():
    det = MiddleFingerDetector()
    frames = [make_hand(UP)] * 5 + [make_hand(OPEN)] + [make_hand(UP)] * 5
    states, flaps, _ = run(det, frames)
    assert flaps == 1
    assert all(states[1:])  # the gesture stays ON through the noisy frame


def test_one_noisy_frame_alone_does_not_flap():
    det = MiddleFingerDetector()
    frames = [make_hand(FIST)] * 5 + [make_hand(UP)] + [make_hand(FIST)] * 5
    states, flaps, _ = run(det, frames)
    assert flaps == 0
    assert not any(states)


def test_hand_lost_resets_to_off():
    det = MiddleFingerDetector()
    run(det, [make_hand(UP)] * 5)
    assert det.gesture_on
    assert det.update(None, 10.0) == (False, False)
    assert not det.gesture_on


def test_hand_lost_then_back_up_flaps_again():
    det = MiddleFingerDetector()
    _, flaps, _ = run(det, [make_hand(UP)] * 5)
    det.update(None, 1.0)
    _, flap = det.update(make_hand(UP), 2.0)
    assert flaps == 1
    assert flap is False  # first matching frame only: needs ON_FRAMES in a row
    _, flap = det.update(make_hand(UP), 2.1)
    assert flap is True


def test_flap_needs_two_matching_frames_in_a_row():
    det = MiddleFingerDetector()
    states, flaps, flap_frames = run(det, [make_hand(UP)] * 2)
    assert flaps == 1
    assert flap_frames == [1]


def test_gesture_turns_off_after_two_non_matching_frames():
    det = MiddleFingerDetector()
    run(det, [make_hand(UP)] * 3)
    assert det.gesture_on
    det.update(make_hand(FIST), 1.0)
    assert det.gesture_on  # one miss is not enough
    det.update(make_hand(FIST), 1.1)
    assert not det.gesture_on


def test_min_flap_gap_blocks_fast_double_flap():
    det = MiddleFingerDetector(min_flap_gap=0.120)
    # Up/down/up in 60 ms total: the second rising edge is too soon after the first.
    frames = [make_hand(UP)] * 2 + [make_hand(FIST)] * 2 + [make_hand(UP)] * 2
    _, flaps, _ = run(det, frames, dt=0.02)
    assert flaps == 1


def test_min_flap_gap_allows_flap_after_gap():
    det = MiddleFingerDetector(min_flap_gap=0.120)
    frames = [make_hand(UP)] * 2 + [make_hand(FIST)] * 2 + [make_hand(UP)] * 2
    _, flaps, _ = run(det, frames, dt=0.2)
    assert flaps == 2


def test_thumb_position_is_ignored():
    det = MiddleFingerDetector()
    hand = make_hand(UP)
    hand[4] = (0.9, 0.1)  # thumb tip far away
    hand[3] = (0.0, 0.0)
    _, flaps, _ = run(det, [hand] * 3)
    assert flaps == 1


def test_thresholds_can_be_tuned():
    # With a very strict extend ratio, the normal hand no longer counts as up.
    det = MiddleFingerDetector(extend_ratio=2.0)
    _, flaps, _ = run(det, [make_hand(UP)] * 10)
    assert flaps == 0

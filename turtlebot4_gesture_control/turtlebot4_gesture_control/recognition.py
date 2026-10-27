"""Temporal Wave on top of real MediaPipe landmarks, not a canned AI label."""
from collections import deque
from dataclasses import dataclass
import math
from .protocol import MODEL_LABELS


@dataclass
class WaveConfig:
    window: float = 1.8
    excursion: float = 0.12  # fraction of image width between turning points
    reversals: int = 2
    min_seconds: float = 0.45
    max_gap: float = 0.25
    hold_seconds: float = 0.5
    max_vertical: float = 0.18


class WaveDetector:
    def __init__(self, config=None):
        self.c = config or WaveConfig()
        self.points = deque()
        self.wave_until = 0.
        self.hand = None

    def reset(self):
        self.points.clear()
        self.wave_until = 0.
        self.hand = None

    def update(self, x, y, now, hand='Right'):
        c = self.c
        if self.points and (now-self.points[-1][0] > c.max_gap or hand != self.hand):
            self.reset()
        self.hand = hand
        self.points.append((now, x, y))
        while self.points and now-self.points[0][0] > c.window:
            self.points.popleft()
        if len(self.points) < 4:
            return now < self.wave_until
        if max(p[2] for p in self.points)-min(p[2] for p in self.points) > c.max_vertical:
            self.points.clear()
            self.wave_until = 0.
            return False
        anchor = self.points[0][1]
        direction, reversals = 0, 0
        extreme = anchor
        for _, px, _ in self.points:
            if direction == 0:
                if abs(px-anchor) >= c.excursion:
                    direction = 1 if px > anchor else -1
                    extreme = px
            elif direction*(px-extreme) > 0:
                extreme = px
            elif direction*(px-extreme) <= -c.excursion:
                reversals += 1
                direction *= -1
                extreme = px
        if reversals >= c.reversals and now-self.points[0][0] >= c.min_seconds:
            self.wave_until = now+c.hold_seconds
        return now < self.wave_until


class Recognizer:
    def __init__(self, model_path, confidence=0.65, stop_confidence=0.45, wave=None):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        self.mp = mp
        self.threshold, self.stop_threshold = confidence, stop_confidence
        self.wave = WaveDetector(wave)
        opts = vision.GestureRecognizerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5, min_tracking_confidence=0.5)
        self.model = vision.GestureRecognizer.create_from_options(opts)
        self.last_ms = 0

    def process(self, bgr, now, executing=False):
        import cv2
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        ms = max(self.last_ms+1, int(now*1000))
        self.last_ms = ms
        result = self.model.recognize_for_video(self.mp.Image(
            image_format=self.mp.ImageFormat.SRGB, data=rgb), ms)
        hands = result.hand_landmarks
        if not hands:
            self.wave.reset()
            return 'NO_HAND', 0., result
        # Multiple hands are ambiguous: palm/fist still stop, other commands refused.
        categories = [gs[0] for gs in result.gestures if gs]
        for cat in categories:
            if cat.category_name in ('Open_Palm', 'Closed_Fist') and cat.score >= self.stop_threshold:
                if len(hands) > 1 or cat.category_name == 'Closed_Fist' or executing:
                    self.wave.reset()
                    return MODEL_LABELS[cat.category_name], cat.score, result
        if len(hands) != 1 or not categories:
            self.wave.reset()
            return 'UNKNOWN', 0., result
        cat = categories[0]
        label = MODEL_LABELS.get(cat.category_name, 'UNKNOWN')
        threshold = self.stop_threshold if label == 'OPEN_PALM' else self.threshold
        if cat.score < threshold:
            # Brief low confidence must not erase all motion history.
            # update() still enforces max_gap before accepting the next palm.
            return 'UNKNOWN', cat.score, result
        if label == 'OPEN_PALM':
            # Wave requires a confident palm, not just a low-confidence safety stop.
            if cat.score >= self.threshold:
                palm = hands[0]
                x = sum(palm[i].x for i in (0, 5, 9, 13, 17))/5
                y = sum(palm[i].y for i in (0, 5, 9, 13, 17))/5
                hand = result.handedness[0][0].category_name
                if self.wave.update(x, y, now, hand):
                    return 'WAVE', cat.score, result
            else:
                self.wave.reset()
        elif label != 'UNKNOWN':
            self.wave.reset()
        return label, cat.score, result

    def close(self):
        self.model.close()

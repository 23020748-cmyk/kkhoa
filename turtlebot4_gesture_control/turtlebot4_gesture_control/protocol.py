"""Shared strict JSON v1 contract inside std_msgs/String. No Python eval."""
import json
import math
import time
import uuid

LABELS = {'WAVE', 'POINTING_UP', 'VICTORY', 'THUMBS_UP', 'OPEN_PALM',
          'CLOSED_FIST', 'NO_HAND', 'UNKNOWN', 'CAMERA_ERROR'}
MODEL_LABELS = {'Pointing_Up': 'POINTING_UP', 'Victory': 'VICTORY',
                'Thumb_Up': 'THUMBS_UP', 'Open_Palm': 'OPEN_PALM',
                'Closed_Fist': 'CLOSED_FIST'}


class Encoder:
    def __init__(self):
        self.session = uuid.uuid4().hex
        self.seq = 0

    def encode(self, label, confidence=0.0, frame_age=0.0):
        self.seq += 1
        return json.dumps(dict(v=1, session=self.session, seq=self.seq,
                               stamp=time.time(), frame_age=frame_age,
                               label=label, confidence=float(confidence)),
                          allow_nan=False)


def decode(raw, max_age=0.7):
    d = json.loads(raw)
    if not isinstance(d, dict) or d.get('v') != 1:
        raise ValueError('bad schema')
    if d.get('label') not in LABELS:
        raise ValueError('unknown label')
    if not isinstance(d.get('session'), str) or not 1 <= len(d['session']) <= 64:
        raise ValueError('bad session')
    if type(d.get('seq')) is not int or d['seq'] < 1:
        raise ValueError('bad sequence')
    for key in ('confidence', 'stamp', 'frame_age'):
        if type(d.get(key)) not in (float, int) or not math.isfinite(d[key]):
            raise ValueError('non-finite field')
    if not 0 <= d['confidence'] <= 1 or not 0 <= d['frame_age'] <= max_age:
        raise ValueError('bad confidence/frame age')
    age = time.time() - d['stamp']
    if not -0.2 <= age <= max_age:
        raise ValueError('stale message / clocks differ')
    return d

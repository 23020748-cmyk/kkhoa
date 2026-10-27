"""Fresh frames from local OpenCV or the supplied Windows JPEG bridge."""
import time
import urllib.request
import json
from pathlib import Path


class Camera:
    def __init__(self, source='0'):
        import cv2
        self.cv2, self.source = cv2, str(source)
        self.cap = None
        self.last_seq = None
        if not self.source.startswith(('http://', 'https://', 'file://')):
            index = int(self.source) if self.source.isdecimal() else self.source
            self.cap = cv2.VideoCapture(index)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not self.cap.isOpened():
                raise RuntimeError(f'Cannot open camera {self.source}; WSL needs /dev/video or Windows bridge')

    def read(self):
        if self.cap is not None:
            return self._read_once()
        deadline = time.monotonic()+0.3
        while True:
            try:
                return self._read_once()
            except (OSError, RuntimeError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.015)  # worker only; ROS watchdog never blocks

    def _read_once(self):
        if self.cap is not None:
            ok, image = self.cap.read()
            if not ok:
                raise RuntimeError('camera read failed')
            return image
        import numpy as np
        if self.source.startswith('file://'):
            data = Path(self.source[7:]).read_bytes()
            header, jpeg = data.split(b'\n', 1)
            meta = json.loads(header)
            age = time.time()-meta['stamp']
            if not -0.1 <= age <= 0.35 or meta['seq'] == self.last_seq:
                raise RuntimeError('stale/duplicate local bridge frame')
            self.last_seq = meta['seq']
            image = self.cv2.imdecode(np.frombuffer(jpeg, np.uint8), self.cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError('local JPEG decode failed')
            return image
        with urllib.request.urlopen(self.source, timeout=0.4) as response:
            # Bridge refuses stale camera data. Also reject duplicates here.
            age = float(response.headers['X-Frame-Age'])
            seq = response.headers['X-Frame-Seq']
            if age > 0.35 or seq == self.last_seq:
                raise RuntimeError('stale/duplicate bridge frame')
            data = response.read(2_000_000)
        self.last_seq = seq
        image = self.cv2.imdecode(np.frombuffer(data, np.uint8), self.cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError('JPEG decode failed')
        return image

    def close(self):
        if self.cap is not None:
            self.cap.release()

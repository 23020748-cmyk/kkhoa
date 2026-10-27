"""Official, versioned Google model; local digest recorded for reproducibility."""
import hashlib
from pathlib import Path
import urllib.request
URL = 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task'
target = Path(__file__).resolve().parents[1]/'models/gesture_recognizer.task'
target.parent.mkdir(exist_ok=True)
if not target.exists():
    temporary = target.with_suffix('.tmp')
    urllib.request.urlretrieve(URL, temporary)
    temporary.replace(target)
digest = hashlib.sha256(target.read_bytes()).hexdigest()
target.with_suffix('.task.sha256').write_text(digest+'  gesture_recognizer.task\n')
print(URL, target.stat().st_size, digest)

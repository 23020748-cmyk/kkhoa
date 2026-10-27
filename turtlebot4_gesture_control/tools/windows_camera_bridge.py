"""Run on Windows Python with OpenCV. Serves latest JPEG only, never buffered video."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import signal
import threading
import time
import cv2
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--index', type=int, default=0)
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=8765)
parser.add_argument('--seconds', type=float, default=0, help='0 = until Ctrl+C')
parser.add_argument('--snapshot')
parser.add_argument('--output', help='Atomic local frame file; disables HTTP entirely')
args = parser.parse_args()
lock = threading.Lock()
latest = None
end = threading.Event()


def capture():
    global latest
    cap = cv2.VideoCapture(args.index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(args.index, cv2.CAP_MSMF)
    print(json.dumps(dict(opened=cap.isOpened(), opencv=cv2.__version__,
                          backend=cap.getBackendName() if cap.isOpened() else None)), flush=True)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    seq = 0
    try:
        while not end.is_set() and cap.isOpened():
            ok, image = cap.read()
            if not ok:
                break
            ok, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                seq += 1
                with lock:
                    latest = (time.monotonic(), seq, jpeg.tobytes())
                if args.output:
                    target = Path(args.output)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix('.tmp')
                    header = json.dumps(dict(stamp=time.time(), seq=seq)).encode()+b'\n'
                    temporary.write_bytes(header+jpeg.tobytes())
                    # Windows/WSL can briefly deny replacement while a reader holds the file.
                    # Skip this frame rather than leaving a dead camera worker.
                    try:
                        os.replace(temporary, target)
                    except PermissionError:
                        pass
                if seq == 1 and args.snapshot:
                    cv2.imwrite(args.snapshot, image)
            end.wait(0.04)
    finally:
        cap.release()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/frame':
            self.send_error(404)
            return
        with lock:
            frame = latest
        if frame is None or time.monotonic()-frame[0] > 0.35:
            self.send_error(503, 'No fresh camera image')
            return
        age = time.monotonic()-frame[0]
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Age', str(age))
        self.send_header('X-Frame-Seq', str(frame[1]))
        self.send_header('Content-Length', str(len(frame[2])))
        self.end_headers()
        try:
            self.wfile.write(frame[2])
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    threading.Thread(target=capture, daemon=True).start()
    if args.output:
        print(f'Local file bridge: {args.output} (no network listener)', flush=True)
        started = time.monotonic()
        try:
            while not args.seconds or time.monotonic()-started < args.seconds:
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            end.set()
        raise SystemExit(0)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    server.timeout = 0.2
    print(f'Camera bridge http://{args.host}:{args.port}/frame', flush=True)
    started = time.monotonic()
    try:
        while not args.seconds or time.monotonic()-started < args.seconds:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        end.set()
        server.server_close()

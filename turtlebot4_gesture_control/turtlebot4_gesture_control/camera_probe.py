import argparse
import json
import sys
from .camera import Camera


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='0')
    parser.add_argument('--frames', type=int, default=20)
    parser.add_argument('--save')
    args = parser.parse_args()
    camera = None
    try:
        import cv2
        camera = Camera(args.source)
        import time
        for _ in range(args.frames):
            image = camera.read()
            time.sleep(0.09)
        if args.save:
            cv2.imwrite(args.save, image)
        print(json.dumps(dict(ok=True, source=args.source, shape=list(image.shape),
                              opencv=cv2.__version__,
                              backend=camera.cap.getBackendName() if camera.cap else ('atomic local JPEG' if args.source.startswith('file://') else 'fresh HTTP JPEG'))))
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=str(exc))))
        sys.exit(1)
    finally:
        if camera:
            camera.close()


if __name__ == '__main__':
    main()

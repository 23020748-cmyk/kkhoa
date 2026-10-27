"""Capture/inference worker cannot block ROS heartbeat or stop publication."""
import json
import threading
import time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from std_msgs.msg import String
from .camera import Camera
from .recognition import Recognizer, WaveConfig
from .protocol import Encoder
from .robot_behavior_node import QOS


class GestureRecognitionNode(Node):
    def __init__(self):
        super().__init__('gesture_recognition_node')
        defaults = dict(camera_source='0', model_path=str(Path.home()/'ros2_ws/src/turtlebot4_gesture_control/models/gesture_recognizer.task'),
                        confidence=0.65, stop_confidence=0.45, rate=12.0, mirror=True,
                        show_window=True, frame_timeout=0.45, evidence_dir='')
        self.p = {k: self.declare_parameter(k, v).value for k, v in defaults.items()}
        wave = WaveConfig()
        self.wave = WaveConfig(**{k: self.declare_parameter('wave_'+k, v).value
                                  for k, v in vars(wave).items()})
        if not 1 <= self.p['rate'] <= 30 or self.p['frame_timeout'] <= 0:
            raise ValueError('invalid rate/frame timeout')
        self.pub = self.create_publisher(String, '/detected_gesture', QOS)
        self.sub = self.create_subscription(String, '/gesture_control/status', self.on_status, QOS)
        self.encoder = Encoder()
        self.status = 'waiting for controller'
        self.executing = False
        self.lock = threading.Lock()
        self.latest = None
        self.saved_labels = set()
        self.end = threading.Event()
        self.worker = threading.Thread(target=self.capture, daemon=True)
        self.worker.start()
        self.timer = self.create_timer(1/self.p['rate'], self.on_timer,
                                      clock=Clock(clock_type=ClockType.STEADY_TIME))

    def on_status(self, msg):
        try:
            d = json.loads(msg.data)
            self.executing = d['state'] == 'EXECUTING'
            self.status = f"{d['state']} | {d['selected']} | {d['reason']}"
        except (ValueError, KeyError):
            self.status = 'invalid controller status'

    def capture(self):
        camera = model = None
        try:
            camera = Camera(self.p['camera_source'])
            model = Recognizer(self.p['model_path'], self.p['confidence'],
                               self.p['stop_confidence'], self.wave)
            while not self.end.is_set():
                start = time.monotonic()
                try:
                    image = camera.read()
                except (OSError, RuntimeError) as exc:
                    with self.lock:
                        self.latest = None
                    self.get_logger().warning(f'Camera temporarily unavailable: {exc}',
                                              throttle_duration_sec=3.)
                    # Recover recognition, never resume a stopped behavior automatically.
                    self.end.wait(0.1)
                    continue
                acquired = time.monotonic()
                if self.p['mirror']:
                    import cv2
                    image = cv2.flip(image, 1)
                label, confidence, result = model.process(image, acquired, self.executing)
                with self.lock:
                    self.latest = (acquired, label, confidence, image, result)
                self.end.wait(max(0., 1/self.p['rate']-(time.monotonic()-start)))
        except Exception as exc:
            self.get_logger().error(f'Camera/AI worker stopped: {exc}')
            with self.lock:
                self.latest = None
        finally:
            if model:
                model.close()
            if camera:
                camera.close()

    def on_timer(self):
        with self.lock:
            latest = self.latest
        age = time.monotonic()-latest[0] if latest else 1e6
        if latest and age <= self.p['frame_timeout']:
            _, label, confidence, image, result = latest
            self.pub.publish(String(data=self.encoder.encode(label, confidence, age)))
            if self.p['show_window']:
                self.show(image.copy(), label, confidence, result)
        else:
            self.pub.publish(String(data=self.encoder.encode('CAMERA_ERROR', 0., 0.)))
            if self.p['show_window']:
                import cv2
                import numpy as np
                image = np.zeros((220, 700, 3), dtype=np.uint8)
                cv2.putText(image, 'CAMERA/AI STALE - ROBOT STOP', (15, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow('TB4 Gesture Control', image)
                cv2.waitKey(1)

    def show(self, image, label, confidence, result):
        import cv2
        h, w = image.shape[:2]
        for hand in result.hand_landmarks:
            for p in hand:
                cv2.circle(image, (int(p.x*w), int(p.y*h)), 3, (0, 255, 0), -1)
        for i, text in enumerate([f'{label} confidence={confidence:.2f}', self.status,
                                  'Palm: STOP | Fist: CANCEL | Thumb: CONFIRM']):
            cv2.putText(image, text, (8, 25+27*i), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 220, 255), 2)
        if self.p['evidence_dir'] and label not in self.saved_labels:
            folder = Path(self.p['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(folder/(label.lower()+'.jpg')), image)
            self.saved_labels.add(label)
        cv2.imshow('TB4 Gesture Control', image)
        cv2.waitKey(1)  # GUI event pump only; keyboard never controls robot.

    def close(self):
        self.pub.publish(String(data=self.encoder.encode('CAMERA_ERROR')))
        self.end.set()
        self.worker.join(timeout=1.)
        import cv2
        cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = GestureRecognitionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            if rclpy.ok():
                node.close()
            else:
                node.end.set()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

import json
import signal
import time
from dataclasses import fields
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from .behavior import Config, Controller
from .protocol import decode

QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                 durability=DurabilityPolicy.VOLATILE)


class RobotBehaviorNode(Node):
    def __init__(self):
        super().__init__('robot_behavior_node')
        defaults = Config()
        values = {f.name: self.declare_parameter(f.name, getattr(defaults, f.name)).value
                  for f in fields(defaults)}
        self.engine = Controller(Config(**values))
        topic = self.declare_parameter('cmd_vel_topic', '/cmd_vel').value
        self.cmd = self.create_publisher(Twist, topic, QOS)
        self.status_pub = self.create_publisher(String, '/gesture_control/status', QOS)
        self.sub = self.create_subscription(String, '/detected_gesture', self.on_gesture, QOS)
        self.session, self.seq = None, 0
        self.old_sessions = set()
        # Never let paused /clock disable the safety watchdog.
        self.timer = self.create_timer(0.05, self.on_timer,
                                      clock=Clock(clock_type=ClockType.STEADY_TIME))

    def publish_velocity(self, velocity):
        message = Twist()
        message.linear.x, message.angular.z = map(float, velocity)
        self.cmd.publish(message)

    def on_gesture(self, message):
        try:
            d = decode(message.data)
            if d['session'] in self.old_sessions:
                raise ValueError('retired session')
            if d['session'] != self.session:
                if self.session is not None:
                    self.old_sessions.add(self.session)
                    self.engine.stop('recognizer_restarted')
                    self.publish_velocity((0., 0.))
                self.session, self.seq = d['session'], 0
            if d['seq'] <= self.seq:
                raise ValueError('replayed/out-of-order sequence')
            self.seq = d['seq']
            self.publish_velocity(self.engine.receive(d['label'], d['confidence'], time.monotonic()))
        except Exception as exc:
            self.publish_velocity(self.engine.stop('invalid_message'))
            self.get_logger().warning(str(exc))

    def on_timer(self):
        try:
            self.publish_velocity(self.engine.tick(time.monotonic()))
            self.status_pub.publish(String(data=json.dumps(self.engine.status())))
        except Exception:
            self.safe_stop('timer_exception')
            raise

    def safe_stop(self, reason='shutdown'):
        self.engine.stop(reason)
        # A short burst helps delivery; no sleeps and no blocking callback.
        for _ in range(5):
            self.publish_velocity((0., 0.))


def main(args=None):
    # Handle SIGINT/SIGTERM while DDS context is still alive, allowing final zeros.
    rclpy.init(args=args, signal_handler_options=rclpy.signals.SignalHandlerOptions.NO)
    node = None
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        node = RobotBehaviorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.safe_stop()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

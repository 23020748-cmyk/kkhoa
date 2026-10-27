"""Real Gazebo smoke test. No fabricated gesture messages, 0.03 m/s for 1 s."""
import argparse
import json
import math
import time
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data

p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
args = p.parse_args()
rclpy.init()
node = rclpy.create_node('gesture_small_motion_check')
pub = node.create_publisher(Twist, '/cmd_vel', 1)
poses = []
def odom(msg):
    poses.append((time.monotonic(), msg.pose.pose.position.x, msg.pose.pose.position.y))
sub = node.create_subscription(Odometry, '/odom', odom, qos_profile_sensor_data)
result = {'test': 'REAL_GAZEBO_SMALL_MOTION', 'speed': 0.03, 'seconds': 1.0}
try:
    deadline = time.monotonic()+12
    while time.monotonic() < deadline and (not poses or pub.get_subscription_count() == 0):
        rclpy.spin_once(node, timeout_sec=.1)
    if not poses or pub.get_subscription_count() == 0:
        raise RuntimeError('No odometry or cmd_vel subscriber; motion refused')
    if node.count_publishers('/cmd_vel') > 1:
        raise RuntimeError('Other velocity publisher present; motion refused')
    before = poses[-1]
    begin = time.monotonic()
    while time.monotonic()-begin < 1.:
        msg = Twist()
        msg.linear.x = .03
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=.05)
    pub.publish(Twist())
    deadline = time.monotonic()+1.
    while time.monotonic() < deadline:
        pub.publish(Twist())
        rclpy.spin_once(node, timeout_sec=.05)
    after = poses[-1]
    result.update(before=before[1:], after=after[1:],
                  displacement=math.hypot(after[1]-before[1], after[2]-before[2]),
                  odom_samples=len(poses), subscriber_count=pub.get_subscription_count())
    result['passed'] = .001 < result['displacement'] < .08
except Exception as exc:
    result.update(passed=False, error=str(exc))
finally:
    for _ in range(10):
        pub.publish(Twist())
        rclpy.spin_once(node, timeout_sec=.02)
    with open(args.output, 'w') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
    node.destroy_node()
    rclpy.shutdown()
if not result['passed']:
    raise SystemExit(1)

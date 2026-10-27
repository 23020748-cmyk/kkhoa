"""Observe only: no gesture/velocity publisher, no artificial input."""
import argparse
from collections import Counter
import json
import time
from pathlib import Path
import rclpy
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data

p = argparse.ArgumentParser()
p.add_argument('--seconds', type=float, default=20)
p.add_argument('--output', required=True)
args = p.parse_args()
rclpy.init()
node = rclpy.create_node('gesture_live_observer')
counts = Counter()
states = Counter()
commands = []
odometry = []
errors = []
events = []
previous_label = None
previous_state = None
def gesture(msg):
    global previous_label
    try:
        d = json.loads(msg.data)
        counts[d['label']] += 1
        if d['label'] != previous_label:
            events.append(dict(stamp=time.time(), kind='gesture', label=d['label'], confidence=d['confidence']))
            previous_label = d['label']
    except Exception as exc:
        errors.append(str(exc))
def status(msg):
    global previous_state
    d = json.loads(msg.data)
    states[d['state']] += 1
    signature = (d['state'], d['selected'], d['reason'])
    if signature != previous_state:
        events.append(dict(stamp=time.time(), kind='state', **d))
        previous_state = signature
def velocity(msg):
    commands.append((msg.linear.x, msg.angular.z))
def odom(msg):
    odometry.append((msg.pose.pose.position.x, msg.pose.pose.position.y))
subscriptions = [
    node.create_subscription(String, '/detected_gesture', gesture, 1),
    node.create_subscription(String, '/gesture_control/status', status, 1),
    node.create_subscription(Twist, '/cmd_vel', velocity, 1),
    node.create_subscription(Odometry, '/odom', odom, qos_profile_sensor_data)]
start = time.monotonic()
while time.monotonic()-start < args.seconds:
    rclpy.spin_once(node, timeout_sec=.1)
result = dict(kind='REAL_LIVE_OBSERVATION_NO_SYNTHETIC_INPUT', seconds=args.seconds,
              gestures=dict(counts), states=dict(states), command_count=len(commands),
              nonzero_commands=sum(abs(v)+abs(w)>1e-6 for v,w in commands),
              odom_samples=len(odometry), first_odom=odometry[0] if odometry else None,
              last_odom=odometry[-1] if odometry else None, errors=errors, events=events)
Path(args.output).write_text(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k != 'events'}))
node.destroy_node()
rclpy.shutdown()

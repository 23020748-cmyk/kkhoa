"""Actual DDS transport on isolated topics; NOT evidence of AI/Gazebo gestures."""
import os
import signal
import subprocess
import time
import pytest
rclpy = pytest.importorskip('rclpy')
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from turtlebot4_gesture_control.protocol import Encoder


def test_ros_transport_invalid_input_watchdog_and_sigterm(tmp_path):
    rclpy.init()
    node = rclpy.create_node('gesture_wrapper_test')
    velocities = []
    states = []
    diagnostics = open(tmp_path/'controller.log', 'w')
    state_sub = node.create_subscription(String, '/gesture_test/status', lambda m: states.append(m.data), 10)
    pub = node.create_publisher(String, '/gesture_test/input', 1)
    sub = node.create_subscription(Twist, '/gesture_test/cmd', lambda m: velocities.append(
        (time.monotonic(), m.linear.x, m.angular.z)), 10)
    process = subprocess.Popen(
        ['ros2', 'run', 'turtlebot4_gesture_control', 'robot_behavior_node',
         '--ros-args', '-p', 'cmd_vel_topic:=/gesture_test/cmd',
         '-r', '/detected_gesture:=/gesture_test/input',
         '-r', '/gesture_control/status:=/gesture_test/status'],
        stdout=diagnostics, stderr=diagnostics, start_new_session=True)
    encoder = Encoder()
    def spin(seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.02)
    def send(label, seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            pub.publish(String(data=encoder.encode(label, .99)))
            spin(.06)
    try:
        deadline = time.monotonic()+12
        while time.monotonic() < deadline and (not velocities or pub.get_subscription_count() == 0):
            spin(.1)
        assert velocities and pub.get_subscription_count() > 0
        send('POINTING_UP', 1.0)
        assert all(v == 0 and w == 0 for _,v,w in velocities)
        send('THUMBS_UP', 1.0)
        assert any(v > 0 for _,v,_ in velocities), str(states[-15:])
        pub.publish(String(data='not-json'))
        spin(.4)
        assert velocities[-1][1:] == (0., 0.)
        send('VICTORY', 1.0)
        send('THUMBS_UP', 1.0)
        assert velocities[-1][1] > 0, str(states[-15:])
        spin(1.)
        assert velocities[-1][1:] == (0., 0.)
        send('POINTING_UP', 1.0)
        send('THUMBS_UP', 1.0)
        assert velocities[-1][1] > 0, str(states[-15:])
        # SIGTERM to the process group: node's finally sends zero while DDS alive.
        os.killpg(process.pid, signal.SIGTERM)
        spin(.3)
        assert velocities[-1][1:] == (0., 0.)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
        node.destroy_node()
        rclpy.shutdown()
        diagnostics.close()
        print((tmp_path/'controller.log').read_text()[-4000:])

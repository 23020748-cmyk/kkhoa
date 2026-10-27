"""Standalone DDS exception probe; only invoked by unit tests."""
import time
import rclpy
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import Twist
from turtlebot4_gesture_control.robot_behavior_node import RobotBehaviorNode

rclpy.init(args=['--ros-args','-p','cmd_vel_topic:=/gesture_exception/cmd',
                 '-r','/detected_gesture:=/gesture_exception/input',
                 '-r','/gesture_control/status:=/gesture_exception/status'])
node = RobotBehaviorNode()
node.timer.cancel()
observer = rclpy.create_node('gesture_exception_observer')
received = []
sub = observer.create_subscription(Twist, '/gesture_exception/cmd',
    lambda m: received.append((m.linear.x,m.angular.z)), 10)
executor = SingleThreadedExecutor()
executor.add_node(node)
executor.add_node(observer)
def spin(seconds):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        executor.spin_once(timeout_sec=.02)
try:
    until = time.monotonic()+8
    while time.monotonic() < until and node.cmd.get_subscription_count() == 0:
        spin(.1)
    assert node.cmd.get_subscription_count() > 0
    node.publish_velocity((.03,0.))
    spin(.3)
    assert received and received[-1] == (.03,0.), received
    def fail(now):
        raise RuntimeError('injected timer error: unit test only')
    node.engine.tick = fail
    caught = False
    try:
        node.on_timer()
    except RuntimeError:
        caught = True
    assert caught
    spin(.3)
    assert received[-1] == (0.,0.), received
    assert node.engine.state == 'STOPPED'
    assert node.engine.reason == 'timer_exception'
    print('EXCEPTION_DDS_ZERO_VERIFIED')
finally:
    node.safe_stop()
    spin(.1)
    executor.shutdown()
    node.destroy_node()
    observer.destroy_node()
    rclpy.shutdown()

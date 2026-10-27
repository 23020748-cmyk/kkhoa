from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import os


def generate_launch_description():
    share = get_package_share_directory('turtlebot4_gesture_control')
    config = os.path.join(share, 'config', 'gesture_control.yaml')
    behavior = Node(package='turtlebot4_gesture_control', executable='robot_behavior_node',
                    parameters=[config, {'cmd_vel_topic': LaunchConfiguration('cmd_vel_topic')}],
                    output='screen')
    recognition = Node(package='turtlebot4_gesture_control', executable='gesture_recognition_node',
                       parameters=[config, {
                           'camera_source': ParameterValue(LaunchConfiguration('camera_source'), value_type=str),
                           'model_path': LaunchConfiguration('model_path'),
                           'evidence_dir': LaunchConfiguration('evidence_dir'),
                           'show_window': ParameterValue(LaunchConfiguration('show_window'), value_type=bool)}],
                       output='screen')
    return LaunchDescription([
        DeclareLaunchArgument('camera_source', default_value='0'),
        DeclareLaunchArgument('cmd_vel_topic', default_value='/cmd_vel'),
        DeclareLaunchArgument('evidence_dir', default_value=''),
        DeclareLaunchArgument('show_window', default_value='true'),
        DeclareLaunchArgument('model_path', default_value=os.path.expanduser(
            '~/ros2_ws/src/turtlebot4_gesture_control/models/gesture_recognizer.task')),
        behavior, recognition,
        RegisterEventHandler(OnProcessExit(target_action=behavior,
            on_exit=[EmitEvent(event=Shutdown(reason='controller exited'))])),
        RegisterEventHandler(OnProcessExit(target_action=recognition,
            on_exit=[EmitEvent(event=Shutdown(reason='recognition exited'))]))
    ])

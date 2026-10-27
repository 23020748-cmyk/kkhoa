"""Use surveyed local TurtleBot4 launch files; isolated 12 m empty arena."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    own = get_package_share_directory('turtlebot4_gesture_control')
    old = get_package_share_directory('turtlebot4_slam_nav2')
    world_stem = os.path.join(own, 'worlds', 'gesture_arena')
    def include(filename, args):
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(
            os.path.join(old, 'launch', filename)), launch_arguments=args.items())
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true'),
        SetEnvironmentVariable('FASTDDS_BUILTIN_TRANSPORTS', 'UDPv4'),
        SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),
        include('ignition.launch.py', {'world': world_stem, 'gui': LaunchConfiguration('gui'),
                                      'model': 'lite'}),
        include('turtlebot4_spawn.launch.py', {
            'world': 'gesture_arena', 'x': '0.0', 'y': '0.0', 'z': '0.05',
            'model': 'lite', 'rviz': 'false', 'low_resource': 'true',
            'slam': 'false', 'nav2': 'false', 'localization': 'false',
            'camera_enabled': 'false', 'spawn_dock': 'false'})
    ])

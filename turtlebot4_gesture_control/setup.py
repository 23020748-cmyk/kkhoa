from glob import glob
from setuptools import setup, find_packages
setup(name='turtlebot4_gesture_control', version='0.1.0',
      packages=find_packages(exclude=['test']), install_requires=['setuptools'],
      data_files=[('share/ament_index/resource_index/packages', ['resource/turtlebot4_gesture_control']),
                  ('share/turtlebot4_gesture_control', ['package.xml', 'README.md']),
                  ('share/turtlebot4_gesture_control/launch', glob('launch/*.launch.py')),
                  ('share/turtlebot4_gesture_control/config', glob('config/*.yaml')),
                  ('share/turtlebot4_gesture_control/worlds', glob('worlds/*.sdf'))],
      tests_require=['pytest'], zip_safe=True, maintainer='Khoa', maintainer_email='khoa@example.com',
      description='MediaPipe gesture control', license='Apache-2.0',
      entry_points={'console_scripts': [
          'gesture_recognition_node = turtlebot4_gesture_control.gesture_recognition_node:main',
          'robot_behavior_node = turtlebot4_gesture_control.robot_behavior_node:main',
          'camera_probe = turtlebot4_gesture_control.camera_probe:main']})

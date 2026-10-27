#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/../../.."
source /opt/ros/humble/setup.bash
source install/setup.bash
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD/.venv-gesture/lib/python3.10/site-packages:${PYTHONPATH:-}"
exec ros2 launch turtlebot4_gesture_control gesture_control.launch.py "$@"

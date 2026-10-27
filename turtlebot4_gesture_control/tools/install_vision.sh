#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
export PYTHONNOUSERSITE=1
python3 -m venv --system-site-packages .venv-gesture
.venv-gesture/bin/python -m pip install -r src/turtlebot4_gesture_control/requirements-vision.txt
mkdir -p src/turtlebot4_gesture_control/models
.venv-gesture/bin/python src/turtlebot4_gesture_control/tools/download_model.py
.venv-gesture/bin/python -c 'import cv2, mediapipe, numpy, rclpy; print("OpenCV",cv2.__version__,"MediaPipe",mediapipe.__version__,"NumPy",numpy.__version__)'

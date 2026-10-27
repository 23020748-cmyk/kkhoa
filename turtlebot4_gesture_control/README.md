# Bài tập 6 - Điều khiển TurtleBot 4 bằng cử chỉ
Package ROS 2 Humble ament_python, Ubuntu 22.04/Python 3.10.
Source nhận diện, giao thức, máy trạng thái tách riêng. Không cần Nav2/bản đồ.
Không dùng bàn phím điều khiển khi demo.

## Cài đặt (Ubuntu/WSL)
```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
# Nếu python3 -m venv chưa có: sudo apt install python3-venv
bash src/turtlebot4_gesture_control/tools/install_vision.sh
colcon build --symlink-install --packages-select turtlebot4_gesture_control
source install/setup.bash
```
Vision dùng venv riêng `.venv-gesture` (--system-site-packages để đọc rclpy),
không thay Python hệ thống. Bản ghim: MediaPipe 0.10.14, OpenCV contrib
4.8.1.78, NumPy 1.26.4, protobuf 4.25.8. Trình chạy chèn site-packages venv
cho executable ROS vốn dùng /usr/bin/python3. Build bằng Python ROS mặc định.
Không dùng --break-system-packages.

Model chính thức phiên bản float16/1:
https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task
Script download_model.py tải model và lưu SHA256; model không commit Git.
Xem giấy phép/model card tại
https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer

## Simulation được khảo sát
Workspace có turtlebot4_slam_nav2 với ignition.launch.py,
turtlebot4_spawn.launch.py và lean_control.launch.py. Launch mới include
các file này, dùng robot Lite, official ros2_control, không bật SLAM/Nav2. World tắt Sensors renderer để tránh lỗi OpenGL headless WSL; /scan bridge có thể tồn tại nhưng không phát dữ liệu. Điều khiển không sử dụng LaserScan.
```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
ros2 launch turtlebot4_gesture_control gesture_sim.launch.py gui:=true
```
Dùng gui:=false khi test server. Chờ controller spawner (30-60 giây).
World riêng gesture_arena: mặt phẳng 12x12 m, xuất phát (0,0), không vật cản.
Đừng khởi chạy đồng thời simulation/teleop/Nav2 khác.

## Camera Ubuntu trực tiếp
```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
PYTHONPATH="$PWD/.venv-gesture/lib/python3.10/site-packages:$PYTHONPATH" \
  ros2 run turtlebot4_gesture_control camera_probe --source 0
```
Kiểm tra ls -l /dev/video*; groups; quyền video.
WSL khảo sát không có /dev/video*: webcam Windows không tự xuất hiện trong WSL.

## Cầu nối webcam Windows sang WSL (không dùng mạng)
Mở PowerShell Windows, chạy:
```powershell
& 'C:\Users\khoa8\miniconda3\python.exe' '\\wsl.localhost\Ubuntu-22.04\home\khoa\ros2_ws\src\turtlebot4_gesture_control\tools\windows_camera_bridge.py' --output 'C:\Users\khoa8\Downloads\turtlebot4_gesture_runtime\camera.frame'
```
Đây là Python Windows có OpenCV 5.0.0 đã kiểm tra, backend DSHOW
(fallback MSMF). Không mở cổng mạng. Ghi JPEG kèm timestamp/sequence vào file
tạm rồi replace nguyên tử; Ubuntu đọc qua /mnt/c. Không đặt file runtime trong UNC WSL/AppData vì đã gặp lỗi khóa file và Store virtualization.
Ảnh cũ quá 0,35 s, ảnh lặp, lỗi camera/AI đều dẫn tới dừng.
File runtime được ghi đè liên tục, không nằm trong repo. Ảnh bằng chứng private được gitignore; không tự đưa ảnh cá nhân lên GitHub.

Trong Ubuntu WSL:
```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export CAMERA_URL="file:///mnt/c/Users/khoa8/Downloads/turtlebot4_gesture_runtime/camera.frame"
PYTHONPATH="$PWD/.venv-gesture/lib/python3.10/site-packages:$PYTHONPATH" \
  ros2 run turtlebot4_gesture_control camera_probe --source "$CAMERA_URL"
bash src/turtlebot4_gesture_control/tools/run.sh camera_source:="$CAMERA_URL"
```
WSL đã khảo sát dùng NAT; localhost Windows không truy cập được từ Ubuntu.
Không cần đổi firewall/ExecutionPolicy/networkingMode.
Nếu camera bị từ chối: Settings > Privacy & security > Camera > quyền
desktop apps; đóng Zoom/Camera/Teams nếu đang chiếm webcam.
Bridge còn hỗ trợ endpoint JPEG HTTP với header X-Frame-Age/X-Frame-Seq,
nhưng luồng chính đã chọn file nội bộ; không cần sử dụng HTTP.
Không hỗ trợ URL MJPEG tùy ý qua backend JPEG này.

## Khởi chạy
Camera gắn trực tiếp: bash tools/run.sh camera_source:=0 (từ root package thì đổi đường dẫn).
Lệnh đầy đủ từ workspace:
```bash
bash src/turtlebot4_gesture_control/tools/run.sh camera_source:=0
# Hoặc dùng "$CAMERA_URL" ở trên. Không cần nhấn phím nào để robot chạy.
```
Launch hỗ trợ model_path, show_window, cmd_vel_topic, evidence_dir; mọi tham số khác trong
config/gesture_control.yaml. Sửa YAML rồi khởi động lại; chưa hỗ trợ đổi runtime.
Ví dụ cmd_vel_topic:=/robot1/cmd_vel chỉ sau khi kiểm tra subscriber thật.

## Giao thức và ánh xạ
/detected_gesture: std_msgs/msg/String chứa JSON:
```json
{"v":1,"session":"uuid","seq":12,"stamp":1790000000.0,"frame_age":0.03,"label":"VICTORY","confidence":0.94}
```
Ví dụ minh họa định dạng, không phải bản tin dùng chạy test vật lý.
Nhãn chuẩn: WAVE, POINTING_UP, VICTORY, THUMBS_UP, OPEN_PALM,
CLOSED_FIST, NO_HAND, UNKNOWN, CAMERA_ERROR.
Heartbeat 12 Hz. Schema, tuổi bản tin/ảnh, số thứ tự và phiên được kiểm tra.
Nhận diện và điều khiển cùng WSL; không dùng clock ROS mô phỏng cho watchdog.

| Cử chỉ | Nhãn model | Nhãn publish | Hành vi |
|---|---|---|---|
| Wave | Không có | WAVE | Chọn xoay chào trái-phải, chờ xác nhận |
| Pointing Up | Pointing_Up | POINTING_UP | Chọn 4 chu kỳ tiến rồi lùi |
| Victory | Victory | VICTORY | Chọn tròn |
| Thumbs Up | Thumb_Up | THUMBS_UP | Xác nhận lựa chọn |
| Open Palm | Open_Palm | OPEN_PALM | Dừng ngay, giữ lựa chọn |
| Closed Fist | Closed_Fist | CLOSED_FIST | Hủy và xóa lựa chọn |

Model có None, Closed_Fist, Open_Palm, Pointing_Up, Thumb_Down, Thumb_Up,
Victory, ILoveYou. Không gán Thumb_Down/ILoveYou thành lệnh robot.
Không tay -> NO_HAND; nhãn không hỗ trợ/độ tin cậy thấp -> UNKNOWN.
Hai tay -> không chọn/xác nhận; palm/fist vẫn dừng/hủy.

Wave: tâm 5 landmark lòng bàn tay, di chuyển ngang >=0,12 chiều rộng ảnh,
ít nhất 2 lần đổi hướng, thời gian >=0,45 s trong cửa sổ 1,8 s.
Gián đoạn >0,25 s, đổi tay hoặc dịch dọc >0,18 chiều cao làm reset lịch sử.
Chỉ dùng palm confidence >=0,65. Wave được giữ 0,5 s để debounce.
Palm chưa đủ Wave vẫn xuất OPEN_PALM. Khi EXECUTING, mọi palm xuất OPEN_PALM;
bộ điều khiển còn xử lý WAVE khi đang chạy như stop để loại race trạng thái.
Do đó hãy vẫy khi đang chờ, nhìn SELECTED GREETING rồi đổi sang Thumbs Up.

Debounce chọn/xác nhận: >=3 bản tin và >=0,25 s; cooldown 0,7 s.
Bộ lọc chịu UNKNOWN ngắn tối đa 0,15 s, nhưng vẫn cần đủ mẫu hợp lệ. Sau stop/kết thúc phải nhả Thumbs Up >=0,2 s rồi xác nhận lại; giữ ngón cái
không lặp vô hạn. Giữ OPEN_PALM cũng tính là nhả ngón cái, nhưng robot vẫn đứng yên cho đến xác nhận mới. OPEN_PALM/CLOSED_FIST không qua cửa sổ debounce.
Ngưỡng stop 0,45 thấp hơn ngưỡng chọn/xác nhận 0,65.

## Máy trạng thái, kích thước chuyển động, an toàn
IDLE -> SELECTED -> EXECUTING -> IDLE; STOPPED giữ lựa chọn,
CANCELLED xóa lựa chọn. Stop/mất tín hiệu không tự tiếp tục.
Giữ tay hợp lệ trong khung hình trong toàn bộ hành vi; giữ Thumbs Up được.
Mất tay/UNKNOWN >0,6 s hoặc heartbeat >0,7 s -> zero; camera error -> zero ngay
ở callback. Timer 20 Hz dùng STEADY_TIME; trễ timer >0,3 s -> zero.
SIGINT/SIGTERM và exception phát zero trước đóng DDS. Kill -9/mất máy không thể
gửi zero: controller robot phải giữ cmd_vel_timeout=0,5 s như cấu hình đã khảo sát.
Không cam kết độ trễ thời gian thực cứng trên WSL.

Tiến/lùi v=0,08 m/s, t=1,5 s: 0,12 m mỗi chiều; 4 chu kỳ, tổng đường đi 0,96 m,
lý tưởng trở lại điểm xuất phát. Có một tick zero khi đảo chiều.
Chào w=0,35 rad/s: +0,35, -0,70, +0,35 rad, tổng 4 s.
Tròn R=0,40 m, w=v/R=0,20 rad/s, T=31,42 s; tâm (0,0,4) theo hệ xuất phát,
độ lệch cực đại 0,8 m từ vị trí bắt đầu.
Cộng bán kính robot khoảng 0,18 m và dự phòng 0,3 m: cần vùng trống bán kính >=1,3 m
quanh mỗi điểm bắt đầu; world mới có 6 m mỗi phía.
Đây là chuyển động theo thời gian thực trên máy, không phải điều khiển odometry;
Gazebo chậm có thể làm đường đi ngắn, góc xoay/vòng tròn chưa khép kín.
Không có tránh va chạm, không dùng LaserScan để tuyên bố bảo vệ phía sau.
Không thử dài ở maze bài trước. Quan sát và dừng bằng palm nếu robot lệch ra ngoài.

## Kiểm tra và chẩn đoán
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
ros2 node list
ros2 topic info /cmd_vel -v
ros2 topic info /detected_gesture -v
ros2 topic echo /gesture_control/status
ros2 topic echo /detected_gesture
ros2 topic echo /odom --once
ros2 service call /controller_manager/list_controllers controller_manager_msgs/srv/ListControllers '{}'
```
/cmd_vel phải là geometry_msgs/msg/Twist và có diffdrive_controller subscriber.
Không publish lệnh nếu topic có publisher điều khiển khác.
QoS gesture/cmd/status: RELIABLE VOLATILE KEEP_LAST(1). Không latch lệnh.
Hai controller phải active. Nếu chưa active, xem log spawner và renderer WSL.
Nếu ModuleNotFoundError mediapipe: dùng run.sh để nạp đúng venv.
Nếu model lỗi: chạy download_model.py và kiểm tra SHA256.
Nếu ROS mất topic: source cả ROS/workspace và cùng ROS_DOMAIN_ID/FASTDDS setting.
Nếu E_ACCESSDENIED từ terminal Codex: cần quyền chạy WSL ngoài sandbox,
không xử lý bằng tắt bảo mật Windows.

## Unit test, integration, evidence
```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
PYTHONPATH="$PWD/src/turtlebot4_gesture_control:$PYTHONPATH" \
 .venv-gesture/bin/python -m pytest src/turtlebot4_gesture_control/test -v
colcon test --packages-select turtlebot4_gesture_control --event-handlers console_direct+
colcon test-result --test-result-base build/turtlebot4_gesture_control
```
Xem reports/bai_tap_6_cu_chi_tay/ để biết kết quả thực tế và giới hạn.
Mock/synthetic chỉ xuất hiện trong unit/ROS transport test, không làm bằng chứng
webcam đã nhận đủ sáu cử chỉ. tools/smoke_motion.py thử vận tốc nhỏ, có finally zero
và ghi odometry; chỉ chạy trong world trống sau khi kiểm tra topic.
Không có nút bấm/keyboard chọn hành vi trong luồng demo chính.

## Demo và xuất bản
Đặt cửa sổ TB4 Gesture Control cạnh Gazebo, giữ bàn tay đủ sáng, một tay trong khung.
Windows quay bằng OBS Display Capture, không dùng keyboard lái robot.
Xem kịch bản chi tiết trong báo cáo. Source mới có thể tách thành repo Public:
chỉ đưa package này và báo cáo, không đưa venv/model/token/ảnh cá nhân.
Chưa tạo repo hay link Drive khi chưa có tài khoản/kết nối. Hướng dẫn bước cuối
trong reports/bai_tap_6_cu_chi_tay/PUBLISH.md.

## Nguồn chính thức
- https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer
- https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer/python
- https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html
- https://turtlebot.github.io/turtlebot4-user-manual/

## Quay tự động hai cửa sổ thật (không phát lệnh robot)
Mở Gazebo và TB4 Gesture Control trước, sau đó:
```bash
cd ~/ros2_ws
PYTHONNOUSERSITE=1 .venv-gesture/bin/python \
 src/turtlebot4_gesture_control/tools/record_demo.py --seconds 90 \
 --output reports/bai_tap_6_cu_chi_tay/private/demo_thuc_nghiem.mp4
```
Video ghi màn hình X11 thật cạnh nhau ở 4 fps; kiểm tra bao phủ sáu cử chỉ trước
khi gọi là demo hoàn chỉnh. Không dùng video này làm bằng chứng nếu các cửa sổ
báo lỗi hoặc chưa thấy thực thi. Có thể quay OBS để có fps cao hơn.

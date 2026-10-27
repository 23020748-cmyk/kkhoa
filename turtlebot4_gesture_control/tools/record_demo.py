"""Capture real WSL X11 webcam/Gazebo windows side by side. No robot commands."""
import argparse
import ctypes as C
import re
import subprocess
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--seconds', type=float, default=60)
p.add_argument('--fps', type=float, default=4)
p.add_argument('--output', required=True)
args = p.parse_args()
x = C.CDLL('libX11.so.6')
x.XOpenDisplay.restype = C.c_void_p
x.XOpenDisplay.argtypes = [C.c_char_p]
display = x.XOpenDisplay(None)
if not display:
    raise SystemExit('No X11 display; run this in Ubuntu WSLg')
class XImage(C.Structure):
    _fields_ = [('width',C.c_int),('height',C.c_int),('xoffset',C.c_int),
                ('format',C.c_int),('data',C.c_void_p),('byte_order',C.c_int),
                ('bitmap_unit',C.c_int),('bitmap_bit_order',C.c_int),
                ('bitmap_pad',C.c_int),('depth',C.c_int),('bytes_per_line',C.c_int),
                ('bits_per_pixel',C.c_int),('red_mask',C.c_ulong),
                ('green_mask',C.c_ulong),('blue_mask',C.c_ulong)]
x.XGetImage.restype = C.POINTER(XImage)
x.XGetImage.argtypes = [C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_ulong,C.c_int]
x.XDestroyImage.argtypes = [C.POINTER(XImage)]
x.XCloseDisplay.argtypes = [C.c_void_p]
x.XGetGeometry.argtypes = [C.c_void_p,C.c_ulong]+[C.c_void_p]*7

def find(title):
    tree = subprocess.check_output(['xwininfo','-root','-tree'],text=True)
    lines = [line for line in tree.splitlines() if f'"{title}"' in line]
    if len(lines) != 1:
        raise RuntimeError(f'Need exactly one {title} window, found {len(lines)}')
    line = lines[0]
    window = int(line.split()[0],16)
    width,height = map(int,re.search(r'(\d+)x(\d+)\+',line).groups())
    return window,width,height

def capture(window):
    handle,width,height = window
    root_return=C.c_ulong()
    x_return,y_return=C.c_int(),C.c_int()
    width_return,height_return,border_return,depth_return=[C.c_uint() for _ in range(4)]
    x.XGetGeometry(display,handle,C.byref(root_return),C.byref(x_return),C.byref(y_return),
                   C.byref(width_return),C.byref(height_return),C.byref(border_return),C.byref(depth_return))
    width,height=width_return.value,height_return.value
    im = x.XGetImage(display,handle,0,0,width,height,0xffffffff,2)
    if not im:
        raise RuntimeError('Window capture failed')
    try:
        info = im.contents
        data = C.string_at(info.data,info.bytes_per_line*info.height)
        rgb = Image.frombytes('RGB',(info.width,info.height),data,'raw','BGRX',info.bytes_per_line)
        return cv2.cvtColor(np.array(rgb),cv2.COLOR_RGB2BGR)
    finally:
        x.XDestroyImage(im)

def fit(image):
    h,w = image.shape[:2]
    scale = min(640/w,540/h)
    small = cv2.resize(image,(round(w*scale),round(h*scale)))
    panel = np.zeros((540,640,3),np.uint8)
    sh,sw = small.shape[:2]
    panel[(540-sh)//2:(540-sh)//2+sh,(640-sw)//2:(640-sw)//2+sw] = small
    return panel

camera, gazebo = find('TB4 Gesture Control'), find('Gazebo')
target = Path(args.output)
target.parent.mkdir(parents=True,exist_ok=True)
writer = cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*'mp4v'),args.fps,(1280,620))
if not writer.isOpened():
    raise SystemExit('MP4 writer unavailable')
start = time.monotonic()
frames = 0
try:
    while time.monotonic()-start < args.seconds:
        tick = time.monotonic()
        frame = np.zeros((620,1280,3),np.uint8)
        frame[50:590,:640] = fit(capture(camera))
        frame[50:590,640:] = fit(capture(gazebo))
        cv2.putText(frame,'REAL WEBCAM / MEDIAPIPE', (12,32),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,220,100),2)
        cv2.putText(frame,'REAL GAZEBO / TURTLEBOT 4', (650,32),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,220,100),2)
        cv2.putText(frame,time.strftime('%Y-%m-%d %H:%M:%S')+' | Test recording - verify gesture coverage',
                    (12,612),cv2.FONT_HERSHEY_SIMPLEX,.5,(220,220,220),1)
        writer.write(frame)
        if frames == 0:
            cv2.imwrite(str(target.with_suffix('.jpg')),frame)
        frames += 1
        time.sleep(max(0.,1/args.fps-(time.monotonic()-tick)))
finally:
    writer.release()
    x.XCloseDisplay(display)
print(dict(output=str(target),frames=frames,actual_seconds=time.monotonic()-start,
           encoded_seconds=frames/args.fps))

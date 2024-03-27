from time import time
from os import path
import json
import cv2

SCRIPT_DIR = path.abspath(path.join(path.dirname(__file__)))
VIDEO_DIR = path.join(SCRIPT_DIR, 'video')
VIDEO_PATH = path.join(VIDEO_DIR, 'sample-3s.mp4')
OUTPUT_PATH = path.join('/run', 'sample-gray.mp4')

def handle(event, context):
    try:
        req = json.loads(event.body.decode())
    except Exception as _:
        video_id = 0
    else:
        video_id = req.get('video_id', 0)
    start = time()
    if video_id == 0:
        VIDEO_PATH = path.join(VIDEO_DIR, 'sample-3s.mp4')
    else:
        VIDEO_PATH = path.join(VIDEO_DIR, 'sample-6s.mp4')
    video = cv2.VideoCapture(VIDEO_PATH)

    width = int(video.get(3))
    height = int(video.get(4))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, 20.0, (width, height))

    while video.isOpened():
        ret, frame = video.read()

        if ret:
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            tmp_file_path = path.join('/run', 'tmp.jpg')
            cv2.imwrite(tmp_file_path, gray_frame)
            gray_frame = cv2.imread(tmp_file_path)
            out.write(gray_frame)
        else:
            break

    video.release()
    out.release()

    latency = time() - start
    return {
        "statusCode": 200,
        "body": {'latency': latency, 'data': OUTPUT_PATH},
    }


from os import path
from time import time
from PIL import Image
import json

from .ops import *

SCRIPT_DIR = path.abspath(path.join(path.dirname(__file__)))
IMAGE_DIR = path.join(SCRIPT_DIR, 'images')
IMAGE_PATH = path.join(IMAGE_DIR, 'image.jpg')
IMAGE_NAME = 'image.jpg'

def handle(event, context):
    start = time()
    path_list = []
    with Image.open(IMAGE_PATH) as image:
        path_list += flip(image, IMAGE_NAME)
        path_list += rotate(image, IMAGE_NAME)
        path_list += filter(image, IMAGE_NAME)
        path_list += gray_scale(image, IMAGE_NAME)
        path_list += resize(image, IMAGE_NAME)

    latency = time() - start
    return {
        "statusCode": 200,
        "body": {
            'latency': latency,
            'data': path_list
        }
    }

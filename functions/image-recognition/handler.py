import json
from time import time
from os import path

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

from PIL import Image
import torch
from torchvision import transforms
from torchvision.models import resnet50

SCRIPT_DIR = path.abspath(path.join(path.dirname(__file__)))
IMAGE_PATH = path.join(SCRIPT_DIR, 'images', '800px-Welsh_Springer_Spaniel.jpg')
MODEL_PATH = path.join(SCRIPT_DIR, 'model', 'resnet50-19c8e357.pth')
CLASS_IDX_PATH = path.join(SCRIPT_DIR, 'imagenet_class_index.json')
class_idx = None
idx2label = None
model = None

def handle(event):
    global model
    global class_idx
    global idx2label
    model_process_begin = time()
    if model is None:
        model = resnet50(weights=None)
        model.load_state_dict(torch.load(MODEL_PATH))
        model.eval()
    if class_idx is None:
        class_idx = json.load(open(CLASS_IDX_PATH, 'r'))
        idx2label = [class_idx[str(k)][1] for k in range(len(class_idx))]
    model_process_end = time()
   
    process_begin = time()
    input_image = Image.open(IMAGE_PATH)
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    input_tensor = preprocess(input_image)
    input_batch = input_tensor.unsqueeze(0) # create a mini-batch as expected by the model 
    output = model(input_batch)
    _, index = torch.max(output, 1)
    # The output has unnormalized scores. To get probabilities, you can run a softmax on it.
    prob = torch.nn.functional.softmax(output[0], dim=0)
    _, indices = torch.sort(output, descending=True)
    ret = idx2label[index]
    process_end = time()

    model_process_time = (model_process_end - model_process_begin)
    process_time = (process_end - process_begin)
    return json.dumps({
            'latency': process_time + model_process_time,
            'latencies': {
                'process_time': process_time,
                'model_process_time': model_process_time
            },
            'data': {'idx': index.item(), 'class': ret}
        })


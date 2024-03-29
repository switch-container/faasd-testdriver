from os import path
from time import time
import json

SCRIPT_DIR = path.abspath(path.join(path.dirname(__file__)))
FILES_DIR = path.join(SCRIPT_DIR, 'files')
DEFAULT_NAME = '1'
AVAILABLE_NAMES = ['1', '2', '3', '4', '5']
# sample json input:
# { 'name': '1'}
# available name: '1', '2' and 'search'

def handle(event, context):
    start = time()
    try:
        req = json.loads(event.body.decode())
    except Exception as _:
        name = '1'
    else:
        name = req.get('name', '1')
    if name not in AVAILABLE_NAMES:
        name = '1'
    file_path = path.join(FILES_DIR, f'{name}.json')
    f = open(file_path, 'r')
    j = json.load(f)
    str_j = json.dumps(j, indent=4)


    return {
        "statusCode": 200,
        "body": {
            'latency': time() - start,
            'data': file_path
        }
    }

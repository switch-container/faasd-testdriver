from datetime import datetime
import json
from random import sample
from os import path
from time import time

from jinja2 import Template

# {
#     "username": "Tsinghua University",
#     "random_len": 1000
# }

SCRIPT_DIR = path.abspath(path.join(path.dirname(__file__)))

def handle(event, context):
    req = json.loads(event.body.decode())
    name = req.get('username')
    size = req.get('random_len')

    start = time()
    cur_time = datetime.now()
    random_numbers = sample(range(0, 1000000), size)
    template = Template(open(path.join(SCRIPT_DIR, 'templates', 'template.html'), 'r').read())
    html = template.render(username = name, cur_time = cur_time, random_numbers = random_numbers)

    latency = time() - start
    return {
        "statusCode": 200,
        "body":{'latency': latency, 'data': html} 
    }

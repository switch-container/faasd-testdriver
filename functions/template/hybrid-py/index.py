#!/usr/bin/env python

# first activate virtual python environment
import sys, os, traceback
VIRTUALENV_PATH = "./faas"

try:
  # if the directory 'virtualenv' is extracted out of a zip file
  path_to_virtualenv = os.path.abspath(VIRTUALENV_PATH)
  if os.path.isdir(path_to_virtualenv):
    # activate the virtualenv using activate_this.py contained in the virtualenv
    activate_this_file = path_to_virtualenv + '/bin/activate_this.py'
    if os.path.exists(activate_this_file):
      with open(activate_this_file) as f:
        code = compile(f.read(), activate_this_file, 'exec')
        exec(code, dict(__file__=activate_this_file))
    else:
      sys.stderr.write("Invalid virtualenv. There does not include 'activate_this.py'.\n")
      sys.exit(1)
except Exception:
  traceback.print_exc(file=sys.stderr, limit=0)
  sys.exit(1)


from flask import Flask, request, jsonify
from waitress import serve
import os

from function import handler

import psutil
import multiprocessing
import time
import gc

app = Flask(__name__)

class Event:
    def __init__(self):
        self.body = request.get_data()
        self.headers = request.headers
        self.method = request.method
        self.query = request.args
        self.path = request.path

class Context:
    def __init__(self):
        self.hostname = os.getenv('HOSTNAME', 'localhost')

def format_status_code(res):
    if 'statusCode' in res:
        return res['statusCode']
    
    return 200

def format_body(res, content_type):
    if content_type == 'application/octet-stream':
        return res['body']

    if 'body' not in res:
        return ""
    elif type(res['body']) == dict:
        return jsonify(res['body'])
    else:
        return str(res['body'])

def format_headers(res):
    if 'headers' not in res:
        return []
    elif type(res['headers']) == dict:
        headers = []
        for key in res['headers'].keys():
            header_tuple = (key, res['headers'][key])
            headers.append(header_tuple)
        return headers
    
    return res['headers']

def get_content_type(res):
    content_type = ""
    if 'headers' in res:
        content_type = res['headers'].get('Content-type', '')
    return content_type

def format_response(res):
    if res == None:
        return ('', 200)

    statusCode = format_status_code(res)
    content_type = get_content_type(res)
    body = format_body(res, content_type)

    headers = format_headers(res)

    return (body, statusCode, headers)

def monitor_memory(pid, sum, count, interval = 0.01):
    while True:
        process = psutil.Process(pid)
        memory_usage = process.memory_info().rss / (1024 * 1024)  # Convert to MB
        sum.value += memory_usage
        count.value += 1
        time.sleep(interval)

@app.route('/', defaults={'path': ''}, methods=['GET', 'PUT', 'POST', 'PATCH', 'DELETE'])
@app.route('/<path:path>', methods=['GET', 'PUT', 'POST', 'PATCH', 'DELETE'])
def call_handler(path):
    event = Event()
    context = Context()

    # Start memory monitor
    current_pid = psutil.Process().pid
    sum = multiprocessing.Value('d', 0.0)
    count = multiprocessing.Value('i', 0)
    monitor_process = multiprocessing.Process(target=monitor_memory, args=(current_pid, sum, count))
    monitor_process.start()

    # Call handler
    response_data = handler.handle(event, context)

    # Stop memory monitor
    monitor_process.terminate()
    response_data['body']['memory_usage'] = sum.value / count.value
    
    res = format_response(response_data)
    return res

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)

import sys
import json

arr = []

def handle(event, context):
    if event.method != 'POST':
        return {
            "statusCode": 405,
            "body": "Method not allowed"
        }
    req = json.loads(event.body.decode())
    size = req.get('size')
    main(size)
    return {
        "statusCode": 200,
        "body": f"alloc arr of {size} bytes successfully"
    }

def convert_size_to_length(size):
    base = sys.getsizeof([])
    return (size - base) // 8

def main(size):
    global arr
    length = convert_size_to_length(size)
    arr = [2022310806] * length

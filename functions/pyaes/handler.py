from time import time
import random
import string
import pyaes
import json

# {
#     "length_of_message": 1000,
#     "num_of_iterations": 100
# }


def generate(length):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))


def handle(event, context):
    start = time()
    req = json.loads(event.body.decode())
    length_of_message = req['length_of_message']
    num_of_iterations = req['num_of_iterations']

    message = generate(length_of_message)

    # 128-bit key (16 bytes)
    KEY = b'\xa1\xf6%\x8c\x87}_\xcd\x89dHE8\xbf\xc9,'

    for loops in range(num_of_iterations):
        aes = pyaes.AESModeOfOperationCTR(KEY)
        ciphertext = aes.encrypt(message)

        aes = pyaes.AESModeOfOperationCTR(KEY)
        plaintext = aes.decrypt(ciphertext)
        aes = None

    latency = time() - start

    return {
        "statusCode": 200,
        "body": {
            'latency': latency,
            'data': ''
        }
    }

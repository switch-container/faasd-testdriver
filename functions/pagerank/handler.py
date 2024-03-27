from time import time
import json
import igraph

DEFAULT_SIZE = 50000
DEFAULT_EDGE_PER_VERT = 10
# sample json input:
# { 'size': 60000, 'out': 15 }

def handle(event, context):
    start = time()
    try:
        req = json.loads(event.body.decode())
    except Exception as _:
        size = 50000
        m = DEFAULT_EDGE_PER_VERT
    else:
        size = req.get('size', DEFAULT_SIZE)
        m = req.get('out', DEFAULT_EDGE_PER_VERT)

    graph = igraph.Graph.Barabasi(size, m)
    result = graph.pagerank()

    return {
        "statusCode": 200,
        "body": {
            'latency': time() - start,
            'data': {'size': size, 'out': m}
        }
    }

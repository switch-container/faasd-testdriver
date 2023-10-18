from time import time
import json
import igraph


def handle(event, context):
    size = json.loads(event.body.decode()).get("size")

    start = time()
    graph = igraph.Graph.Barabasi(size, 10)
    result = graph.pagerank()
    latency = time() - start

    return {"statusCode": 200, "body": {"latency": latency, "data": result[0]}}

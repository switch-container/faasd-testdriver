import random
import argparse
import yaml
import json
from typing import List

random.seed(2022310806)
PEEK_CONCURRENCY = 40
PEEK_PERIOD = 15  # seconds
CYCLE_PERIOD = 120  # seconds
TOTAL_TIME = 240  # seconds


def workload_1(conf: List[str], T: int, cycle_num: int):
    """
    :param cache_time: cache time of container in seconds
    :param T: the period of the cycle for burst request (a little longer than cache time)
    :param cycle_num: the number of cycles to generate
    """
    res = {}
    for func in conf:
        # run multiple instance in 10s
        arrival_invokes = []
        peak_start = PEEK_PERIOD * random.randint(0, (T // PEEK_PERIOD) - 1)
        print(f"{func} peak start is at {peak_start}")
        for _ in range(cycle_num):
            left = PEEK_CONCURRENCY
            for t in range(T):
                num = 0
                if t >= peak_start:
                    num = abs(random.normalvariate(PEEK_CONCURRENCY // PEEK_PERIOD, 5))
                    num = min(int(num), left)
                arrival_invokes.append(num)
                left -= num
        res[func] = arrival_invokes
        print(f"length of arrival_invokes {len(arrival_invokes)}")
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="config file path (default: config.yml)", default="config.yml")
    args = parser.parse_args()

    config = None
    with open(args.config, "r") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    if config is None:
        raise Exception(f"Error: Config {args.config} is invalid")

    functions = config.get("functions", None)
    res = workload_1(list(functions.keys()), CYCLE_PERIOD, TOTAL_TIME // CYCLE_PERIOD)
    with open("workload_1.json", "w") as f:
        json.dump(res, f, indent=2)

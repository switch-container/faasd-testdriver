import random
import argparse
import yaml
import json
import math

random.seed(2022310806)


def workload_1(config: dict):
    """
    :param config: parsed dict from config.yml
    """

    # each funtion will busrt in one peek_period in one cycle_period
    # so for workload 1: the cycle_period should > faasd containerd cache duration
    functions = config["functions"]
    cycle_period = config.get("cycle_period", 90)
    cycle_num = config.get("cycle_num", 6)
    func_period = cycle_period // len(functions)

    peak_start_array = list(range(len(functions)))
    random.shuffle(peak_start_array)

    res = {}
    for func_name in functions:
        # run multiple instance in 10s
        arrival_invokes = []
        func = functions[func_name]
        peek_concurrency = func.get("max_concurrency", 40)
        exec_time_hint = func["exec_time_hint"]
        # we should burst request in exec_time_hint to prevent reuse
        peak_start = peak_start_array.pop(0) * func_period
        print(f"{func_name} peak start is at {peak_start} peek concurrency is {peek_concurrency}")
        for _ in range(cycle_num):
            for t in range(cycle_period):
                num = 0
                peak_period = min(func_period, exec_time_hint)
                if t >= peak_start and t <= math.ceil(peak_start + peak_period):
                    std = (peek_concurrency // peak_period) * 0.05
                    std = max(math.ceil(std), 1)

                    num = abs(random.normalvariate(peek_concurrency // peak_period, std))
                    num = min(int(num), 300)
                arrival_invokes.append(num)
        assert len(arrival_invokes) == cycle_period * cycle_num
        res[func_name] = arrival_invokes
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

    res = workload_1(config)
    with open("workload_1.json", "w") as f:
        json.dump(res, f, indent=2)

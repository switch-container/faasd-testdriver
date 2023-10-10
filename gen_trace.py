import random
import argparse
import yaml
import json

random.seed(2022310806)


def workload_1(config: dict):
    """
    :param config: parsed dict from config.yml
    """

    # each funtion will busrt in one peek_period in one cycle_period
    # so for workload 1: the cycle_period should > faasd containerd cache duration
    functions = config["functions"]
    peek_period = config.get("peek_period", 15)
    cycle_period = config.get("cycle_period", 90)
    cycle_num = config.get("cycle_num", 6)

    peak_start_array = list(range(cycle_period // peek_period))
    random.shuffle(peak_start_array)

    res = {}
    for func_name in functions:
        # run multiple instance in 10s
        arrival_invokes = []
        func = functions[func_name]
        peek_concurrency = func.get("max_concurrency", 40)
        peak_start = peak_start_array.pop(0) * peek_period
        print(f"{func_name} peak start is at {peak_start} peek concurrency is {peek_concurrency}")
        for _ in range(cycle_num):
            left = peek_concurrency
            for t in range(cycle_period):
                num = 0
                if t >= peak_start:
                    num = abs(random.normalvariate(peek_concurrency // peek_period, 5))
                    num = min(int(num), left)
                arrival_invokes.append(num)
                left -= num
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

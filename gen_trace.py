import random
import argparse
import yaml
import json
import math
import matplotlib.pyplot as plt

random.seed(2022310806)


def workload_1(config: dict):
    """
    :param config: parsed dict from config.yml
    """
    print(f"start generating workload 1 ...")

    # each funtion will busrt in one peek_period in one cycle_period
    # so for workload 1: the cycle_period should > faasd containerd cache duration
    functions = config["functions"]
    cycle_period = config.get("cycle_period", 90)
    cycle_num = config.get("cycle_num", 6)
    func_period = cycle_period // len(functions)
    print(f"cycle_period {cycle_period} func_period {func_period} cycle_num {cycle_num}")

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
                if t >= peak_start and t < math.ceil(peak_start + peak_period):
                    std = (peek_concurrency // peak_period) * 0.05
                    std = max(math.ceil(std), 1)

                    num = abs(random.normalvariate(peek_concurrency // peak_period, std))
                    num = min(int(num), 300)
                arrival_invokes.append(num)
        assert len(arrival_invokes) == cycle_period * cycle_num
        res[func_name] = arrival_invokes
    return res


def workload_2(config: dict):
    print(f"start generating workload 2 ...")
    # we will send burst workload within the gc criterion
    # but due the limitation of memory, we may meet cold start
    functions = config["functions"]
    gc_criterion = config["faasd_gc_criterion"]
    cycle_num = config.get("cycle_num", 6)
    interval = int(gc_criterion * 0.8)
    func_period = interval // len(functions)

    print(f"gc criterion {gc_criterion} interval {interval} func_period {func_period} cycle_num {cycle_num}")

    res = {}
    start = 0
    for func_name in functions:
        arrival_invokes = []
        concurrency = functions[func_name]["max_concurrency"]
        dur = functions[func_name]["duration"]
        print(f"{func_name} start is at {start} concurrency is {concurrency} duration {dur}")
        for _ in range(cycle_num):
            for t in range(interval):
                if t >= start and t < start + dur:
                    arrival_invokes.append(concurrency)
                else:
                    arrival_invokes.append(0)
        assert len(arrival_invokes) == interval * cycle_num
        res[func_name] = arrival_invokes
        start += func_period
    return res


def draw_workload(res: dict):
    size = 120
    fig, ax = plt.subplots()
    for func_name, arrival_invokes in res.items():
        times = list(range(size))
        ax.plot(times, arrival_invokes[:size], label=func_name)
    ax.legend()
    fig.savefig("workload.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--workload", type=str, choices=["1", "2"], required=True, help="the workload to generate")
    args = parser.parse_args()

    config = None
    with open(f"workload{args.workload}.yml", "r") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    if config is None:
        raise Exception(f"Error: Config {args.config} is invalid")

    if args.workload == "1":
        res = workload_1(config)
    elif args.workload == "2":
        res = workload_2(config)
    else:
        raise Exception(f"unknown workload args {args.workload}")

    with open(f"workload.json", "w") as f:
        json.dump(res, f, indent=2)

    draw_workload(res)

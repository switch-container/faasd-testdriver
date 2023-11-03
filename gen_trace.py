from os import path
import random
import argparse
import yaml
import json
import math
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

random.seed(2022310806)
np.random.seed(2022310806)

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
    warmup_cycle = config.get("warmup_cycle", 2)
    assert warmup_cycle <= cycle_num
    print(f"cycle_period {cycle_period} func_period {func_period} cycle_num {cycle_num} warmup cycle {warmup_cycle}")

    peak_start_array = list(range(len(functions)))
    random.shuffle(peak_start_array)

    res = {}  # this is real workload that we need test
    warmup = {}  # this is the warmup worload
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
        warmup[func_name] = arrival_invokes[: cycle_period * warmup_cycle]
    return res, warmup


def workload_2(config: dict):
    print(f"start generating workload 2 ...")
    # we will send burst workload within the gc criterion
    # but due the limitation of memory, we may meet cold start
    functions = config["functions"]
    gc_criterion = config["faasd_gc_criterion"]
    cycle_num = config.get("cycle_num", 6)
    warmup_cycle = config.get("warmup_cycle", 2)
    assert warmup_cycle <= cycle_num

    T = 0
    for func_name in functions:
        T += functions[func_name]["last"]

    print(f"gc criterion {gc_criterion} one cycle dur {T} cycle_num {cycle_num} warmup_cycle {warmup_cycle}")

    res = {}
    warmup = {}
    start = 0
    for func_name in functions:
        arrival_invokes = []
        concurrency = functions[func_name]["max_concurrency"]
        dur = functions[func_name]["duration"]
        print(f"{func_name} start is at {start} concurrency is {concurrency} duration {dur}")
        for _ in range(cycle_num):
            for t in range(T):
                if t >= start and t < start + dur:
                    arrival_invokes.append(concurrency)
                else:
                    arrival_invokes.append(0)
        assert len(arrival_invokes) == T * cycle_num
        res[func_name] = arrival_invokes
        start += functions[func_name]["last"]
        warmup[func_name] = arrival_invokes[: T * warmup_cycle]
    return res, warmup


class AzureTraceConfig:
    def __init__(self, hash: dict, dir: str):
        self.idx = hash
        inv_filepath = path.join(dir, "invocations_per_function_md.anon.d03.csv")
        dur_filepath = path.join(dir, "function_durations_percentiles.anon.d03.csv")
        mem_filepath = path.join(dir, "function_durations_percentiles.anon.d03.csv")
        inv_df = pd.read_csv(inv_filepath)
        dur_df = pd.read_csv(dur_filepath)
        mem_df = pd.read_csv(mem_filepath)
        df = pd.merge(inv_df, dur_df, on=["HashOwner", "HashApp", "HashFunction"])
        df = pd.merge(df, mem_df, on=["HashOwner", "HashApp", "HashFunction"])
        inv_cols = [str(x) for x in range(1, 1441)]
        df["totals"] = df[inv_cols].sum(axis=1)
        df["max"] = df[inv_cols].max(axis=1)
        df["min"] = df[inv_cols].min(axis=1)
        df["avg"] = df[inv_cols].mean(axis=1)
        self.df = df

    def get_func_data(self):
        data = {}
        for func_name, row_id in self.idx.items():
            row = self.df.iloc[row_id]
            data[func_name] = row
            print(
                f"{func_name} per minute max: {row['max']} min: {row['min']} avg: {row['avg']:.3f} avg_dur: {row['Average_x']} ms"
            )
        return data


def skew_split_one_min_load(number: int):
    # Generate more samples than needed from a Poisson distribution with a very small lambda
    samples = np.random.poisson(0.1, 600)
    # Take the first 60 samples
    bins = samples[:60]
    # If the sum is 0 (unlikely, but just to be safe), set one bin to total_number
    if bins.sum() == 0:
        bins[np.random.randint(0, 60)] = number
    # Otherwise, normalize the samples to the total number
    else:
        scale_factor = number / bins.sum()
        bins = np.floor(bins * scale_factor).astype(int)
        # If rounding leaves us with a shortfall, add the remainder randomly
        while bins.sum() < number:
            bins[np.random.randint(0, len(bins))] += 1
    return bins.tolist()

def evenally_split_one_min_load(number: int):
    # Generate 59 random numbers between 1 and total_number - 1
    random_points = [random.randint(0, number) for _ in range(59)]
    # Sort the random points and add 0 at the beginning and total_number at the end
    edges = [0] + sorted(random_points) + [number]
    # Calculate the differences between consecutive numbers to get the bin sizes
    bins = [edges[i+1] - edges[i] for i in range(60)]
    # Now bins contains 60 integer numbers which sum up to total_number
    return bins


def azure_workload(index: dict, dir: str):
    warmup_sec = 5 * 60
    total_sec = 60 * 60  # 1 hours
    config = AzureTraceConfig(index, dir)
    data = config.get_func_data()
    invokes = {}
    warmup = {}
    for func_name in data:
        arrival_invokes = []
        row = data[func_name]
        for m in range(1, 1441):
            left_invokes_per_min = int(row[str(m)])
            # special cases for 0 requests
            if left_invokes_per_min == 0:
                arrival_invokes += [0] * 60
                continue
            # 20 % generate some skew load
            if random.random() < 0.8:
                one_min_load = evenally_split_one_min_load(left_invokes_per_min)
            else:
                one_min_load = skew_split_one_min_load(left_invokes_per_min)
            # do not use too skew workload
            if not func_name.startswith('dynamic-html') and max(one_min_load) >= 40:
                one_min_load = evenally_split_one_min_load(left_invokes_per_min)
            assert(sum(one_min_load) == left_invokes_per_min and len(one_min_load) == 60)
            arrival_invokes += one_min_load
        assert len(arrival_invokes) == 1440 * 60
        warmup[func_name] = arrival_invokes[:warmup_sec]
        invokes[func_name] = arrival_invokes[warmup_sec:total_sec]
    return invokes, warmup


def ali_scalr_workload(index: dict, dir: str):
    warmup_sec = 5 * 60
    trace = {}
    min_start_time = 1 << 62
    max_start_time = 0
    with open(path.join(dir, "requests"), "r") as f:
        for line in f.readlines():
            item = json.loads(line)
            meta_key = item["metaKey"]
            if meta_key not in trace:
                trace[meta_key] = []
            trace[meta_key].append(item["startTime"] / 1000.0)

            max_start_time = max(max_start_time, item["startTime"] / 1000.0)
            min_start_time = min(min_start_time, item["startTime"] / 1000.0)
    # now select from trace
    total = math.ceil(max_start_time - min_start_time)
    invokes = {}
    warmup = {}
    print(f"total {total} seconds")
    for func_name, meta_key in index.items():
        start_times = [math.floor(t - min_start_time) for t in trace[meta_key]]
        arrival_invokes = [0] * total
        for t in start_times:
            arrival_invokes[t] += 1
        warmup[func_name] = arrival_invokes[:warmup_sec]
        invokes[func_name] = arrival_invokes[warmup_sec:]

        groups = [arrival_invokes[i : i + 60] for i in range(0, len(arrival_invokes), 60)]
        sums = [sum(group) for group in groups]
        largest_sum = max(sums)
        smallest_sum = min(sums)
        average_sum = sum(sums) / len(sums)
        print(f"{func_name} per minute max: {largest_sum} min: {smallest_sum} avg: {average_sum:.3f}")
    return invokes, warmup


def draw_workload(res: dict):
    fig, ax = plt.subplots()
    for func_name, arrival_invokes in res.items():
        ax.plot(list(range(len(arrival_invokes))), arrival_invokes, label=func_name)
    ax.legend()
    fig.savefig("workload.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-w", "--workload", type=str, choices=["1", "2", "azure", "ali"], required=True, help="the workload to generate"
    )
    # /root/downloads/azurefunction-dataset2019
    parser.add_argument(
        "--dataset", type=str, help="if you want to generate trace of azure or alibaba, please specify dataset path"
    )
    args = parser.parse_args()

    if args.workload == "1":
        with open(f"workload{args.workload}.yml", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
        res, warmup = workload_1(config)
    elif args.workload == "2":
        with open(f"workload{args.workload}.yml", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
        res, warmup = workload_2(config)
    elif args.workload == "azure":
        if args.dataset is None or len(args.dataset) == 0:
            parser.error("-w/--workload azure requires --dataset")
        index = {
            "dynamic-html": 2551,
            "image-flip-rotate": 27884,
            "video-processing": 3666,
            "chameleon": 4067,
            "pyaes": 846,
            "image-processing": 1554,
            "image-recognition": 30486,
            "crypto": 839,
            "image-flip-rotate_1": 46374,
            "video-processing_1": 654,
            "chameleon_1": 4812,
            "pyaes_1": 1059,
            "image-processing_1": 3568,
            "image-recognition_1": 9298,
            "crypto_1": 45306,
            "image-flip-rotate_2": 46376,
            "video-processing_2": 1086,
            "chameleon_2": 1164,
            "pyaes_2": 4263,
            "image-processing_2": 2376,
            "image-recognition_2": 9416,
            "crypto_2": 42794,
        }
        res, warmup = azure_workload(index, args.dataset)
    elif args.workload == "ali":
        if args.dataset is None or len(args.dataset) == 0:
            parser.error("-w/--workload ali requires --dataset")
        index = {
            "dynamic-html": "a5d16f04c764b7bd3c5bb36d2ae74e96bf7d126c",
            "image-flip-rotate": "c5e35a591b9915b413944fa520c63c7d62433d6a",
            "video-processing": "f2ce5b954bb55d1c30b47dc12c66cc565961fcd7",
            "chameleon": "9543b9e40874abe031f13f750b0be62131e8bd88",
            "pyaes": "0181aff53a1108a9365bf812f9707a46a76a93ba",
            "image-processing": "dfd9a820c6f3dcaffea1649adc248d7a95bb01ed",
            "image-recognition": "0dd9b0ae5c58a00ac5bcc9b77100381444a854ad",
            "crypto": "030707aacf589606b1160912bdf4396b2d252915",
            "image-flip-rotate_1": "f43c6f855fce936da9177b65dfc67ef579edf77e",
            "video-processing_1": "9a89d9b5b379a958255fd34e5ee770ace2cdafb2",
            "chameleon_1": "8ab8fd7f7cfe58aafbee740940425f6ac88487dd",
            "pyaes_1": "da10c07532a06efb9a6a89baae980c6f1782503b",
            "image-processing_1": "a0b745bfcecce6c5dfa80d8e5302cc2e1ffbf9af",
            "image-recognition_1": "105e1e0e0208ddaaabc59ed6e08aeef437cb1d1a",
            "crypto_1": "0181aff53a1108a9365bf812f9707a46a76a93ba",
            "image-flip-rotate_2": "35abc2d27b129b752c68e6e45c266194575eebc2",
            "video-processing_2": "2e8773e5d82ab7e1da7f937e2e4f472c36e0bca8",
            "chameleon_2": "aba6f081b7f2564d501d250225e2dcd207095fe9",
            "pyaes_2": "5b6d00d467537593c02dfe735e15c182056c572a",
            "image-processing_2": "9c1222b7b54433655b7c623555490f47042cafdc",
            "image-recognition_2": "bd3456a228222fd75ce1c74098fe7bd3fd1ce59c",
            "crypto_2": "5b6d00d467537593c02dfe735e15c182056c572a",
        }
        res, warmup = ali_scalr_workload(index, args.dataset)
    else:
        raise Exception(f"unknown workload args {args.workload}")

    with open(f"workload.json", "w") as f:
        json.dump(res, f, indent=2)

    with open(f"warmup.json", "w") as f:
        json.dump(warmup, f, indent=2)

    draw_workload(res)

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


def functional_workload(config: dict, iter_nr: int):
    functions = config["functions"]
    T = 0
    for func_name in functions:
        last = functions[func_name]["last"]
        T += last
    print(f"start generating func workload {iter_nr} iter, T = {T}")
    warmup = {}  # functional_test warmup only have single round
    res = {}
    start_time = 0
    for func_name in functions:
        print(f"{func_name} start at {start_time} in each cycle, last for {functions[func_name]['last']}")
        arrival_invokes = []
        for _ in range(iter_nr):
            for t in range(T):
                if t == start_time:
                    arrival_invokes.append(1)
                else:
                    arrival_invokes.append(0)
        warmup[func_name] = arrival_invokes[:T]
        res[func_name] = arrival_invokes
        start_time += functions[func_name]["last"]
    for invokes in res.values():
        assert len(invokes) == T * iter_nr
    return res, warmup


def workload_1(config: dict):
    """
    :param config: parsed dict from config.yml
    """
    print(f"start generating workload 1 ...")

    # each funtion will busrt in one peek_period in one cycle_period
    # so for workload 1: the cycle_period should > faasd containerd cache duration
    functions = config["functions"]
    cycle_num = config.get("cycle_num", 6)
    warmup_cycle = config.get("warmup_cycle", 2)
    assert warmup_cycle <= cycle_num

    T = sum([functions[func_name]["last"] for func_name in functions])

    print(f"one cycle period {T} cycle_num {cycle_num} warmup cycle {warmup_cycle}")

    peak_start_array = list(range(len(functions)))
    random.shuffle(peak_start_array)

    res = {}  # this is real workload that we need test
    warmup = {}  # this is the warmup worload
    start = 0
    for func_name in functions:
        # run multiple instance in 10s
        arrival_invokes = []
        func = functions[func_name]
        concurrency = func["max_concurrency"]
        # we should burst request in exec_time_hint to prevent reuse
        peak_times = func["peak_times"]
        peak_interval = func.get("interval", 0)
        peak_period = peak_interval * (peak_times - 1) + peak_times
        upper = 0
        for _ in range(cycle_num):
            for t in range(T):
                num = 0
                if t >= start and t < start + peak_period and ((t - start) % (peak_interval + 1) == 0):
                    std = concurrency * 0.1
                    std = max(math.ceil(std), 1)
                    num = abs(random.normalvariate(concurrency, std))
                    num = int(min(num, concurrency * 1.1))
                    upper = max(upper, num)
                arrival_invokes.append(num)
        print(
            f"{func_name} peak start at {start} peek concurrency is {upper} "
            f"period is {peak_period} interval is {peak_interval}"
        )
        assert len(arrival_invokes) == T * cycle_num
        warmup[func_name] = arrival_invokes[: T * warmup_cycle]
        res[func_name] = arrival_invokes[T * warmup_cycle:]
        start += func["last"]
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
        peak_times = functions[func_name]["peak_times"]
        peak_interval = functions[func_name].get("interval", 0)
        print(f"{func_name} start is at {start} concurrency is {concurrency} peak_times {peak_times} interval {peak_interval}")
        peak_period = peak_interval * (peak_times - 1) + peak_times
        for _ in range(cycle_num):
            for t in range(T):
                if t >= start and t < start + peak_period and ((t - start) % (peak_interval + 1) == 0):
                    arrival_invokes.append(concurrency)
                else:
                    arrival_invokes.append(0)
        assert len(arrival_invokes) == T * cycle_num
        warmup[func_name] = arrival_invokes[: T * warmup_cycle]
        res[func_name] = arrival_invokes[T * warmup_cycle:]
        start += functions[func_name]["last"]
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
            # print(
            #     f"{func_name} per minute max: {row['max']} min: {row['min']} avg: {row['avg']:.3f} avg_dur: {row['Average_x']} ms"
            # )
        return data


def skew_split_one_min_load(number: int, skew=0.1):
    # Generate more samples than needed from a Poisson distribution with a very small lambda
    samples = np.random.poisson(skew, 600)
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

def add_upper_bound_constraint(bins: list, upper_bound: int):
    for idx in range(len(bins)):
        while bins[idx] > upper_bound:
            lowest_idx = bins.index(min(bins))
            bins[idx] -= 1
            bins[lowest_idx] += 1
    return bins


def evenally_split_one_min_load(number: int):
    # Generate 59 random numbers between 1 and total_number - 1
    random_points = [random.randint(0, number) for _ in range(59)]
    # Sort the random points and add 0 at the beginning and total_number at the end
    edges = [0] + sorted(random_points) + [number]
    # Calculate the differences between consecutive numbers to get the bin sizes
    bins = [edges[i + 1] - edges[i] for i in range(60)]
    # Now bins contains 60 integer numbers which sum up to total_number
    return bins


def azure_workload(index: dict, dir: str):
    warmup_sec = 5 * 60
    total_sec = 60 * 60  # 1 hours
    config = AzureTraceConfig(index, dir)
    data = config.get_func_data()
    invokes = {}
    warmup = {}
    upper_bound = {
        "chameleon": 17,
        "image-processing": 12,
        "image-flip-rotate": 15,
        "pyaes": 18,
        "crypto": 20,
        "image-recognition": 7,
        "video-processing": 10,
        "dynamic-html": 80,
        "pagerank": 18,
        "json-serde": 25,
        "js-json-serde": 25,
    }
    for func_name in data:
        arrival_invokes = []
        row = data[func_name]
        skew_prob = 0.4 if '_' not in func_name else 0.2
        for m in range(1, 61):
            left_invokes_per_min = int(row[str(m)])
            # special cases for 0 requests
            if left_invokes_per_min == 0:
                arrival_invokes += [0] * 60
                continue
            # 40 % generate some skew load
            if random.random() < (1 - skew_prob) and "dynamic-html" not in func_name:
                one_min_load = evenally_split_one_min_load(left_invokes_per_min)
            else:
                one_min_load = skew_split_one_min_load(left_invokes_per_min)
                service_name = func_name.rsplit('_', 1)[0]
                one_min_load = add_upper_bound_constraint(one_min_load, upper_bound[service_name])
            # do not use too skew workload
            for name, upper in upper_bound.items():
                if func_name.startswith(name) and max(one_min_load) > upper:
                    one_min_load = evenally_split_one_min_load(left_invokes_per_min)
            assert sum(one_min_load) == left_invokes_per_min and len(one_min_load) == 60
            arrival_invokes += one_min_load
        assert len(arrival_invokes) == 60 * 60
        warmup[func_name] = arrival_invokes[:warmup_sec]
        invokes[func_name] = arrival_invokes[warmup_sec:total_sec]
        print(f"{func_name} skew {skew_prob:.1%} warmup: max {max(warmup[func_name])} avg {np.mean(warmup[func_name]):.2f}"
            f" workload: max {max(invokes[func_name])} avg {np.mean(invokes[func_name]):.2f}")
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

def get_huawei_at(dir:str, idx, day, start_hour, off=0):
    trace_filepath = path.join(dir, f"day_{day:02}.csv")
    df = pd.read_csv(trace_filepath)
    tmp = df.T
    tmp = tmp.fillna(0).iloc[2:]
    start_min = start_hour * 60 - off
    return tmp.iloc[idx, start_min:start_min + 60]

def huawei_workload(index: dict, dir: str):
    upper_bound = {
        "chameleon": 17,
        "image-processing": 12,
        "image-flip-rotate": 15,
        "pyaes": 18,
        "crypto": 20,
        "image-recognition": 7,
        "video-processing": 10,
        "dynamic-html": 80,
        "pagerank": 18,
        "json-serde": 25,
        "js-json-serde": 25,
      }
    invokes = {}
    warmup = {}
    for func_name in index:
        arrival_invokes = []
        if len(index[func_name]) == 4:
            id, day, start_hour, off = index[func_name]
        else:
            id, day, start_hour = index[func_name]
            off = 0
        skew_prob = 0.4 if '_' not in func_name else 0.1
        trace = get_huawei_at(dir, id, day, start_hour, off)
        max_val_of_trace = max(trace)
        assert trace.shape == (60, )
        for t in range(0, 60):
            left_invokes_per_min = trace.iloc[t]
            if not isinstance(left_invokes_per_min, int):
                left_invokes_per_min = int(left_invokes_per_min + 1e-3)
            # special cases for 0 requests
            if left_invokes_per_min == 0:
                arrival_invokes += [0] * 60
                continue
            if '_' not in func_name and max_val_of_trace == left_invokes_per_min:
                one_min_load = skew_split_one_min_load(left_invokes_per_min)
                service_name = func_name.rsplit('_', 1)[0]
                one_min_load = add_upper_bound_constraint(one_min_load, upper_bound[service_name])
            elif random.random() < skew_prob:
                one_min_load = skew_split_one_min_load(left_invokes_per_min)
                service_name = func_name.rsplit('_', 1)[0]
                one_min_load = add_upper_bound_constraint(one_min_load, upper_bound[service_name])
            else:
                one_min_load = evenally_split_one_min_load(left_invokes_per_min)
            assert sum(one_min_load) == left_invokes_per_min and len(one_min_load) == 60
            arrival_invokes += one_min_load
        assert len(arrival_invokes) == 60 * 60
        warmup[func_name] = arrival_invokes[:5*60]
        invokes[func_name] = arrival_invokes[5*60:]
        warmup_max = max(warmup[func_name])
        warmup_total = sum(warmup[func_name])
        invoke_max = max(invokes[func_name])
        invoke_total = sum(invokes[func_name])
        print(f"{func_name} skew {skew_prob:.1%} off {off} warmup max {warmup_max} total {warmup_total}, invokes max {invoke_max} total {invoke_total}")
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
        "-w", "--workload", type=str, choices=["1", "2", "azure", "ali", "huawei", "func"], required=True, help="the workload to generate"
    )
    # /root/downloads/azurefunction-dataset2019
    parser.add_argument(
        "--dataset", type=str, help="if you want to generate trace of azure or alibaba, please specify dataset path"
    )
    parser.add_argument("--iter", type=int, default=5, help="iteration for func workload")
    args = parser.parse_args()

    if args.workload == "1":
        with open(f"workload-{args.workload}.yml", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
        res, warmup = workload_1(config)
    elif args.workload == "2":
        with open(f"workload-{args.workload}.yml", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
        res, warmup = workload_2(config)
    elif args.workload == "azure":
        if args.dataset is None or len(args.dataset) == 0:
            parser.error("-w/--workload azure requires --dataset")
        index = {
            "image-flip-rotate": 6669,
            "video-processing": 37121,
            "chameleon": 10982,
            "pyaes": 2400,
            "image-processing": 14876,
            "image-recognition": 28412,
            "crypto": 28418,
            "json-serde": 39078,
            "pagerank": 44914,
            "js-json-serde": 26387,
            "dynamic-html": 19236,

            "image-flip-rotate_1": 40905,
            "video-processing_1": 31485,
            # "chameleon_1": 3840,
            "pyaes_1": 11187,
            "image-processing_1": 5195,
            "image-recognition_1": 35943,
            "crypto_1": 8849,
            "pagerank_1": 35278,
            "dynamic-html_1": 4756,

            "image-flip-rotate_2": 36112,
            "video-processing_2": 23833,
            # "chameleon_2": 7659,
            "pyaes_2": 8997,
            "image-processing_2": 29974,
            "image-recognition_2": 15085,
            "crypto_2": 25780,
            "dynamic-html_2": 3237,
        }
        res, warmup = azure_workload(index, args.dataset)
    elif args.workload == "ali":
        if args.dataset is None or len(args.dataset) == 0:
            parser.error("-w/--workload ali requires --dataset")
        index = {
            "dynamic-html": "6f8d9ac59bfa8eff8c53ddc83ad161b5372f14ef",
            "image-flip-rotate": "c095d9e0c27a664d6902aa2fd6f538ec3ba8894a",
            "video-processing": "e576a4f2c918c1166dcec40f7958e11c17cc62ad",
            "chameleon": "a0b745bfcecce6c5dfa80d8e5302cc2e1ffbf9af",
            "pyaes": "3c66fdfa3354c35841d82814ec92a826a26f5e24",
            "image-processing": "f43c6f855fce936da9177b65dfc67ef579edf77e",
            "image-recognition": "9cdb9644ccd8e9a99f4d95c7a3e4bdebb181e717",
            "crypto": "bfe1ad9927f9fbcc1b9989d7fc82ca92fabfc6a4",
            "dynamic-html_1": "97256a15f348b0350a93129691ebdafd14227c9d",
            "image-flip-rotate_1": "20952e985be6abf488a639a189491c8d4da36849",
            "video-processing_1": "6f8d9ac59bfa8eff8c53ddc83ad161b5372f14ef",
            "chameleon_1": "8fd13b83de53b911e072a5e8673a0a29da35c544",
            "pyaes_1": "da10c07532a06efb9a6a89baae980c6f1782503b",
            "image-processing_1": "2e8773e5d82ab7e1da7f937e2e4f472c36e0bca8",
            "image-recognition_1": "e3caff0e323e3d0835838826c336d5fc2fb08653",
            "crypto_1": "c5e35a591b9915b413944fa520c63c7d62433d6a",
            "dynamic-html_2": "e97e7d5d66536d0e5c854a501951ee4e0104a228",
            "image-flip-rotate_2": "36cc3d741b86ad4298c3cdc279ff07f01298f5d9",
            "video-processing_2": "616877714f984e3cf777ee77829c3ebe1304c8a2",
            "chameleon_2": "6d8d38f8d7956864f25f428d349a0c94bff3ce14",
            "pyaes_2": "f7683b06956ceddc5119030e333630f3ec08b31c",
            "image-processing_2": "6d8d38f8d7956864f25f428d349a0c94bff3ce14",
            "image-recognition_2": "7c1846e2a724b584e8a2fcc182a24f47074c7ed6",
            "crypto_2": "c095d9e0c27a664d6902aa2fd6f538ec3ba8894a",
            # a5d16f04c764b7bd3c5bb36d2ae74e96bf7d126c
            # 663e9d923bb282b4624f45707582ff2e33666a1b
            # 6f8d9ac59bfa8eff8c53ddc83ad161b5372f14ef
        }
        res, warmup = ali_scalr_workload(index, args.dataset)
    elif args.workload == "huawei":
        if args.dataset is None or len(args.dataset) == 0:
            parser.error("-w/--workload ali requires --dataset")
        index = {
            # id, day, start, offset
            "image-flip-rotate": (372, 21, 16, -4),
            "video-processing": (372, 1, 17, 2),
            "chameleon": (50, 19, 4),
            "image-recognition": (87, 23, 20),
            "pyaes": (80, 17, 19),
            "image-processing": (372, 1, 15),
            "json-serde": (397, 23, 5),
            "crypto": (372, 0, 15, -2),
            "pagerank": (915, 19, 10, -7),
            "js-json-serde": (200, 19, 1),
            "dynamic-html": (2976, 15, 1),
            
            "image-flip-rotate_1": (181, 0, 16),
            "video-processing_1": (37, 1, 0),
            # "chameleon_1": 3840,
            "pyaes_1": (36, 0, 5),
            "image-processing_1": (36, 0, 2),
            "image-recognition_1": (44, 0, 5),
            "crypto_1": (26, 1, 3),
            "pagerank_1": (472, 0, 23),
            "dynamic-html_1": (38, 1, 9),
            
            "image-flip-rotate_2": (551, 1, 13),
            "video-processing_2": (425, 1, 18),
            # "chameleon_2": 7659,
            "pyaes_2": (181, 0, 1),
            "image-processing_2": (37, 0, 0),
            "image-recognition_2": (44, 3, 2),
            "crypto_2": (181, 0, 7),
            "dynamic-html_2": (38, 0, 10),
        }
        res, warmup = huawei_workload(index, args.dataset)
    elif args.workload == "func":
        with open(f"workload-{args.workload}.yml", "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
        res, warmup = functional_workload(config, args.iter)
    else:
        raise Exception(f"unknown workload args {args.workload}")

    with open(f"workload.json", "w") as f:
        json.dump(res, f, indent=2)

    with open(f"warmup.json", "w") as f:
        json.dump(warmup, f, indent=2)

    # draw_workload(res)

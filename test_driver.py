import gevent
from gevent import monkey

monkey.patch_all()

import matplotlib.pyplot as plt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import subprocess
from time import time
import random
from typing import Dict, List
import re
import logging

logging.basicConfig(format="[%(levelname)s] %(asctime)s %(message)s", level=logging.INFO)


class TestDriver:
    def __init__(self, gateway: str, function_yaml: str = "functions.yml", *, timeout: int = 50, max_retry: int = 3):
        self.gateway = gateway
        self.function_yaml = function_yaml
        self.max_retry = max_retry
        self.timeout = timeout

        retry_strategy = Retry(
            total=max_retry,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)
        self.http = http

        # Check faas-cli
        try:
            subprocess.check_call(["faas-cli", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            choice = input("faas-cli not found, do you want to install it? [Y/n] ")
            if choice == "" or choice.lower() == "y":
                subprocess.check_call("curl -sSL https://cli.openfaas.com | sudo sh", shell=True)
            else:
                print("Error: faas-cli not found")
                exit(1)

    def login(self, username: str, password: str):
        """Login faas-cli"""
        subprocess.check_call(["faas-cli", "login", "-g", self.gateway, "-u", username, "-p", password])

    def logout(self):
        """Logout faas-cli"""
        subprocess.check_call(["faas-cli", "logout", "-g", self.gateway])

    def build(self, parallel: int):
        """Build function images"""
        subprocess.check_call(["faas-cli", "build", "-f", "functions.yml", "--parallel", str(parallel)], cwd="functions")

    def push(self, parallel: int):
        """Push function images"""
        subprocess.check_call(["faas-cli", "push", "-f", "functions.yml", "--parallel", str(parallel)], cwd="functions")

    def deploy(self):
        """Deploy functions"""
        subprocess.check_call(["faas-cli", "deploy", "-f", "functions.yml", "-g", self.gateway], cwd="functions")

    def up(self, parallel: int):
        """Build, push and deploy functions"""
        self.build(parallel)
        self.push(parallel)
        self.deploy()

    def register(self):
        subprocess.check_call(["faas-cli", "register", "-f", self.function_yaml, "-g", self.gateway])

    def invoke(self, lambda_name: str, request_body):
        # Perform a single request
        retry_count = 0
        response = None
        error = None
        e2e_latency = 0
        while response is None or response.status_code != 200:
            start = time()
            try:
                response = requests.post(
                    f"{self.gateway}/invoke/{lambda_name}",
                    json=request_body,
                    timeout=self.timeout,
                )
                if response.status_code != 200:
                    raise RuntimeError(f"[{response.status_code} {response.reason}] {response.text}")
            except Exception as e:
                logging.warning(f"invoke {lambda_name} try {retry_count}th failed: {e}")
                error = e
                if retry_count == self.max_retry:
                    break
                gevent.sleep(0.5 * (2**retry_count))
                retry_count += 1
            else:
                e2e_latency = time() - start
                error = None
        if error is not None or response is None:
            logging.error(f"invoke {lambda_name} FINALLY failed: {error}")
            raise RuntimeError(f"Max retry limit exceeded: {error}")
        if response.text is None or response.text == "":
            raise RuntimeError(f"Empty response from {lambda_name}")
        data = response.json()
        latency = data.get("latency")
        if latency is None:
            raise RuntimeError(f"Invalid response from {lambda_name}")
        res = {"e2e_latency": e2e_latency, "latency": latency, "data": data, "retry_count": retry_count}
        if "recognition" in lambda_name:
            logging.info("%s %s", lambda_name, res)
        else:
            logging.info("%s %s", lambda_name, {"e2e_latency": e2e_latency, "latency": latency, "retry_count": retry_count})
        return res

    def warmup(self, warmup: Dict[str, List[int]], functions: dict):
        logging.info("START warmup...")
        jobs = {}
        total_timeout = 0
        for func, invokes in warmup.items():
            if total_timeout == 0:
                total_timeout = len(invokes)
            else:
                assert total_timeout == len(invokes)
            func_jobs = []
            conf = functions[func]
            request_body = conf.get("request_body")
            for t, invoke_num in enumerate(invokes):
                for _ in range(invoke_num):
                    g = gevent.spawn_later(t + random.random(), self.invoke, func, request_body)
                    func_jobs.append(g)
            jobs[func] = func_jobs
        gevent.joinall(sum(jobs.values(), []), timeout=int(total_timeout * 1.2))

    def cleanup_metric(self):
        response = requests.delete(
            f"{self.gateway}/system/metrics",
            timeout=self.timeout,
        )
        if response.status_code != 200:
            logging.error(f"cleanup_metric failed: [{response.status_code} {response.reason}] {response.text}")
            raise RuntimeError(f"[{response.status_code} {response.reason}] {response.text}")

    def test(self, workloads: Dict[str, List[int]], functions: dict):
        """Test functions"""
        logging.info("START test...")
        jobs = {}
        all_e2e_latency = {}
        all_latency = {}
        all_startup_latency = {}
        total_timeout = 0
        for func, arrival_invokes in workloads.items():
            if total_timeout == 0:
                total_timeout = len(arrival_invokes)
            else:
                assert total_timeout == len(arrival_invokes)
            func_jobs = []
            conf = functions[func]
            request_body = conf.get("request_body")
            for t, invoke_num in enumerate(arrival_invokes):
                for _ in range(invoke_num):
                    g = gevent.spawn_later(t + random.random(), self.invoke, func, request_body)
                    func_jobs.append(g)
            jobs[func] = func_jobs
        gevent.joinall(sum(jobs.values(), []), timeout=int(total_timeout * 1.2))

        startup_latencies = self.get_start_up_latency()
        logging.info("startup_latencies: ", startup_latencies)
        for func, gs in jobs.items():
            e2e_latency = [g.get()["e2e_latency"] for g in gs]
            latency = [g.get()["latency"] for g in gs]

            all_e2e_latency[func] = e2e_latency
            all_latency[func] = latency

            if func not in startup_latencies:
                logging.error(f"find {func} in /system/metrics failed")
                return
            all_startup_latency[func] = startup_latencies[func]
        logging.info("final startup latency: ", all_startup_latency)

        # Draw result
        # self.draw_result(all_e2e_latency, "e2e_latency")
        # self.draw_result(all_latency, "latency")
        # self.draw_result(all_startup_latency, "start_latency")

    def get_start_up_latency(self):
        try:
            response = requests.get(
                f"{self.gateway}/system/metrics",
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(f"[{response.status_code} {response.reason}] {response.text}")
        except Exception as e:
            logging.error(f"request for /system/metrics failed: {e}")
            return {}
        else:
            start_latency = self.parse_latency_metric(response.text, "switch-latency")
            cold_start_latency = self.parse_latency_metric(response.text, "cold-start-latency")
            reuse_counter = self.parse_counter_metric(response.text, "reuse-count")

            for func, reuse_num in reuse_counter.items():
                if func not in start_latency:
                    start_latency[func] = []
                start_latency[func] += [0] * reuse_num

            for func, latency in cold_start_latency.items():
                if func not in start_latency:
                    start_latency[func] = []
                start_latency[func] += latency
            return start_latency

    @staticmethod
    def parse_latency_metric(response_text: str, metric_name: str):
        """
        :param response_text: the response from request to /system/metrics
        :param metric_name: the metric name

        Return a dict with pattern: function_name -> List[latency_in_ms]
        """
        m = re.search(r"latency metric {}: (.*)$".format(metric_name), response_text, re.M)
        if m is None:
            logging.error(f"parse latency metric failed {metric_name}")
            return {}
        pairs = re.findall(r"(.*?) -> \[(.*?)\]", m.group(1), re.M)
        res = {}
        for name, duration in pairs:
            name = name.strip()
            elapsed = []
            for x in duration.split(" "):
                if x.endswith("ms"):
                    elapsed.append(float(x.strip("ms")))
                elif x.endswith("µs"):
                    elapsed.append(float(x.strip("µs")) / 1000)
                elif x.endswith("s"):
                    elapsed.append(float(x.strip("s")) * 1000)
                else:
                    raise RuntimeError(f"unknown suffix: {x}")
            res[name] = elapsed
        return res

    @staticmethod
    def parse_counter_metric(response_text: str, metric_name: str):
        """
        :param response_text: the response from request to /system/metrics
        :param metric_name: the metric name

        Return a dict with pattern: function_name -> List[latency_in_ms]
        """
        m = re.search(r"find grained counter metric {}: (.*)$".format(metric_name), response_text, re.M)
        if m is None:
            logging.error(f"parse latency metric failed {metric_name}")
            return {}
        pairs = re.findall(r"([^ ]*?) -> (\d+)", m.group(1), re.M)
        res = {}
        for name, val in pairs:
            name = name.strip()
            res[name] = int(val)
        return res

    @staticmethod
    def draw_result(data: Dict[str, List[float]], label: str):
        """Draw test result"""
        # Prepare data
        for func in data:
            # Set x axis range
            fig, ax = plt.subplots()
            ax.ecdf(data[func])
            plt.savefig(f"{func}-{label}.png")

    @staticmethod
    def draw_memory_graph(data: list[float], names: list[str]):
        """Draw memory usage graph"""
        # Set x axis range
        x = range(len(names))

        # Draw bar chart
        plt.bar(x, data, width=0.4, label="Max Memory Usage (MB)")

        # Set title, x axis label and y axis label
        plt.title("Memory Usage Comparison")
        plt.xlabel("Function Name")
        plt.ylabel("Memory Usage (MB)")

        # Set x axis scale
        plt.xticks(x, names, rotation=30)

        # Set legend
        plt.legend()

        # Show plot
        plt.subplots_adjust(bottom=0.25)
        plt.show()

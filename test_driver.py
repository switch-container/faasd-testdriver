import gevent
from gevent import monkey

monkey.patch_all()

import json
import matplotlib.pyplot as plt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import subprocess
from time import time
import random
from typing import Dict, List


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
        # Perform test
        retry_count = 0
        response = None
        error = None
        e2e_latency = 0
        while (response is None or response.status_code != 200) and retry_count < self.max_retry:
            start = time()
            try:
                response = requests.post(
                    f"{self.gateway}/invoke/{lambda_name}",
                    json=request_body,
                    timeout=self.timeout,
                )
                if response.status_code != 200:
                    print(f"invoke {lambda_name} try {retry_count}th failed: {response.text}")
                    raise RuntimeError(f"[{response.status_code} {response.reason}] {response.text}")
            except Exception as e:
                error = e
                gevent.sleep(0.5 * (2**retry_count))
                retry_count += 1
                continue
            e2e_latency = time() - start
            error = None
        if error is not None or response is None:
            print(f"invoke {lambda_name} FINALLY failed: {error}")
            raise RuntimeError(f"Max retry limit exceeded: {error}")
        if response.text is None or response.text == "":
            raise RuntimeError(f"Empty response from {lambda_name}")
        data = response.json()
        latency = data.get("latency")
        if latency is None:
            raise RuntimeError(f"Invalid response from {lambda_name}")
        res = {"e2e_latency": e2e_latency, "latency": latency, "data": data}
        print(lambda_name, {"e2e_latency": e2e_latency, "latency": latency}, sep=" ")
        return res

    def test(self, workloads: Dict[str, List[int]], functions: dict):
        """Test functions"""
        jobs = {}
        e2e_latency = {}
        latency = {}
        for func, arrival_invokes in workloads.items():
            func_jobs = []
            conf = functions[func]
            request_body = conf.get("request_body")
            for t, invoke_num in enumerate(arrival_invokes):
                for _ in range(invoke_num):
                    g = gevent.spawn_later(t + random.random(), self.invoke, func, request_body)
                    func_jobs.append(g)
            jobs[func] = func_jobs
        gevent.joinall(sum(jobs.values(), []), timeout=700)
        for func, gs in jobs.items():
            e2e_latency[func] = [g.get()["e2e_latency"] for g in gs]
            latency[func] = [g.get()["latency"] for g in gs]

        # Draw result
        self.draw_result(e2e_latency, "e2e_latency")
        self.draw_result(latency, "latency")

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

import json
import matplotlib.pyplot as plt
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import subprocess
from time import time
from tqdm import tqdm
import tabulate

class TestDriver:
    def __init__(self, gateway: str):
        self.gateway = gateway

        # Check faas-cli
        try:
            subprocess.check_call(['which', 'faas-cli'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            choice = input('faas-cli not found, do you want to install it? [Y/n] ')
            if choice == '' or choice.lower() == 'y':
                subprocess.check_call('curl -sSL https://cli.openfaas.com | sudo sh', shell=True)
            else:
                print('Error: faas-cli not found')
                exit(1)
        subprocess.call(['faas-cli', 'version'])

    def login(self, username: str, password: str):
        '''Login faas-cli'''
        subprocess.check_call(['faas-cli', 'login', '-g', self.gateway, '-u', username, '-p', password])

    def logout(self):
        '''Logout faas-cli'''
        subprocess.check_call(['faas-cli', 'logout', '-g', self.gateway])

    def build(self, parallel: int):
        '''Build function images'''
        subprocess.check_call(['faas-cli', 'build', '-f', 'functions.yml', '--parallel', str(parallel)], cwd='functions')

    def push(self, parallel: int):
        '''Push function images'''
        subprocess.check_call(['faas-cli', 'push', '-f', 'functions.yml', '--parallel', str(parallel)], cwd='functions')

    def deploy(self):
        '''Deploy functions'''
        subprocess.check_call(['faas-cli', 'deploy', '-f', 'functions.yml', '-g', self.gateway], cwd='functions')

    def up(self, parallel: int):
        '''Build, push and deploy functions'''
        self.build(parallel)
        self.push(parallel)
        self.deploy()

    def test(self, functions: dict, timeout: int, max_retry: int, average: int, warm_up_count: int):
        '''Test functions'''
        # Init requests
        retry_strategy = Retry(
            total=max_retry,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=['HEAD', 'GET', 'OPTIONS', 'POST']
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount('https://', adapter)
        http.mount('http://', adapter)
        
        result = []
        for function, conf in tqdm(functions.items(), desc='Testing Functions', unit='function', position=0, ncols=80, leave=None, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]'):
            request_body = conf.get('request_body')

            # Warm up
            for _ in tqdm(range(warm_up_count), desc=f'Warming up {function}', unit='warmup', position=1, ncols=80, leave=None):
                http.post(f'{self.gateway}/function/{function}', json=request_body, timeout=timeout)

            # Perform test
            total_latency = 0
            total_e2e_latency = 0
            total_memory_usage = 0.0
            for _ in tqdm(range(average), desc=f'Testing {function}', unit='test', position=1, ncols=80, leave=None):
                retry_count = 0
                response = None
                error = None
                e2e_latency = 0
                while (response is None or response.status_code != 200) and retry_count < max_retry:
                    start = time()
                    try:
                        response = requests.post(f'{self.gateway}/function/{function}', json=request_body, timeout=timeout)
                        if response.status_code != 200:
                            raise RuntimeError(f'[{response.status_code} {response.reason}] {response.text}')
                    except Exception as e:
                        error = e
                        retry_count += 1
                        continue
                    e2e_latency = time() - start
                    error = None
                if error is not None or response is None:
                    raise RuntimeError(f'Max retry limit exceeded: {error}')
                if response.text is None or response.text == '':
                    raise RuntimeError(f'Empty response from {function}')
                data = response.json()
                latency = data.get('latency')
                if latency is None:
                    raise RuntimeError(f'Invalid response from {function}')
                total_latency += latency
                total_e2e_latency += e2e_latency
                total_memory_usage += data.get('memory_usage', 0)
            result.append({
                'Name': function,
                'Average Latency(ms)': int(total_latency * 1000 / average),
                'Average Other Latencies(ms)': int((total_e2e_latency - total_latency) * 1000 / average),
                'Memory Usage(MB)': total_memory_usage / average
            })
        
        print('Test completed')
        print(tabulate.tabulate(result, headers='keys', floatfmt='.3f', numalign='right'))

        # Draw result
        self.draw_result(result)
        self.draw_memory_graph([item['Memory Usage(MB)'] for item in result], [item['Name'] for item in result])

        return result
    
    @staticmethod
    def draw_result(data: list[dict]):
        '''Draw test result'''
        # Prepare data
        names = [item['Name'] for item in data]
        avg_latency = [item['Average Latency(ms)'] for item in data]
        avg_other_latency = [item['Average Other Latencies(ms)'] for item in data]

        # Set x axis range
        x = range(len(names))

        # Draw bar chart
        plt.bar(x, avg_latency, width=0.4, label='Average Computing Latency (ms)')
        plt.bar(x, avg_other_latency, width=0.4, label='Average Other Latencies (ms)', bottom=avg_latency)

        # Set title, x axis label and y axis label
        plt.title('Latency Comparison')
        plt.xlabel('Function Name')
        plt.ylabel('Average Latency (ms)')

        # Set x axis scale
        plt.xticks(x, names, rotation=30)

        # Set legend
        plt.legend()

        # Show plot
        plt.subplots_adjust(bottom=0.25)
        plt.show()

    @staticmethod
    def draw_memory_graph(data: list[float], names: list[str]):
        '''Draw memory usage graph'''
        # Set x axis range
        x = range(len(names))

        # Draw bar chart
        plt.bar(x, data, width=0.4, label='Max Memory Usage (MB)')

        # Set title, x axis label and y axis label
        plt.title('Memory Usage Comparison')
        plt.xlabel('Function Name')
        plt.ylabel('Memory Usage (MB)')

        # Set x axis scale
        plt.xticks(x, names, rotation=30)

        # Set legend
        plt.legend()

        # Show plot
        plt.subplots_adjust(bottom=0.25)
        plt.show()

import json
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

        # 检查faas-cli
        try:
            subprocess.check_call(['faas-cli', 'version'])
        except:
            choice = input('faas-cli not found, do you want to install it? [Y/n] ')
            if choice == '' or choice.lower() == 'y':
                subprocess.check_call('curl -sSL https://cli.openfaas.com | sudo sh', shell=True)
            else:
                print('Error: faas-cli not found')
                exit(1)

    def login(self, username: str, password: str):
        '''登录faas-cli'''
        subprocess.check_call(['faas-cli', 'login', '-g', self.gateway, '-u', username, '-p', password])

    def logout(self):
        '''登出faas-cli'''
        subprocess.check_call(['faas-cli', 'logout', '-g', self.gateway])

    def build(self, parallel: int):
        '''构建函数镜像'''
        subprocess.check_call(['faas-cli', 'build', '-f', 'functions.yml', '--parallel', str(parallel)], cwd='functions')

    def push(self, parallel: int):
        '''推送函数镜像'''
        subprocess.check_call(['faas-cli', 'push', '-f', 'functions.yml', '--parallel', str(parallel)], cwd='functions')

    def deploy(self):
        '''部署函数镜像'''
        subprocess.check_call(['faas-cli', 'deploy', '-f', 'functions.yml', '-g', self.gateway], cwd='functions')

    def up(self, parallel: int):
        '''构建、推送、部署函数镜像'''
        self.build(parallel)
        self.push(parallel)
        self.deploy()

    def test(self, functions: dict, timeout: int, max_retry: int, average: int, warm_up_count: int):
        '''测试函数'''
        # 初始化requests
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

            # 预热
            for _ in tqdm(range(warm_up_count), desc=f'Warming up {function}', unit='warmup', position=1, ncols=80, leave=None):
                http.post(f'{self.gateway}/function/{function}', json=request_body, timeout=timeout)

            # 测试
            total_latency = 0
            total_e2e_latency = 0
            for i in tqdm(range(average), desc=f'Testing {function}', unit='test', position=1, ncols=80, leave=None):
                start = time()
                response = http.post(f'{self.gateway}/function/{function}', json=request_body, timeout=timeout)
                e2e_latency = time() - start
                if response.status_code != 200:
                    raise f'Error: [{response.status_code} {response.reason}] {response.text}'
                if response.text is None or response.text == '':
                    raise 'Error: Empty response'
                start = response.text.find('{')
                end = response.text.rfind('}')
                if start == -1 or end == -1:
                    raise 'Error: Invalid response'
                data = json.loads(response.text[start:end+1])
                latency = data.get('latency')
                if latency is None:
                    raise 'Error: Invalid response'
                total_latency += latency
                total_e2e_latency += e2e_latency
            result.append({
                'Name': function,
                'Average Latency(ms)': int(total_latency * 1000 / average),
                'Average E2E Latency(ms)': int(total_e2e_latency * 1000 / average)
            })
        
        print('Test completed')
        print(tabulate.tabulate(result, headers='keys', floatfmt='.3f', numalign='right'))
        return result

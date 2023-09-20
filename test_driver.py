import argparse
import json
import multiprocessing
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import subprocess
from time import time
from tqdm import tqdm
import tabulate
import yaml

# 初始化argparse
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', help='config file path (default: config.yml)', default='config.yml')
parser.add_argument('-p', '--parallel', help=f'Build, push images in parallel to depth specified (default: {multiprocessing.cpu_count()})', type=int, default=multiprocessing.cpu_count())
parser.add_argument('action', help='action to perform (default: all)', nargs='*', choices=['login', 'logout', 'build', 'push', 'deploy', 'test', 'all'], default='all')

# 初始化requests
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=1,
    allowed_methods=['HEAD', 'GET', 'OPTIONS', 'POST']
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount('https://', adapter)
http.mount('http://', adapter)

if __name__ == '__main__':
    # 解析命令行参数
    args = parser.parse_args()
    config_file = args.config
    parallel = str(args.parallel)

    # 加载配置文件
    config = None
    with open(config_file, 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    if config is None:
        raise Exception(f'Error: Config {config_file} is invalid')
    provider = config.get('provider', {})
    gateway = provider.get('gateway', 'http://localhost:8080')
    username = provider.get('username', 'admin')
    password = provider.get('password', None)
    functions = config.get('functions', [])
    timeout = config.get('timeout', 60)
    max_retry = config.get('max_retry', 3)
    average = config.get('average', 3)
    warm_up_count = config.get('warm_up_count', 3)

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

    # 登录faas-cli
    if 'login' in args.action or 'all' in args.action:
        print('Logging in')
        if password is None:
            password = input('Please input faas-cli gateway password:')
        subprocess.check_call(['faas-cli', 'login', '-g', gateway, '-u', username, '-p', password])

    if 'all' in args.action:
        print('Building, pushing and deploying functions')
        subprocess.check_call(['faas-cli', 'up', '-f', 'functions.yml', '--parallel', parallel], cwd='functions')
    else:
        # 构建函数
        if 'build' in args.action:
            print('Building functions')
            subprocess.check_call(['faas-cli', 'build', '-f', 'functions.yml', '--parallel', parallel], cwd='functions')

        # 推送函数
        if 'push' in args.action:
            print('Pushing functions')
            subprocess.check_call(['faas-cli', 'push', '-f', 'functions.yml', '--parallel', parallel], cwd='functions')
        
        # 部署函数
        if 'deploy' in args.action:
            print('Deploying functions')
            subprocess.check_call(['faas-cli', 'deploy', '-f', 'functions.yml', '-g', gateway], cwd='functions')

    # 测试函数
    if 'test' in args.action or 'all' in args.action:
        result = []
        for function, conf in tqdm(functions.items(), desc='Testing Functions', unit='function', position=0, ncols=80, leave=None, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]'):
            request_body = conf.get('request_body')

            # 预热
            for i in tqdm(range(warm_up_count), desc=f'Warming up {function}', unit='warmup', position=1, ncols=80, leave=None):
                http.post(f'{gateway}/function/{function}', json=request_body, timeout=timeout)

            # 测试
            total_latency = 0
            total_e2e_latency = 0
            for i in tqdm(range(average), desc=f'Testing {function}', unit='test', position=1, ncols=80, leave=None):
                start = time()
                response = http.post(f'{gateway}/function/{function}', json=request_body, timeout=timeout)
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

    # 登出faas-cli
    if 'logout' in args.action or 'all' in args.action:
        print('Logging out')
        subprocess.check_call(['faas-cli', 'logout', '-g', gateway])

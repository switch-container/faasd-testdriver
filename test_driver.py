import yaml
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import json
from time import time

if __name__ == '__main__':
    # 初始化requests
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=1,
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)

    # 加载配置文件
    config = None
    with open('config.yml', 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    if config is None:
        raise Exception('config.yml is invalid')
    gateway = config.get('gateway', 'http://localhost:8080')
    functions = config.get('functions', [])
    timeout = config.get('timeout', 60)
    max_retry = config.get('max_retry', 3)
    average = config.get('average', 3)

    # 测试函数
    for function, conf in functions.items():
        print(f'Testing {function}')
        request_body = conf.get('request_body')
        total_latency = 0
        total_e2e_latency = 0
        for i in range(average):
            start = time()
            try:
                response = http.post(f'{gateway}/function/{function}', json=request_body, timeout=timeout)
            except Exception as e:
                print(f'\tError: {e}')
                continue
            e2e_latency = time() - start
            if response.status_code != 200:
                print(f'\tError: [{response.status_code} {response.reason}] {response.text}')
                continue
            if response.text is None or response.text == '':
                print(f'\tError: Empty response')
                continue
            start = response.text.find('{')
            end = response.text.rfind('}')
            if start == -1 or end == -1:
                print(f'\tError: Invalid response')
                continue
            data = json.loads(response.text[start:end+1])
            latency = data.get('latency')
            if latency is None:
                print(f'\tError: Invalid response')
                continue
            total_latency += latency
            total_e2e_latency += e2e_latency
            print(f'\tTest {i+1}: latency: {latency}s, end-to-end latency: {e2e_latency}s')
        print(f'\tAverage Latency: {total_latency / average}s')
        print(f'\tAverage End-to-end Latency: {total_e2e_latency / average}s')
    
    print('Test completed')

import argparse
import multiprocessing
import yaml

from test_driver import TestDriver

if __name__ == '__main__':
    # 初始化argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', help='config file path (default: config.yml)', default='config.yml')
    parser.add_argument('-p', '--parallel', help=f'Build, push images in parallel to depth specified (default: {multiprocessing.cpu_count()})', type=int, default=multiprocessing.cpu_count())
    parser.add_argument('action', help='action to perform (default: all)', nargs='*', choices=['login', 'logout', 'build', 'push', 'deploy', 'test', 'all'], default='all')

    # 解析命令行参数
    args = parser.parse_args()
    config_file = args.config
    parallel = args.parallel

    # 加载配置文件
    config = None
    with open(config_file, 'r') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    if config is None:
        raise Exception(f'Error: Config {config_file} is invalid')
    provider = config.get('provider', {})
    gateway = provider.get('gateway', 'http://localhost:8080')

    test_driver = TestDriver(gateway)

    # 登录faas-cli
    if 'login' in args.action or 'all' in args.action:
        print('Logging in')
        username = provider.get('username', 'admin')
        password = provider.get('password', None)
        if password is None:
            password = input('Please input faas-cli gateway password:')
        test_driver.login(username, password)

    if 'all' in args.action:
        print('Building, pushing and deploying functions')
        test_driver.up(parallel)
    else:
        # 构建函数
        if 'build' in args.action:
            print('Building functions')
            test_driver.build(parallel)

        # 推送函数
        if 'push' in args.action:
            print('Pushing functions')
            test_driver.push(parallel)
        
        # 部署函数
        if 'deploy' in args.action:
            print('Deploying functions')
            test_driver.deploy()

    # 测试函数
    if 'test' in args.action or 'all' in args.action:
        functions = config.get('functions', None)
        if functions is None:
            print('Warning: No functions to test')
        else:
            timeout = config.get('timeout', 60)
            max_retry = config.get('max_retry', 3)
            average = config.get('average', 3)
            warm_up_count = config.get('warm_up_count', 3)
            test_driver.test(functions=functions, timeout=timeout, max_retry=max_retry, average=average, warm_up_count=warm_up_count)

    # 登出faas-cli
    if 'logout' in args.action or 'all' in args.action:
        print('Logging out')
        test_driver.logout()

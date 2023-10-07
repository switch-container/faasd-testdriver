import argparse
import yaml
import json

from test_driver import TestDriver

if __name__ == "__main__":
    # 初始化argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="config file path (default: config.yml)", default="config.yml")
    args = parser.parse_args()
    config_file = args.config

    config = None
    with open(config_file, "r") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    if config is None:
        raise Exception(f"Error: Config {config_file} is invalid")
    provider = config.get("provider", {})
    gateway = provider.get("gateway", "http://localhost:8081")
    test_driver = TestDriver(gateway, max_retry=config.get("max_retry", 3), timeout=config.get("timeout", 60))

    workloads = None
    with open("workload_1.json", "r") as f:
        workloads = json.load(f)

    test_driver.test(workloads, config["functions"])

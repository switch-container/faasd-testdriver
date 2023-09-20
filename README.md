# faasd Test Driver

针对 [faasd](https://github.com/openfaas/faasd) 开展的基于 [FunctionBench](https://github.com/ddps-lab/serverless-faas-workbench) 和 [SeBS](https://github.com/spcl/serverless-benchmarks) 的 test driver

## Benchmark 版本

本仓库 `functions` 文件夹中包含了以下版本的 FunctionBench 和 SeBS 中的部分函数，并对进行了修改以适配 faasd 的测试：

- FunctionBench: #cf3e1e9
- SeBS: v1.1

## 准备工作

1. 安装 docker（如需构建镜像）
2. 部署 faasd
3. 安装 [faas-cli](https://github.com/openfaas/faas-cli)（也可在运行本程序时一并安装）
4. 根据需要修改 `config.yml`、 `functions/functions.yml` 中的配置

## 使用方法

```shell
python3 main.py [-h] [-c CONFIG] [-p PARALLEL] [ACTION]
```

支持的参数：

- `-h`：查看帮助
- `-c`、`--config`：指定配置文件，默认为 `config.yml`
- `-p`、`--parallel`：指定**build和push操作**的最大并行度，默认为 CPU 核心数
- `action`：指定需要执行的操作，默认为 `all`，可选项有：
  - `login`：登录 faas-cli
  - `logout`：登出 faas-cli
  - `build`：构建镜像
  - `push`：推送镜像
  - `deploy`：部署函数
  - `test`：测试函数
  - `all`：执行以上所有操作

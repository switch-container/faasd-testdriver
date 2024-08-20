# faasd Test Driver

Test driver for [faasd](https://github.com/openfaas/faasd) based on [FunctionBench](https://github.com/ddps-lab/serverless-faas-workbench) and [SeBS](https://github.com/spcl/serverless-benchmarks)

## Benchmark Version

The `functions` folder in this repo includes the following functions ported from FunctionBench and SeBS:

- FunctionBench: #cf3e1e9
  - chameleon
  - pyaes
  - image-processing
  - video-processing
- SeBS: v1.1
  - dynamic-html
  - image-recognition

## Preparation

1. Install docker (if you need to build function images)
2. Deploy faasd
3. Install [faas-cli](https://github.com/openfaas/faas-cli)
4. Edit `config.yml`、 `functions/functions.yml`

## Usage

```shell
python3 main.py [-h] [-c CONFIG] [-p PARALLEL] [ACTION]
```

Supported Arguments：

- `-h`: help
- `-c`、`--config`: config file, default to `config.yml`
- `-p`、`--parallel`: Parallelism for **build and push operation**, default to CPU core count
- `action`: actions to perform, default to `all`, available actions:
  - `login`: Login faas-cli
  - `logout`: Logout faas-cli
  - `build`: Build function image for faasd
  - `push`: Push image
  - `deploy`: Deploy function
  - `test`: Run test
  - `all`: All above actions

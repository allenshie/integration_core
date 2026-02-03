# Deployment Guide

本文件提供在 Docker/K8s 中使用 integration core 的部署範例。若主專案
將 `integration` 作為子模組導入，建議以套件方式安裝，並使用 `CONFIG_ROOT`
作為相對路徑解析基準。

## Dockerfile（pip 版本）

```dockerfile
WORKDIR /app
COPY . /app

# 安裝 core 套件（editable 方便開發）
RUN pip install -e integration

# 需要時可改成非 editable
# RUN pip install integration
```

環境變數建議：

```
CONFIG_ROOT=/app
PIPELINE_SCHEDULE_PATH=pipeline_schedule.json
```

## Dockerfile（uv 版本）

```dockerfile
WORKDIR /app
COPY . /app

# 安裝 uv
RUN pip install uv

# 使用 uv 安裝 core 套件
RUN uv pip install -e integration
```

環境變數建議：

```
CONFIG_ROOT=/app
PIPELINE_SCHEDULE_PATH=pipeline_schedule.json
```

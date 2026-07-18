#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "=== 流光璃韵 Web 版 ==="
echo ""

if [ ! -d "web/venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv web/venv
fi

source web/venv/bin/activate

echo "安装依赖..."
pip install -q -r web/requirements-web.txt
pip install -q -r requirements.txt

echo ""
echo "启动服务..."
echo "访问地址: http://localhost:8000"
echo ""

python -m uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload

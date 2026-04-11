#!/bin/bash

# Soul's Travel — 一键启动脚本
# 同时启动后端 (Flask :5001) 和前端 (Vite :3000)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════╗${NC}"
echo -e "${BLUE}║      Soul's Travel           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════╝${NC}"
echo ""

# 检查 Node.js 版本（需要 v18+）
NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$NODE_VERSION" ] || [ "$NODE_VERSION" -lt 18 ]; then
  echo -e "${YELLOW}⚠️  Node.js v18+ 未找到，尝试使用 nvm 加载...${NC}"
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
  nvm use 20 2>/dev/null || nvm use --lts 2>/dev/null
fi

# 检查 Python 依赖
echo -e "${GREEN}[1/4] 检查 Python 依赖...${NC}"
cd "$BACKEND_DIR"
pip3 install -r requirements.txt -q

# 初始化数据库并导入样例数据
echo -e "${GREEN}[2/4] 初始化数据库...${NC}"
if [ ! -f "$BACKEND_DIR/travel.db" ]; then
  python3 seed.py
else
  echo "      数据库已存在，跳过 seed"
fi

# 检查前端依赖
echo -e "${GREEN}[3/4] 检查前端依赖...${NC}"
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
  npm install --silent
else
  echo "      node_modules 已存在，跳过安装"
fi

# 启动后端
echo -e "${GREEN}[4/4] 启动服务...${NC}"
echo ""
echo -e "  🐍 后端 → ${BLUE}http://localhost:5001${NC}"
echo -e "  ⚛️  前端 → ${BLUE}http://localhost:5000${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 后台启动后端
cd "$BACKEND_DIR"
python3 app.py &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 前台启动前端（保持终端输出）
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# 等待任意服务退出，然后清理
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait $FRONTEND_PID
kill $BACKEND_PID 2>/dev/null

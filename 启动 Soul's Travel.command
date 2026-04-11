#!/bin/bash

# Soul's Travel — 双击启动
# macOS .command 文件，双击即可在 Terminal 中运行

PROJECT_DIR="/Users/soul/Documents/Cursor/soul's travel"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

clear
echo -e "${BLUE}╔══════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Soul's Travel  ✈️            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════╝${NC}"
echo ""

# 加载 nvm（处理 Node.js 版本）
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

NODE_VER=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$NODE_VER" ] || [ "$NODE_VER" -lt 18 ]; then
  echo -e "${YELLOW}⚠️  切换到 Node.js 20...${NC}"
  nvm use 20 2>/dev/null || nvm use --lts 2>/dev/null || {
    echo -e "${RED}❌ 未找到 Node.js v18+，请先安装：https://nodejs.org${NC}"
    read -p "按回车关闭..."
    exit 1
  }
fi

# 检查/安装 Python 依赖
echo -e "${GREEN}▶ 检查 Python 依赖...${NC}"
cd "$BACKEND_DIR" && pip3 install -r requirements.txt -q 2>&1 | grep -v "already satisfied" || true

# 初始化数据库
if [ ! -f "$BACKEND_DIR/travel.db" ]; then
  echo -e "${GREEN}▶ 首次运行，导入样例数据...${NC}"
  python3 "$BACKEND_DIR/seed.py"
fi

# 检查/安装前端依赖
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo -e "${GREEN}▶ 安装前端依赖（首次约需 1 分钟）...${NC}"
  cd "$FRONTEND_DIR" && npm install --silent
fi

# 启动后端（新 Terminal 标签）
echo -e "${GREEN}▶ 启动后端服务...${NC}"
osascript <<APPLESCRIPT
tell application "Terminal"
  do script "cd '$BACKEND_DIR' && python3 app.py"
end tell
APPLESCRIPT

sleep 2

# 启动前端（当前窗口）
echo ""
echo -e "  ✅  后端运行中 → ${BLUE}http://localhost:5001${NC}"
echo -e "  🚀 正在启动前端..."
echo ""
echo -e "${YELLOW}关闭此窗口即可停止前端服务（后端请关闭另一个 Terminal 窗口）${NC}"
echo "────────────────────────────────────"

cd "$FRONTEND_DIR"
npm run dev


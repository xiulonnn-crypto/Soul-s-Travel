#!/bin/bash

# Soul's Travel — 双击启动
# macOS .command 文件，双击即可在 Terminal 中运行

PROJECT_DIR="/Users/soul/Documents/Cursor/soul's travel"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

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

# 加载 nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

NODE_VER=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$NODE_VER" ] || [ "$NODE_VER" -lt 18 ]; then
  echo -e "${YELLOW}⚠️  切换到 Node.js 20...${NC}"
  nvm use 20 2>/dev/null || nvm use --lts 2>/dev/null || {
    echo -e "${RED}❌ 未找到 Node.js v18+，请先安装：https://nodejs.org${NC}"
    read -rp "按回车关闭..."
    exit 1
  }
fi

# 检查/安装 Python 依赖
echo -e "${GREEN}▶ 检查 Python 依赖...${NC}"
pip3 install -r "$BACKEND_DIR/requirements.txt" -q 2>&1 | grep -v "already satisfied" || true

# 初始化数据库
if [ ! -f "$BACKEND_DIR/travel.db" ]; then
  echo -e "${GREEN}▶ 首次运行，导入样例数据...${NC}"
  python3 "$BACKEND_DIR/seed.py"
fi

# 检查/安装前端依赖
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo -e "${GREEN}▶ 安装前端依赖（首次约需 1 分钟）...${NC}"
  npm --prefix "$FRONTEND_DIR" install --silent
fi

# ── 后台启动后端 ──
echo -e "${GREEN}▶ 启动后端 (port 5001)...${NC}"
python3 "$BACKEND_DIR/app.py" &
BACKEND_PID=$!

# 等待后端就绪
for i in 1 2 3 4 5; do
  sleep 1
  if curl -s http://localhost:5001/api/health >/dev/null 2>&1; then
    break
  fi
done

echo ""
echo -e "  ✅  后端运行中 → ${BLUE}http://localhost:5001${NC}"
echo -e "  🚀  正在启动前端 → ${BLUE}http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 同时停止前端和后端${NC}"
echo "────────────────────────────────────"

# Ctrl+C 清理两个进程
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 前台启动前端
npm --prefix "$FRONTEND_DIR" run dev

# 前端退出后同时关闭后端
kill $BACKEND_PID 2>/dev/null

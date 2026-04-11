# Soul's Travel

个人旅游经历记录与分析工具。AI 辅助录入旅行数据，多维度统计分析，优化未来旅行计划。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Claude API Key (用于 AI 解析功能)

### 后端

```bash
cd backend
pip3 install -r requirements.txt
python3 seed.py          # 导入样例数据（缅甸行程）
python3 app.py           # 启动后端 → http://localhost:5001
```

### 前端

```bash
cd frontend
npm install
npm run dev              # 启动前端 → http://localhost:3000
```

### 环境变量

```bash
export ANTHROPIC_API_KEY="your-api-key"   # AI 解析功能需要
```

## 功能

- **行程管理** — AI 辅助录入（上传 PDF / 自然语言对话），结构化编辑
- **生涯统计** — 目的地排名、开销占比、消费趋势
- **旅行时间线** — 按年分组的垂直时间轴
- **分享** — 生成公开链接让朋友查看行程

## 技术栈

- 前端: React 18 + Vite + Ant Design + Recharts
- 后端: Flask + SQLAlchemy + SQLite
- AI: Claude API (Anthropic)

详细设计见 [DESIGN.md](DESIGN.md)。

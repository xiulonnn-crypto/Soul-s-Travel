# Soul's Travel

个人旅游经历记录与分析工具。AI 辅助录入旅行数据，多维度统计分析，优化未来旅行计划。

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Claude API Key（用于 AI 解析功能）

### 一键启动

```bash
./start.sh
# 后端 → http://localhost:5002
# 前端 → http://localhost:5000
```

### 分步启动

```bash
# 后端
cd backend
pip3 install -r requirements.txt
python3 seed.py          # 导入样例数据（缅甸行程，已有数据时跳过）
python3 app.py           # 启动后端 → http://localhost:5002

# 前端
cd frontend
npm install
npm run dev              # 启动前端 → http://localhost:5000
```

### 环境变量

```bash
export ANTHROPIC_API_KEY="your-api-key"   # AI 解析长文本/PDF 时必填
export AI_API_KEY="your-vision-key"       # AI 解析图片时必填（可选）
```

## 功能

- **行程管理** — AI 辅助录入（上传 PDF / 图片 / 自然语言 / 穷游链接），结构化编辑
- **生涯统计** — 目的地排名、开销占比、消费趋势
- **旅行时间线** — 按年分组的垂直时间轴
- **分享** — 生成公开链接让朋友查看行程
- **行程评价** — 多维度本地规则评分（花费/节奏/住宿/交通/景点）

## 技术栈

- 前端：React 19 + Vite + Ant Design + Recharts
- 后端：Flask + SQLAlchemy + SQLite
- AI：Claude API（Anthropic）+ NLU（jieba + scikit-learn）

## 文档

| 文档 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 项目说明书：编码守则、命名规范、常用命令 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构：服务划分、数据流、模块关系图 |
| [DESIGN.md](DESIGN.md) | 页面设计：组件规范、色彩字体、交互模式 |
| [TECHNICAL.md](TECHNICAL.md) | 技术文档：接口、DB schema、测试、部署 |

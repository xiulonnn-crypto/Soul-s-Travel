# Soul's Travel — 设计文档

个人旅游经历记录与分析工具。AI 辅助录入旅行数据，多维度统计分析，优化未来旅行计划。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + Vite + React Router + Ant Design + Recharts |
| 后端 | Flask + Flask-CORS + SQLAlchemy + pdfplumber |
| AI | Claude API (claude-sonnet-4-20250514) via Anthropic SDK |
| 数据库 | SQLite (单文件) |
| 端口 | 后端 5001 / 前端 3000 (dev) |

## 数据模型

```
Trip 1──* Leg 1──* TripDay
Trip 1──* Expense
Leg  1──* Expense (可选)
TripDay 1──* Expense (可选)
```

### Trip

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| title | TEXT NOT NULL | 行程标题 |
| start_date | DATE NOT NULL | 出发日期 |
| end_date | DATE NOT NULL | 返回日期 |
| traveler_count | INTEGER DEFAULT 1 | 同行人数 |
| description | TEXT | 旅行描述 |
| cover_image | TEXT | 封面图路径 |
| share_token | TEXT UNIQUE | 分享令牌，NULL = 未分享 |
| status | TEXT DEFAULT 'completed' | planned / ongoing / completed |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### Leg (城市站点)

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| trip_id | FK → Trip | |
| order_index | INTEGER NOT NULL | 站点顺序 |
| city | TEXT NOT NULL | 城市名 |
| country | TEXT NOT NULL | 国家名 |
| start_date | DATE NOT NULL | 到达日期 |
| end_date | DATE NOT NULL | 离开日期 |

### TripDay

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| leg_id | FK → Leg | |
| day_number | INTEGER NOT NULL | 全局第几天 |
| date | DATE NOT NULL | |
| description | TEXT | 当日概述 |
| highlights | TEXT | 当日亮点 |
| activities | TEXT (JSON array) | 活动列表 |
| transport | TEXT (JSON array) | 交通信息 |
| accommodation | TEXT | 当晚住宿 |

### Expense

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| trip_id | FK → Trip | |
| leg_id | FK → Leg (可选) | |
| trip_day_id | FK → TripDay (可选) | |
| category | TEXT NOT NULL | 交通/住宿/餐饮/门票/购物/其他 |
| amount | REAL NOT NULL | |
| currency | TEXT DEFAULT 'CNY' | |
| description | TEXT | |
| date | DATE NOT NULL | |

### 设计决策

- 转场日归属出发城市的 Leg
- activities/transport 存 JSON 数组字符串，不建子表
- 开销记总额，人数/数量写在 description

## 页面路由

| 路径 | 页面 | 说明 |
|---|---|---|
| `/` | 首页 | 统计卡片 + 最近行程 |
| `/trips` | 行程列表 | 柔和色卡片列表 + 筛选搜索 |
| `/trips/new` | 新建行程 | 左聊天 + 右表单分屏 |
| `/trips/:id` | 行程详情 | Leg 分块 + 日时间轴 + 开销侧栏 |
| `/trips/:id/edit` | 编辑行程 | 同新建，预填数据 |
| `/timeline` | 时间线 | 按年分组垂直时间轴 |
| `/stats` | 统计 | 概览 + 目的地排名 + 开销图表 |
| `/share/:token` | 分享 | 公开只读，无侧边栏 |

## 核心交互：AI 辅助录入

```
用户上传 PDF / 粘贴文字 / 自然语言对话
          │
          ▼
  POST /api/parse (PDF → pdfplumber 提文本)
          │
          ▼
  Claude API → 结构化 JSON (Trip/Leg/Day/Expense)
          │
          ▼
  前端填充右侧表单 (AI 字段标蓝点)
          │
  用户手动编辑 (dirty flag 防覆盖)
          │
          ▼
  POST /api/trips → 保存数据库
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/parse` | AI 解析文本/PDF → 结构化 JSON |
| GET | `/api/trips` | 行程列表 (支持 ?status=&year= 筛选) |
| POST | `/api/trips` | 创建行程 (含 legs/days/expenses) |
| GET | `/api/trips/:id` | 行程详情 (含关联数据) |
| PUT | `/api/trips/:id` | 更新行程 |
| DELETE | `/api/trips/:id` | 删除行程 |
| POST | `/api/trips/:id/share` | 生成分享令牌 |
| DELETE | `/api/trips/:id/share` | 取消分享 |
| GET | `/api/stats/overview` | 统计概览 |
| GET | `/api/stats/destinations` | 目的地统计 |
| GET | `/api/stats/expenses` | 开销统计 |
| GET | `/api/share/:token` | 公开行程数据 |

## 项目结构

```
soul's travel/
├── backend/
│   ├── app.py                 # Flask 入口，端口 5001
│   ├── database.py            # SQLite + SQLAlchemy 初始化
│   ├── models.py              # Trip / Leg / TripDay / Expense
│   ├── routes/
│   │   ├── trips.py           # 行程 CRUD
│   │   ├── stats.py           # 统计聚合
│   │   ├── share.py           # 分享令牌
│   │   └── parse.py           # AI 解析入口
│   ├── services/
│   │   └── ai_parser.py       # Claude prompt + 调用
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx       # 首页仪表盘
│   │   │   ├── TripList.jsx   # 行程列表
│   │   │   ├── TripDetail.jsx # 行程详情
│   │   │   ├── TripEditor.jsx # AI 对话 + 表单分屏
│   │   │   ├── Timeline.jsx   # 时间线
│   │   │   ├── Stats.jsx      # 统计
│   │   │   └── ShareView.jsx  # 分享
│   │   ├── components/
│   │   │   ├── Layout.jsx     # 72px 图标侧边栏
│   │   │   ├── TripCard.jsx   # 柔和色横排卡片
│   │   │   ├── ChatPanel.jsx  # AI 对话面板
│   │   │   ├── TripForm.jsx   # 结构化表单
│   │   │   ├── ExpenseTable.jsx
│   │   │   ├── TimelineNode.jsx
│   │   │   └── StatsChart.jsx
│   │   ├── services/
│   │   │   └── api.js         # axios 封装
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js         # proxy /api → :5001
├── data/samples/              # 样例数据 (缅甸行程)
├── DESIGN.md
└── README.md
```

## UI 设计系统

参考圆周旅迹 (PiTravel) 风格：清新、轻盈、大留白。

### 色彩

| 用途 | 色值 | 说明 |
|---|---|---|
| 主色 | `#0099ff` | 天蓝，按钮/高亮/选中态 |
| 背景 | `#f5f7fa` | 极浅灰 |
| 卡片 | `#ffffff` | 白色，16px 圆角 |
| 交通 | `#0099ff` | 蓝 |
| 住宿 | `#af52de` | 紫 |
| 餐饮 | `#ff9500` | 橙 |
| 景点 | `#34c759` | 绿 |
| 花费 | `#ff9500` | 橙 |

### 组件规范

- **卡片**: 圆角 16px，阴影 `0 2px 12px rgba(0,0,0,0.06)`，hover 上浮 2px
- **按钮/标签**: 药丸形 `border-radius: 50px`
- **侧边栏**: 72px 宽，白底，图标+文字，选中蓝色高亮
- **行程卡片**: 全宽横排，柔和渐变色背景（绿/黄/蓝/粉/紫），左文右图
- **日期锚点**: 蓝色药丸形 sticky 吸附，左侧 2px 竖线时间轴
- **活动项**: 独立小卡片，分类彩色图标背景
- **图表**: Recharts，折线图带渐变填充

### 响应式

- 桌面: 侧边栏 + 宽内容区
- 移动端: 底部 Tab 导航，卡片单列

## 环境变量

| 变量 | 说明 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 密钥 |

## 启动

```bash
# 后端
cd backend && pip3 install -r requirements.txt && python3 app.py

# 前端
cd frontend && npm install && npm run dev
```

## 样例数据

`data/samples/` 包含缅甸行程真实数据：
- `201910-myanmar.json` — 结构化数据，可导入测试
- `201910-myanmar.csv` — 表格格式
- `201910-myanmar.md` — 人类可读行程总结

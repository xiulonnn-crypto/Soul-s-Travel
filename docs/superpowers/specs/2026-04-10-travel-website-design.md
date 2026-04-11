# Soul's Travel — 个人旅游经历管理网站设计文档

## 1. 项目定位

个人旅游经历记录与分析工具。通过 AI 辅助录入过去的旅行数据，提供多维度统计分析，帮助优化未来旅行计划。支持生成分享链接让朋友查看行程。

**核心价值**: 记录 → 分析 → 优化，不是社交平台也不是预订工具。

## 2. 技术架构

```
前端 (React 18 + Vite)          后端 (Flask + SQLAlchemy)
┌──────────────────┐           ┌──────────────────┐
│ React Router     │  HTTP     │ REST API         │
│ Ant Design       │ ───────── │ Claude API 集成   │
│ Recharts         │  :3000    │ PDF 文本提取      │
└──────────────────┘           │ SQLite 数据库     │
                               └──────────────────┘
                                     :5001
```

- **前端**: React 18 + Vite + React Router + Ant Design + Recharts
- **后端**: Flask + Flask-CORS + SQLAlchemy + Anthropic SDK + pdfplumber（PDF 文本提取）
- **数据库**: SQLite（单文件，零配置）
- **AI**: Claude API，模型 claude-sonnet-4-20250514（文本/PDF 解析为结构化行程数据）
- **端口**: 后端 5001，前端 3000（开发模式）

## 3. 数据模型

### 3.1 Trip（旅行）


| 字段             | 类型                       | 说明                            |
| -------------- | ------------------------ | ----------------------------- |
| id             | INTEGER PK               | 主键                            |
| title          | TEXT NOT NULL            | 旅行标题，如「缅甸7日游」                 |
| start_date     | DATE NOT NULL            | 出发日期                          |
| end_date       | DATE NOT NULL            | 返回日期                          |
| traveler_count | INTEGER DEFAULT 1        | 同行人数                          |
| description    | TEXT                     | 旅行描述                          |
| cover_image    | TEXT                     | 封面图路径                         |
| share_token    | TEXT UNIQUE              | 分享链接令牌，NULL 表示未分享             |
| status         | TEXT DEFAULT 'completed' | planned / ongoing / completed |
| created_at     | TIMESTAMP                | 创建时间                          |
| updated_at     | TIMESTAMP                | 更新时间                          |


### 3.2 Leg（城市站点）


| 字段          | 类型                | 说明   |
| ----------- | ----------------- | ---- |
| id          | INTEGER PK        | 主键   |
| trip_id     | INTEGER FK → Trip | 所属旅行 |
| order_index | INTEGER NOT NULL  | 站点顺序 |
| city        | TEXT NOT NULL     | 城市名  |
| country     | TEXT NOT NULL     | 国家名  |
| start_date  | DATE NOT NULL     | 到达日期 |
| end_date    | DATE NOT NULL     | 离开日期 |


### 3.3 TripDay（每日行程）


| 字段            | 类型               | 说明                     |
| ------------- | ---------------- | ---------------------- |
| id            | INTEGER PK       | 主键                     |
| leg_id        | INTEGER FK → Leg | 所属城市站点                 |
| day_number    | INTEGER NOT NULL | 全局第几天（Day 1, Day 2...） |
| date          | DATE NOT NULL    | 具体日期                   |
| description   | TEXT             | 当日概述                   |
| highlights    | TEXT             | 当日亮点                   |
| activities    | TEXT (JSON)      | 活动列表，JSON 数组           |
| transport     | TEXT (JSON)      | 交通信息，JSON 数组           |
| accommodation | TEXT             | 当晚住宿                   |


### 3.4 Expense（开销）


| 字段          | 类型                   | 说明                          |
| ----------- | -------------------- | --------------------------- |
| id          | INTEGER PK           | 主键                          |
| trip_id     | INTEGER FK → Trip    | 所属旅行                        |
| leg_id      | INTEGER FK → Leg     | 所属城市站点（可选）                  |
| trip_day_id | INTEGER FK → TripDay | 所属日期（可选）                    |
| category    | TEXT NOT NULL        | 交通 / 住宿 / 餐饮 / 门票 / 购物 / 其他 |
| amount      | REAL NOT NULL        | 金额                          |
| currency    | TEXT DEFAULT 'CNY'   | 币种                          |
| description | TEXT                 | 备注                          |
| date        | DATE NOT NULL        | 消费日期                        |


### 3.5 实体关系

```
Trip 1──* Leg 1──* TripDay
Trip 1──* Expense
Leg  1──* Expense
TripDay 1──* Expense
```

Expense 的 leg_id 和 trip_day_id 为可选外键，允许录入不精确到天或城市的开销（只关联到 Trip 层）。

### 3.6 设计决策

- **转场日归属**: 一天横跨两个城市时（如上午曼德勒、傍晚飞蒲甘），该天归属出发城市的 Leg。
- **TripDay 的 activities/transport**: 存储为 JSON 数组字符串，每条是一个描述文本。避免再建子表，保持简单。
- **开销不设 quantity 字段**: 用户直接记录总金额，在 description 中注明人数或数量（如「机票 2人」）。

## 4. 页面结构

### 4.1 整体布局

极简图标侧边栏 + 宽内容区。

```
┌──────┬──────────────────────────────────────┐
│ [S]  │                                      │
│      │            内容区                     │
│ 🏠   │                                      │
│ ✈️   │                                      │
│ 📅   │                                      │
│ 📊   │                                      │
│      │                                      │
└──────┴──────────────────────────────────────┘
 72px
```

- 侧边栏: 72px 宽，白底，图标+文字，选中态蓝色高亮
- 移动端: 切换为底部 Tab 导航

### 4.2 路由


| 路径                | 页面    | 说明           |
| ----------------- | ----- | ------------ |
| `/`               | 首页仪表盘 | 快速统计 + 最近行程  |
| `/trips`          | 行程列表  | 卡片网格，筛选搜索    |
| `/trips/new`      | 新建行程  | AI 对话 + 表单分屏 |
| `/trips/:id`      | 行程详情  | 完整行程展示       |
| `/trips/:id/edit` | 编辑行程  | AI 对话 + 表单分屏 |
| `/timeline`       | 旅行时间线 | 按年份分组的垂直时间轴  |
| `/stats`          | 生涯统计  | 图表仪表盘        |
| `/share/:token`   | 分享页面  | 公开只读，无侧边栏    |


## 5. 功能模块

### 5.1 行程管理 — AI 辅助录入

**核心交互: 左聊天 + 右表单 分屏布局**

左侧（智能对话区）:

- 文本输入框 + PDF 上传按钮
- 支持的输入方式: 上传行程 PDF、粘贴文字描述、自然语言对话
- 对话历史保留在当前编辑会话中
- 用户可通过对话追加修改（如「把 Day 2 住宿改成 XX 酒店」）

右侧（结构化表单）:

- 实时反映 AI 解析结果
- 所有字段均可手动直接编辑
- 前端为每个字段维护「已手动编辑」标记（dirty flag），AI 返回新数据时仅更新未标记的字段；用户在聊天中明确要求修改某字段时，清除该字段的标记后更新
- 底部保存按钮提交最终数据

**AI 解析后端流程**:

1. 前端发送 `POST /api/parse`，body 包含文本内容或 PDF 文件
2. 后端若为 PDF，使用 pdfplumber 提取文本
3. 后端调用 Claude API（claude-sonnet-4-20250514），system prompt 定义输出的 JSON schema（与数据模型一致）
4. Claude 返回结构化 JSON，后端校验后返回前端
5. 前端将解析结果填充到表单
6. 用户确认/修改后，`POST /api/trips` 保存

**Claude prompt 要求**:

- 输出严格符合 Trip/Leg/TripDay/Expense 的 JSON 结构
- 从文本中提取: 日期范围、城市站点、每日活动/交通/住宿、开销明细
- 对模糊或无法确定的信息，在相应字段中标注 `[待确认]`

**行程列表页**:

- 卡片网格布局（响应式：桌面3列，平板2列，手机1列）
- 每张卡片: 标题、国家、日期范围、天数、城市数、总费用
- 筛选: 状态（全部/计划中/已完成）、年份
- 搜索: 按标题和目的地模糊搜索
- 右上角「新建行程」按钮

**行程详情页**:

- 顶部: 标题、日期、人数、总费用/人均费用、分享按钮
- 正文: 按 Leg 分块，每块标题为城市名+日期范围
- 每个 Leg 内: 逐天展示 activities、transport、accommodation
- 底部或右侧: 本次行程开销汇总（按类别饼图）

### 5.2 生涯统计

**页面 `/stats`**，三个区域:

**概览卡片（顶部一行）**:

- 总旅行次数
- 总天数
- 去过的国家数
- 去过的城市数
- 总花费
- 平均每次旅行花费

**目的地统计**:

- 国家访问频次排名（横向柱状图）
- 城市访问频次排名（横向柱状图）
- 每个目的地标注首次和最近访问时间

**开销统计**:

- 按类别占比（饼图: 交通/住宿/餐饮/门票/购物/其他）
- 按旅行对比（柱状图: 每次旅行的总花费）
- 人均日消费趋势（折线图: 每次旅行的人均每天花费）
- 年度花费汇总（柱状图: 按年聚合）

所有图表使用 Recharts 渲染，支持 hover 显示详细数据。

**API**:

- `GET /api/stats/overview` — 总览数字
- `GET /api/stats/destinations` — 目的地统计
- `GET /api/stats/expenses` — 开销统计

### 5.3 旅行时间线

**页面 `/timeline`**:

- 垂直时间轴，从最近到最早排列
- 按年份分组，年份标签醒目显示
- 每个节点展示: 旅行标题、国家、城市列表（如「曼德勒 → 蒲甘 → 茵莱湖」）、日期范围、天数
- 点击节点跳转到行程详情页
- 复用行程列表 API `GET /api/trips?sort=date_desc`，前端做时间线渲染

### 5.4 分享功能

- 行程详情页提供「生成分享链接」按钮
- 点击后调用 `POST /api/trips/:id/share`，后端生成随机 token 写入 Trip.share_token
- 返回链接格式: `{host}/share/{token}`
- 分享页面 `/share/:token`: 只读版行程详情，独立布局（无侧边栏），无需登录
- 行程详情页可点击「取消分享」，将 share_token 置 NULL
- 公开 API: `GET /api/share/:token` 返回行程数据

## 6. API 端点汇总


| 方法     | 路径                      | 说明                            |
| ------ | ----------------------- | ----------------------------- |
| POST   | /api/parse              | AI 解析文本/PDF，返回结构化行程 JSON      |
| GET    | /api/trips              | 行程列表（支持 status/year 筛选）       |
| POST   | /api/trips              | 创建行程（含 legs/days/expenses）    |
| GET    | /api/trips/:id          | 行程详情（含关联的 legs/days/expenses） |
| PUT    | /api/trips/:id          | 更新行程                          |
| DELETE | /api/trips/:id          | 删除行程                          |
| POST   | /api/trips/:id/share    | 生成分享令牌                        |
| DELETE | /api/trips/:id/share    | 取消分享                          |
| GET    | /api/stats/overview     | 统计概览                          |
| GET    | /api/stats/destinations | 目的地统计                         |
| GET    | /api/stats/expenses     | 开销统计                          |
| GET    | /api/share/:token       | 公开行程数据                        |


## 7. 项目目录结构

```
soul's travel/
├── backend/
│   ├── app.py                  # Flask 应用入口
│   ├── database.py             # 数据库初始化
│   ├── models.py               # SQLAlchemy 数据模型
│   ├── routes/
│   │   ├── trips.py            # 行程 CRUD API
│   │   ├── stats.py            # 统计 API
│   │   ├── share.py            # 分享 API
│   │   └── parse.py            # AI 解析 API
│   ├── services/
│   │   └── ai_parser.py        # Claude API 调用与 prompt 管理
│   ├── requirements.txt
│   └── travel.db               # SQLite 数据库文件（运行时生成）
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx        # 首页仪表盘
│   │   │   ├── TripList.jsx    # 行程列表
│   │   │   ├── TripDetail.jsx  # 行程详情
│   │   │   ├── TripEditor.jsx  # 新建/编辑（AI对话+表单分屏）
│   │   │   ├── Timeline.jsx    # 旅行时间线
│   │   │   ├── Stats.jsx       # 生涯统计
│   │   │   └── ShareView.jsx   # 分享页面
│   │   ├── components/
│   │   │   ├── Layout.jsx      # 侧边栏布局
│   │   │   ├── TripCard.jsx    # 行程卡片
│   │   │   ├── ChatPanel.jsx   # AI 对话面板
│   │   │   ├── TripForm.jsx    # 结构化行程表单
│   │   │   ├── ExpenseTable.jsx# 开销表格
│   │   │   ├── TimelineNode.jsx# 时间线节点
│   │   │   └── StatsChart.jsx  # 统计图表
│   │   ├── services/
│   │   │   └── api.js          # API 调用封装
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── data/
│   └── samples/                # 样例数据
│       ├── 201910-myanmar.json
│       ├── 201910-myanmar.csv
│       └── 201910-myanmar.md
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-10-travel-website-design.md
└── README.md
```

## 8. UI 风格

参考圆周旅迹(PiTravel)的设计语言，整体走清新、轻盈、大留白路线。

### 8.1 设计系统

- 组件库: Ant Design
- 主色调: 天蓝色(#0099ff)，清新明亮
- 背景: 极浅灰(#f5f7fa)，大量留白
- 卡片: 大圆角(16px)、柔和阴影(0 2px 12px rgba(0,0,0,0.06))、hover 微浮动
- 按钮/标签: 统一药丸形(border-radius: 50px)
- 分类色彩: 蓝(交通)、紫(住宿)、橙(餐饮/花费)、绿(景点)
- 图表: Recharts，折线图带渐变填充，配色与天蓝主色协调

### 8.2 导航

- 极简图标侧边栏(72px 宽)，白底，只显示图标+文字
- 移动端: 底部 Tab 导航

### 8.3 行程卡片（参考圆周旅迹）

- 全宽大圆角卡片，柔和的渐变/纯色背景（绿/黄/蓝/粉等）
- 左侧: 行程标题(大号加粗)、日期范围、天数/晚数、地点数量
- 右侧: 实景照片缩略图(圆角裁剪)
- 底部: 头像 + 同行人邀请按钮(非必要)

### 8.4 行程详情

- 蓝色药丸形日期锚点(sticky 吸附)，左侧竖线时间轴
- 每个活动项为独立小卡片，带分类彩色图标背景(景点/交通/住宿/餐饮)
- 开销概览在右侧固定列，进度条可视化

### 8.5 UI 原型

高保真 HTML 原型文件存储在 `.superpowers/brainstorm/` 目录中:
- `ui-v2-pitravel-style.html` — 最新版 UI 原型，7 个页面，参考圆周旅迹风格

## 9. 环境配置

- Claude API Key 通过环境变量 `ANTHROPIC_API_KEY` 配置
- 后端启动: `cd backend && python3 app.py`（端口 5001）
- 前端启动: `cd frontend && npm run dev`（端口 3000）
- 前端开发模式通过 Vite proxy 转发 `/api` 请求到后端

## 10. 样例数据

`data/samples/` 目录包含从真实行程 PDF 提取的缅甸行程样例:

- `201910-myanmar.json` — 按数据模型结构化，可作为系统初始测试数据
- `201910-myanmar.csv` — 表格格式，验证导入功能
- `201910-myanmar.md` — 人类可读的行程总结


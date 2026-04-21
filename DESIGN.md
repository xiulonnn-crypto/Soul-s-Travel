# DESIGN.md — 页面设计与交互规范

Soul's Travel 的视觉风格、页面结构、组件规范与交互模式。代码实现时以此为准。

架构与技术栈见 [ARCHITECTURE.md](ARCHITECTURE.md)，接口与数据库见 [TECHNICAL.md](TECHNICAL.md)。

---

## 设计理念

参考圆周旅迹（PiTravel）风格：**清新、轻盈、大留白**。

- 不堆砌信息，每个屏幕只说一件事
- 用色彩区分类别，用留白建立呼吸感
- 动效轻柔，hover 有反馈但不夸张

---

## 设计令牌

### 色彩

| 用途 | 色值 | 说明 |
|------|------|------|
| **主色** | `#0099ff` | 天蓝，按钮/高亮/选中态/Badge |
| **背景** | `#f5f7fa` | 极浅灰，页面大背景 |
| **卡片** | `#ffffff` | 白色 |
| **文字主色** | `#1a1a2e` | 深蓝黑，标题/正文 |
| **文字辅色** | `#8e99a4` | 中灰，副标题/标签/时间 |
| **交通** | `#0099ff` | 蓝 |
| **住宿** | `#af52de` | 紫 |
| **餐饮** | `#ff9500` | 橙 |
| **景点/门票** | `#34c759` | 绿 |
| **购物** | `#ff6b8a` | 粉红 |
| **其他/默认** | `#8e99a4` | 中灰 |

#### 行程卡片渐变色组（循环使用）

| 色组 | 背景渐变 |
|------|----------|
| bg-green | `linear-gradient(135deg, #e8f7ee, #d4f0df)` |
| bg-yellow | `linear-gradient(135deg, #fef6e4, #fdecc8)` |
| bg-blue | `linear-gradient(135deg, #e6f2ff, #cce5ff)` |
| bg-pink | `linear-gradient(135deg, #fde8ef, #fbd0df)` |
| bg-purple | `linear-gradient(135deg, #f0e6f6, #e3d0f0)` |

#### 评价维度配色（TripEvaluation）

| 维度 | 色值 |
|------|------|
| 花费 | `#ff9500` 橙 |
| 节奏 | `#0099ff` 蓝 |
| 住宿 | `#af52de` 紫 |
| 交通 | `#34c759` 绿 |
| 景点 | `#ff6b8a` 粉 |

### 字体

系统字体栈（无需引入外部字体）：

```css
font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Segoe UI', sans-serif;
-webkit-font-smoothing: antialiased;
```

### 字号梯度

| 层级 | 字号 | 用途 |
|------|------|------|
| 页面大标题 | 26–28px | `h1`，页面主标题 |
| 卡片标题 | 17–19px | 行程卡片名称、Leg 城市名 |
| 正文 | 13–14px | 活动描述、表单内容 |
| 辅助文字 | 11–12px | 时间、标签、统计辅助 |
| 微型标签 | 10px | 侧边栏导航文字 |

### 圆角

| 层级 | 圆角值 | 用途 |
|------|--------|------|
| 页面卡片 | `16px` | TripCard、统计卡片、Leg 区块 |
| 小卡片/活动项 | `10–12px` | 日活动 item、输入框容器 |
| 侧边栏导航按钮 | `14px` | `.nav-btn` |
| 药丸/徽标 | `50px` | 按钮、日期锚点、筛选标签 |

### 阴影

```css
/* 标准卡片阴影 */
box-shadow: 0 2px 12px rgba(0,0,0,0.06);

/* hover 浮起 */
box-shadow: 0 6px 20px rgba(0,0,0,0.08);
transform: translateY(-2px);
```

### 间距

- 页面内边距：`28px 32px`
- 卡片列表间距：`14px`
- 卡片内边距：`22–28px`
- 表单行间距：`10–12px`

---

## 布局系统

### 标准页面布局

```
┌──────────────────────────────────────────────┐
│  72px 侧边栏  │          主内容区              │
│  白底，图标+  │  max-width: 1100px            │
│  文字导航     │  padding: 28px 32px           │
└──────────────────────────────────────────────┘
```

侧边栏固定在左，`position: sticky; height: 100vh`。主内容区 `flex: 1` 向右扩展。

### 编辑器分屏布局（TripEditor）

```
┌──────────────────────────────────────────────┐
│  400px ChatPanel  │   剩余宽度 TripForm        │
│  左聊天面板       │   右结构化表单             │
└──────────────────────────────────────────────┘
```

整体占满视口高度（`height: calc(100vh - 56px)`），各区独立滚动。

### 行程详情布局（TripDetail）

```
┌──────────────────────────────────────────────┐
│  主内容区 flex:1  │  280px 侧边栏             │
│  Leg + Day 时间轴 │  开销卡片 + 评价           │
└──────────────────────────────────────────────┘
```

### 分享页（ShareView）

无侧边栏，无 Layout 包裹。居中单列，`max-width: 720px`，顶部 Logo + 标题，底部版权。

---

## 页面规范

### 首页（Home）

- 页面标题：「我的**旅行世界**」（"旅行世界"蓝色高亮）
- 上方：统计药丸行（4 格：旅行次数 / 去过国家 / 旅行天数 / 总花费）
- 下方：「最近行程」标题 + 行程卡片列表（最多 5 条）
- 右上角：「新建行程」主按钮

### 行程列表（TripList）

- 顶部：页面标题 + 行程数量
- 筛选栏：Segmented（全部/completed/planned）+ 搜索框（右侧）
- 列表：TripCard 纵向堆叠
- ProfileDrawer 入口在列表页

### 行程详情（TripDetail）

- 顶部 Hero 卡片：标题 + 日期/人数/状态 Tag + 编辑/分享按钮
- 主内容：Leg 分块（蓝色序号徽标 + 城市名 + 日期）→ 每 Leg 展开 TripDay 列表
- 每个 TripDay：蓝色药丸日期锚点（sticky）→ 左侧竖线时间轴 → 活动/交通/住宿 item 卡片
- 侧边栏：ExpenseTable（费用图表）+ TripEvaluation（评价卡片）

### 新建/编辑行程（TripEditor）

- 左侧 ChatPanel：AI 对话，支持文字 / PDF 文件 / 穷游 URL
- 右侧 TripForm：基本信息（标题/日期/人数）+ 城市站点（Collapse 展开）+ AI 填充字段标蓝点
- AI 解析结果不覆盖用户已手动编辑的字段（dirty flag 保护）

### 时间线（Timeline）

- 页面标题：「旅行**时间线**」
- 按年份降序分组，年份大字 + 次数 Badge
- 每组：左侧 2px 竖线轨道，节点圆点 + TripCard（hover 阴影加深）

### 统计（Stats）

- 上方 6 格概览数字（旅行次数 / 总天数 / 国家 / 城市 / 总花费 / 次均花费）
- 下方 2x2 图表网格：国家排名（自定义条形）/ 开销类别（Pie）/ 各行程花费（Bar）/ 人均日消费趋势（Area）

### 分享（ShareView）

- 无导航，Logo + 行程标题居中
- 展示 Leg → Day 结构（只读，无编辑按钮）
- 底部：「Soul's Travel · 记录旅行，让回忆有迹可循」

---

## 组件规范

### Layout

**职责**：72px 侧边栏包裹所有标准页面。

导航项：首页（`/`）/ 行程（`/trips`）/ 时间线（`/timeline`）/ 统计（`/stats`）。

选中态：蓝色背景 `#e8f4ff` + 文字/图标变 `#0099ff`。

### TripCard

**职责**：行程列表卡片，带渐变背景色，点击进详情。

- 背景色从 `BG_COLORS` 数组按 `index % 5` 循环取
- 展示：标题 / 日期范围 / 天数（粗体） / 城市路线 / 总花费（橙色）
- hover：上浮 2px + 阴影加深，`transition: 0.25s`

### ChatPanel

**职责**：AI 对话面板，解析后调用 `onParsed` 回调。

- 三种输入：文本发送 / 文件上传（PDF/图片）/ 穷游 URL（`plan.qyer.com`）
- 消息气泡：AI 消息左对齐灰底，用户消息右对齐蓝底
- 解析中状态：「解析中...」斜体灰色气泡

### TripForm

**职责**：结构化行程表单，AI 填充字段标蓝点（`.ai-fill`）。

- dirty flag：用户手动修改任意字段后，该字段不再被 AI 覆盖
- AI 填充字段背景：`#f0f9ff`，边框：`#b3deff`
- 城市站点用 Ant Design Collapse 展开，默认展开第 0 项

### ExpenseTable

**职责**：开销总览侧边栏卡片。

- 各类别横向条形图（宽度 = 占比），颜色对应费用分类色
- 底部：合计（粗体大字）/ 人均 / 日均

### TripEvaluation

**职责**：行程评价展示与刷新。

- 加载评价（`GET /api/trips/:id/evaluation`），无缓存则后端生成
- 展示：总分 + summary + 5 个维度卡片（各含评分/说明）+ 建议列表
- 「重新评价」按钮触发 `POST` 刷新

### StatsChart

提供 4 个图表子组件：

| 组件 | 图表类型 | 数据源 |
|------|----------|--------|
| `CategoryPie` | Recharts PieChart | `expenses.by_category` |
| `TripExpenseBar` | Recharts BarChart | `expenses.by_trip` |
| `PerDayTrend` | Recharts AreaChart | `expenses.per_day_trend` |
| `DestinationRank` | 自定义条形 | `destinations.countries` |

### ProfileDrawer

**职责**：侧拉抽屉，展示/编辑用户画像。

- 字段：家庭年收入层级 / 年旅行预算 / 家庭描述
- 展示：已访问国家 / 城市汇总（来自后端统计）

---

## 交互模式

### AI 辅助录入流程

```
用户：上传 PDF / 粘贴文字 / 发送穷游 URL
    ↓
ChatPanel 调用 parseApi
    ↓
后端解析 → 返回 { trip, legs, expenses } 结构
    ↓
前端 onParsed(result) → TripForm 填充右侧表单
    ↓
用户手动校正（AI 字段标蓝，dirty flag 保护已改内容）
    ↓
点击「保存行程」→ POST /api/trips
```

### dirty flag 防覆盖

TripForm 维护一个 `dirty: Set<string>`。用户修改任意字段时，该字段 key 加入 Set。后续 AI 解析结果通过 `useEffect` 更新时，跳过 `dirty` 中已有的 key，保留用户输入。

### 日期锚点 sticky

TripDetail 中每个 TripDay 的日期药丸（`.day-anchor`）采用 `position: sticky; top: 0`，在容器滚动时吸附顶部，始终可见当前日期。

### 行程卡片 hover

```css
.trip-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
  transition: all 0.25s;
}
```

---

## 响应式策略

| 断点 | 布局 |
|------|------|
| 桌面（> 768px） | 72px 侧边栏 + 宽内容区 |
| 移动端（≤ 768px） | 底部 Tab 导航（4 项），卡片单列，无侧边栏 |

> 当前实现以桌面端为主，移动端适配为规划方向。

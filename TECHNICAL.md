# TECHNICAL.md — 技术文档

Soul's Travel 的接口设计、数据库 schema、业务策略逻辑、NLU 系统、测试规范与 Harness 工程规划、工程铁律、部署运维。

---

## 接口设计

### 基本约定

- Base URL：`/api`（开发环境通过 Vite proxy 转发到 `http://localhost:5002`）
- 请求体：`Content-Type: application/json`（文件上传除外，使用 `multipart/form-data`）
- 响应：JSON，成功无固定 envelope，错误统一返回 `{"error": "message"}`

### 完整端点表

| 方法 | 路径 | 描述 | 关键参数 |
|------|------|------|----------|
| GET | `/api/health` | 健康检查 | — |
| **行程** | | | |
| GET | `/api/trips` | 行程列表 | `?status=` `?year=` `?search=` |
| POST | `/api/trips` | 创建行程 | body: Trip + legs + expenses |
| GET | `/api/trips/:id` | 行程详情 | — |
| PUT | `/api/trips/:id` | 更新行程 | body: 部分字段 |
| DELETE | `/api/trips/:id` | 软删除行程 | — |
| PATCH | `/api/trip-days/:dayId/activities` | 追加当日活动 | body: `{activity: string}` |
| **分享** | | | |
| POST | `/api/trips/:id/share` | 生成分享 token | — |
| DELETE | `/api/trips/:id/share` | 撤销分享 | — |
| GET | `/api/share/:token` | 公开读取分享行程 | — |
| **统计** | | | |
| GET | `/api/stats/overview` | 概览数字 | — |
| GET | `/api/stats/destinations` | 目的地排名 | — |
| GET | `/api/stats/expenses` | 开销分析 | — |
| **解析** | | | |
| POST | `/api/parse` | 解析文本/PDF/图片 | `file` (multipart) 或 body: `{text}` |
| POST | `/api/parse/url` | 解析穷游 URL | body: `{url}` |
| **评价** | | | |
| GET | `/api/trips/:id/evaluation` | 获取行程评价（无则生成并缓存） | — |
| POST | `/api/trips/:id/evaluation` | 强制重新生成评价 | — |
| **用户画像** | | | |
| GET | `/api/profile` | 获取用户画像（无则创建默认） | — |
| PUT | `/api/profile` | 更新用户画像 | body: `{household_income, annual_travel_budget, family_description}` |

### 关键请求/响应格式

#### POST /api/trips

```json
{
  "title": "日本关西之行",
  "start_date": "2024-03-01",
  "end_date": "2024-03-07",
  "traveler_count": 2,
  "status": "completed",
  "description": "...",
  "legs": [
    {
      "order_index": 1,
      "city": "大阪",
      "country": "日本",
      "start_date": "2024-03-01",
      "end_date": "2024-03-04",
      "days": [
        {
          "day_number": 1,
          "date": "2024-03-01",
          "activities": ["道顿堀", "心斋桥"],
          "transport": ["飞机 PVG→KIX 09:00"],
          "accommodation": "难波 APA 酒店",
          "description": "抵达大阪"
        }
      ]
    }
  ],
  "expenses": [
    {
      "category": "交通",
      "amount": 6200,
      "currency": "CNY",
      "description": "往返机票 2人",
      "date": "2024-03-01"
    }
  ]
}
```

#### GET /api/trips（列表，含摘要字段）

响应中每条行程含：`id, title, start_date, end_date, traveler_count, status, destination_label, leg_count, total_expense`。

#### POST /api/parse 响应

```json
{
  "type": "trip",
  "trip": { "title": "...", "start_date": "...", "end_date": "...", "traveler_count": 2 },
  "legs": [...],
  "expenses": [...]
}
```

短文本 NLU 解析返回格式见「NLU 系统」章节。

### 错误码

| HTTP 状态码 | 含义 |
|------------|------|
| 400 | 参数缺失或格式错误 |
| 404 | 资源不存在（Trip not found 等） |
| 500 | 服务端内部错误（含 AI 调用失败） |
| 502 | 上游服务失败（穷游抓取超时等） |

---

## 数据库表结构

SQLite 单文件，路径 `backend/travel.db`，由 SQLAlchemy 管理。

### trips

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | |
| title | TEXT | NOT NULL | 行程标题 |
| start_date | DATE | NOT NULL | 出发日期 |
| end_date | DATE | NOT NULL | 返回日期 |
| traveler_count | INTEGER | DEFAULT 1 | 同行人数 |
| description | TEXT | | 旅行描述 |
| cover_image | TEXT | | 封面图路径（未实现上传） |
| share_token | TEXT | UNIQUE | 分享令牌，NULL = 未分享 |
| status | TEXT | DEFAULT 'completed' | planned / ongoing / completed |
| is_deleted | BOOLEAN | NOT NULL DEFAULT 0 | 软删除标记 |
| created_at | DATETIME | | 创建时间 |
| updated_at | DATETIME | | 最后修改时间 |

### legs

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | |
| trip_id | INTEGER | FK trips.id | |
| order_index | INTEGER | NOT NULL | 站点顺序（从 1 开始） |
| city | TEXT | NOT NULL | 城市名（中文） |
| country | TEXT | NOT NULL | 国家名（中文） |
| start_date | DATE | NOT NULL | 到达日期 |
| end_date | DATE | NOT NULL | 离开日期 |

### trip_days

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | |
| leg_id | INTEGER | FK legs.id | |
| day_number | INTEGER | NOT NULL | 全局第几天（从 1 开始） |
| date | DATE | NOT NULL | |
| description | TEXT | | 当日概述 |
| highlights | TEXT | | 当日亮点 |
| activities | TEXT | DEFAULT '[]' | **JSON 字符串数组**，活动列表 |
| transport | TEXT | DEFAULT '[]' | **JSON 字符串数组**，交通信息 |
| accommodation | TEXT | | 当晚住宿名称 |

### expenses

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | |
| trip_id | INTEGER | FK trips.id NOT NULL | |
| leg_id | INTEGER | FK legs.id | 可选，关联城市段 |
| trip_day_id | INTEGER | FK trip_days.id | 可选，关联具体天 |
| category | TEXT | NOT NULL | 交通/住宿/餐饮/门票/购物/其他 |
| amount | REAL | NOT NULL | 总金额（已转换为 CNY） |
| currency | TEXT | DEFAULT 'CNY' | 原始货币代码 |
| description | TEXT | | 描述，含人数/数量信息 |
| date | DATE | NOT NULL | |

### trip_evaluations

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | |
| trip_id | INTEGER | FK trips.id UNIQUE | 每行程最多一条 |
| overall_score | INTEGER | NOT NULL | 综合评分（0–100） |
| evaluation_data | TEXT | NOT NULL | JSON 字符串，含 summary/dimensions/cities/suggestions |
| created_at | DATETIME | | |
| updated_at | DATETIME | | |

### user_profiles

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | |
| household_income | REAL | DEFAULT 1600000 | 家庭年收入（元） |
| annual_travel_budget | REAL | DEFAULT 100000 | 年旅行预算（元） |
| family_description | TEXT | DEFAULT '夫妻两人' | 家庭描述 |
| visited_countries_cities | TEXT | DEFAULT '{}' | JSON 字符串，已访问国家/城市统计 |
| created_at | DATETIME | | |
| updated_at | DATETIME | | |

> 单例：通过 `_get_or_create_profile()` 确保只有一条记录。

### 设计决策

- **转场日归属出发城市的 Leg**：某天从 A 城出发去 B 城，该天归 A 的 Leg
- **activities / transport 存 JSON 字符串**：无需独立查询，不建子表
- **expenses 存总金额**：人数/数量写在 description；外币在解析时按固定汇率换算为 CNY
- **软删除**：`DELETE /api/trips/:id` 设置 `is_deleted=True`，列表查询自动过滤

---

## 业务策略逻辑

### 解析管道

```
POST /api/parse
    ├── 文件 = 图片（.jpg/.png/.webp 等）
    │   └── services/image_parser.py → Vision API → 返回 {type:'trip', trip, legs, expenses}
    │
    ├── 文件 = PDF
    │   └── file_extractor.extract_text_from_pdf()
    │         ├── 主：pymupdf4llm.to_markdown() + pdfplumber 页 0 概览表
    │         └── 降级：pdfplumber 混合 → pdfminer.six → parse_text()
    │
    ├── 文件 = 其他文本
    │   └── UTF-8 解码 → parse_text()
    │
    └── JSON body.text
        └── parse_text()

POST /api/parse/url
    └── url_scraper.scrape_qyer_url()  // Playwright 移动 UA 抓取
        └── parse_qyer_web()            // 穷游 m 站格式解析
```

**`parse_text()` 内部路由**：

```python
if _is_short_command(text):
    return _nlu_parse(text)   # 短文本 → NLU 意图分类 + 槽位抽取
else:
    return _parse_long_text(text)  # 长文本 → 规则解析
```

**PDF 文本抽取链路**（`backend/services/file_extractor.py`）：

1. 主路径 `_extract_via_pymupdf4llm`：[pymupdf4llm](https://github.com/pymupdf/PyMuPDF)（AGPL-3.0）对全文档产出 Markdown。它原生解码 PUA 字符、不产生重复字符、并把费用表 `第N天（总价：¥…）` 保留为可读表头。
2. 主路径补充：pymupdf4llm 的 layout 分析**不**重建穷游概览表（`01\n星期三 … 1. 景点名`），所以把 pdfplumber 仅对页 0 抽出的表格形式文本**前置拼接**——为 `_split_by_day` / `_extract_activities` 保留 `\nNN\s+星期X` 与 `1. 景点名` 锚点。
3. 主路径 adapter `_adapt_pymupdf4llm_output`：剥 `[name](url)` 的 Markdown 链接、把偶发的 `第4 天` 修正为 `第4天`，再交给 `markdown_to_plain` 压扁表格。
4. 降级条件：pymupdf4llm 抛异常、或其输出里找不到任何 `\n(\d{2})\s+星期[一二三四五六日天]` 锚点时，自动回退到 pdfplumber 混合抽取（`_hybrid_extract`）→ pdfminer.six 全文兜底。

**长文本规则解析流程**（`ai_parser.parse_text`）：
1. `_normalize(text)`：去除 PDF 特殊字符、全角半角统一、双字节字符去重（防 PDF 乱码）
2. 提取行程头：标题、开始日期、天数、人数
3. 按「第 N 天」切分文本块
4. 逐块提取：城市站点（`DEST_CITIES` 表匹配）/ 活动 / 交通 / 住宿 / 费用表
5. 费用表正则：支持 CNY/USD/EUR/JPY/KRW/HKD/SGD/THB/MYR/TWD 多货币，按 `_CNY_PER_UNIT` 汇率换算
6. 住宿反填：遇到酒店名时，回填到对应 TripDay 的 accommodation 字段

**PDF 历史回归测试**：`backend/tests/test_pdf_fixtures.py` 参数化加载 `backend/tests/fixtures/pdf_ground_truth/*.json`。每个 JSON 包含一个真实 PDF 的 trip / legs / expenses / required_attractions / required_accommodations 权威值。PDF 不在磁盘时 `pytest.skip`（CI 友好）；本地 7 份 PDF + 12 种断言 = 82 passed / 2 skipped。未打通的 parser 层漂移在 fixture `known_drifts` 字段里留痕，不阻塞本次抽取层交付。

**穷游 PDF 概览表的 DAY 标记格式差异**（`_split_by_day` 必须同时兼容）：

pdfminer 对穷游概览表每天的日期-星期单元格会输出两种形态，取决于该行其他单元格的文字密度：

| 形态 | 示例文本 | 何时出现 |
|---|---|---|
| A: 换行分隔 | `\n01\n星期三 Beijing…` | 该行其他单元格文字较长，DD 被挤到独立行 |
| B: 同行紧贴 | `\n02 星期四 Busan…` | 该行其他单元格较短，DD 与星期 保持在同一行 |

**同一份 PDF 可能混用两种形态**（2024-05 韩国行程即是如此：day 01/03/04 为 A 形，day 02/05 为 B 形）。因此 `_split_by_day` 使用 `\n(\d{2})\s+星期[一二三四五六日天]`（`\s+` 同时吞换行与空格），不能退化为 `\n(\d{2})\n\s*星期`。同样的正则也用于 `parse_text` 里把概览表航班出发时段映射回当天。

**关键常量**（三表必须同步，见 CLAUDE.md 禁止事项）：
- `DEST_CITIES`：已知目的地城市集合
- `COUNTRY_MAP`：城市 → 国家映射
- `_EN_TO_ZH_CITY`：英文城市名 → 中文映射

### NLU 短文本解析

触发条件：文本长度 ≤ 阈值（`_is_short_command` 判定）。

**意图列表**（来自 `nlu/training_data.yml`）：

| 意图 | 示例 | 返回 type |
|------|------|-----------|
| `add_expense` | "加一笔交通费 200 元" | `add_expense` |
| `change_category` | "把机票改为交通" | `change_category` |
| `set_accommodation` | "第 3 天住丽思卡尔顿" | `set_accommodation` |
| `rename_activity` | "把故宫改名为紫禁城" | `rename_activity` |
| `remove_expense` | "删掉那笔购物费用" | `remove_expense` |
| `add_activity` | "第 2 天加一个景点" | `add_activity` |

**复合指令**：用分号 `；` 或 `;` 分隔的多条指令，返回：

```json
{
  "type": "compound",
  "actions": [
    {"type": "add_expense", "expenses": [...]},
    {"type": "change_category", "item_name": "...", "target_category": "交通"}
  ]
}
```

### 行程评价系统

纯本地规则，无 LLM 调用。

**评分维度**：花费合理性 / 行程节奏 / 住宿质量 / 交通效率 / 景点覆盖，各维度 0–100 分，加权合成总分。

**个性化调整**：
1. 读取 `UserProfile.annual_travel_budget` → 确定消费层级（经济 / 舒适 / 豪华）
2. 读取 `city_benchmarks.json` 对应城市基准价格
3. 按季节（月份）调整基准（旺季上调）
4. 实际日均花费 vs 调整后基准 → 花费评分

**口径一致性**：`avg_daily_cost_cny` 代表城市内日均消费（住宿 + 餐饮 + 本地交通 + 景点），不含国际/城际大交通。因此花费评分计算时，用户花费侧也剔除大交通（`_is_flight_expense`）。大交通检测采用分层策略：关键词匹配（机票/高铁等）→ 路线模式匹配（"A到B"格式）→ 本地交通排除（打车/Grab/机场到酒店等）。

**缓存**：评价结果存 `TripEvaluation` 表，`GET` 先查缓存；`POST` 强制重新生成。

---

## NLU 系统

**技术**：jieba 分词 + TF-IDF（bigram）+ LinearSVC

**训练**：
```bash
cd backend
python3 -c "from services.nlu.train import train; train()"
# 或
python3 services/nlu/train.py
```

训练数据：`services/nlu/training_data.yml`，格式：

```yaml
add_expense:
  - "加一笔交通费200元"
  - "记录一下昨天的住宿费"
change_category:
  - "把机票改为交通"
  ...
```

**模型**：训练后保存为 `services/nlu/model.pkl`，首次使用自动加载或训练。

**接口**：

```python
from services.nlu.classifier import classify, classify_with_confidence

intent = classify("加一笔200元交通费")           # → "add_expense"
intent, confidence = classify_with_confidence("...")
```

---

## 测试规范

### 当前状态

| 指标 | 现状 |
|------|------|
| 测试框架 | pytest 8.3.5 |
| 测试文件数 | 7 |
| 测试函数数 | ~131 |
| DB 隔离 | autouse fixture 替换全局 Session 为内存 SQLite |
| 覆盖率工具 | **无** |
| CI | **无** |
| pytest 配置 | **无** pyproject.toml（路径靠 sys.path hack） |
| 前端测试 | **无** |

### 现有测试覆盖

| 文件 | 测试数 | 覆盖内容 |
|------|--------|----------|
| `test_models.py` | 4 | ORM 创建/to_dict/级联删除 |
| `test_trips.py` | 8 | Trip CRUD API（含 leg/day/expense 嵌套） |
| `test_stats.py` | 5 | Stats API 三个端点 |
| `test_share.py` | 1 | 分享完整流程 |
| `test_parser_japan.py` | ~54 | 日本 PDF 解析 + NLU |
| `test_parser_korea.py` | ~22 | 韩国 PDF、USD 费用、类型归类 |
| `test_parser_multi_pdf.py` | ~37 | 斯里兰卡、PUA 箭头、复合指令 |

### 覆盖缺口（规划补充）

| 缺失覆盖 | 优先级 |
|----------|--------|
| `GET/POST /api/trips/:id/evaluation` | 高 |
| `GET/PUT /api/profile` | 高 |
| `POST /api/parse`（含图片分支、URL 分支） | 高 |
| `PATCH /api/trip-days/:id/activities` | 中 |
| 跨货币费用解析正确性断言 | 中 |
| 评价系统 `evaluator.py` 单元测试 | 中 |

---

## Harness 工程规划

> 当前状态：无 CI、无覆盖率、无 pytest 标准配置。以下为待实施的工程化改进计划，按优先级排序。

### 第一层：基础设施

**1. pytest 项目配置**

创建 `backend/pyproject.toml`，消除所有 `sys.path.insert` hack：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

同时删除所有测试文件开头的 `sys.path.insert(0, ...)` 行。

**2. 公共 fixtures 提取**

当前 `client` fixture 在 `test_trips.py`、`test_stats.py`、`test_share.py` 中各自重复定义。目标：统一到 `tests/conftest.py`：

```python
@pytest.fixture
def client(isolated_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
```

`test_stats.py` 的预填数据移到各测试函数内（或单独 fixture）。

**3. 覆盖率工具链**

```
# 安装
pip3 install pytest-cov

# 运行
python3 -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
```

在 `pyproject.toml` 中配置：

```toml
[tool.coverage.run]
source = ["."]
omit = ["tests/*", "seed.py", "services/nlu/train.py"]

[tool.coverage.report]
show_missing = true
```

目标基线：核心业务逻辑（routes + models）≥ 80%。

**4. 后端 Lint**

```
pip3 install ruff
```

`pyproject.toml` 中配置：

```toml
[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
```

### 第二层：CI / 自动化

**5. GitHub Actions 管道**

创建 `.github/workflows/ci.yml`：

```yaml
name: CI
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip3 install -r backend/requirements.txt pytest-cov ruff
      - run: cd backend && ruff check .
      - run: cd backend && python3 -m pytest tests/ --cov=. --cov-fail-under=70
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm install
      - run: cd frontend && npm run lint
      - run: cd frontend && npm run build
```

**6. Makefile 统一入口**

创建项目根目录 `Makefile`：

```makefile
test:
	cd backend && python3 -m pytest tests/ -v

coverage:
	cd backend && python3 -m pytest tests/ --cov=. --cov-report=term-missing

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

lint-fix:
	cd backend && ruff check . --fix
	cd frontend && npm run lint -- --fix

check-all: lint test

check-city:
	cd backend && python3 -c "from services.ai_parser import _EN_TO_ZH_CITY, DEST_CITIES, COUNTRY_MAP; missing=[c for c in DEST_CITIES if c not in COUNTRY_MAP]; print('Missing COUNTRY_MAP:', missing or 'none')"
```

**7. TEC 规则自动检查**

三表一致检查（新增城市后运行）：

```bash
make check-city
```

API 契约变更检测（修改后端 response type 后手动运行）：

```bash
rg "result\.type|result\[.type.\]|\.type ===" frontend/src/
```

### 第三层：测试补全

**8. 后端 mock 基础设施**

```
pip3 install pytest-mock
```

为以下场景建立 mock：
- `services/ai_parser.py` 中的 Claude API 调用（`Anthropic.messages.create`）
- `services/image_parser.py` 中的 Vision API 调用
- `services/url_scraper.py` 中的 Playwright 调用

**9. 前端 Vitest 框架**

```bash
cd frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

`vite.config.js` 添加 test 配置：

```js
test: {
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.js'],
}
```

**10. 前端 API 服务层测试**

测试 `src/services/api.js` 的请求构建和错误处理（mock axios）。

**11. 核心组件测试**

优先：`TripForm`（dirty flag 逻辑）、`ChatPanel`（消息渲染）、`ExpenseTable`（计算正确性）。

### 治理

**12. 端口统一**

当前所有文档（CLAUDE.md / ARCHITECTURE.md）和代码已统一为 **后端 5002 / 前端 5000**。旧文档 `README.md` / `DESIGN.md` 的端口信息已更新。

---

## 工程铁律

以下规则来源于真实踩坑复盘，每条都有失败案例。

### 1. API 契约变更必须同步消费端

**规则：** 后端 response 新增 `type`、重命名字段、改变结构时，同一次修改必须包含前端对应处理。

**来源：** NLU 复合指令修复（2026-04）。后端新增 `type: 'compound'` 返回，但前端 `handleParsed` 无此分支，所有 actions 被静默丢弃。

**检查方法：**
```bash
rg "result\.type|result\[.type.\]|\.type ===" frontend/src/
```

**铁律：** 改了生产端不改消费端 = 交付了一条断路管道。

---

### 2. 测试断言到叶子节点

**规则：** 不要只断言结构存在，要断言最终值正确。

**来源：** 复合指令测试只验了 `type == 'compound'` 和 `len(actions) >= 2`，没验每个 action 内容 → 误判为修复成功。

**对比：**
```python
# BAD — 浅断言，结构对但值错也通过
assert result['type'] == 'compound'
assert len(result['actions']) >= 2

# GOOD — 叶子断言，验证用户会看到的值
assert result['actions'][0]['expenses'][0]['amount'] == 6206
assert result['actions'][1]['target_category'] == '交通'
assert result['actions'][2]['type'] == 'remove_expense'
```

---

### 3. 跨层 bug 必须端到端验证

**规则：** 涉及后端+前端的 bug，Phase 4 验证必须覆盖完整数据流，不接受单侧验证。

**来源：** 第一次修复只跑了 Python 脚本验证后端输出正确，但没验前端渲染 → 用户看到的结果没变。

**完整数据流：**
```
用户输入 → 后端处理 → API 响应 → 前端接收 → 前端处理 → UI 更新
                                                         ↑ 验证终点
```

---

### 4. 城市/地理数据三表一致

**规则：** 新增城市时，`_EN_TO_ZH_CITY`、`DEST_CITIES`、`COUNTRY_MAP` 三张表必须同步更新。

**来源：** 早期只加了 `DEST_CITIES` 没加英文映射，导致英文城市名无法识别。

**检查方法：**
```bash
make check-city
# 或
cd backend && python3 -c "
from services.ai_parser import _EN_TO_ZH_CITY, DEST_CITIES, COUNTRY_MAP
missing_country = [c for c in DEST_CITIES if c not in COUNTRY_MAP]
print('Missing COUNTRY_MAP:', missing_country or 'none')
"
```

---

### 5. 新增返回类型的完整检查清单

当后端 `parse_text()` 返回新 `type` 时：

- [ ] `backend/services/nlu/extractors.py` — extractor 返回正确字段
- [ ] `backend/services/ai_parser.py` — `_nlu_parse` 路由到正确 extractor
- [ ] `frontend/src/pages/TripEditor.jsx` — `applyAction` 有对应分支
- [ ] `frontend/src/components/ChatPanel.jsx` — 聊天消息有对应提示文案
- [ ] `backend/tests/` — 测试覆盖新 type 的叶子值

---

### 6. 数据解析 bug 必须先做完整性审计

**规则：** 排查解析 bug 时，Phase 1 必须先建立源数据的完整期望清单（条数、字段、值域），再对比输出做差分。

**失败模式：** Symptom-First Tunnel Vision（症状优先隧道视觉）

**来源：** 韩国 PDF 费用解析（2026-04）。PDF 有 10 行费用（8×CNY + 2×USD），第一次修复只处理了日期乱码，验证时确认 8 条日期全部正确就交付了。但正则写死 `CNY`，2 条 USD 从始至终被静默跳过。

**检查方法（Phase 1 必选）：**
```bash
cd backend && python3 -c "
import pdfplumber, re
with pdfplumber.open('xxx.pdf') as pdf:
    text = '\n'.join(p.extract_text() or '' for p in pdf.pages)
_CURR = r'(?:CNY|USD|EUR|JPY|KRW|HKD|SGD|THB|MYR|TWD)'
rows = re.findall(r'.{2,30}\s+' + _CURR + r'\s*[\d,.]+\s+\d+\s+' + _CURR + r'\s*[\d,.]+', text)
print(f'源数据费用行: {len(rows)}')
"
```

**铁律：** 正确的值 × 不完整的条数 = 不完整的修复。必须包含 `源条数 == 输出条数` 断言。

---

### 7. 正则解析器禁止写死单一格式

**规则：** 当正则匹配「可变格式」字段时，必须用显式枚举或通配，禁止写死单一值。

**来源：** `_parse_expenses` 正则写死 `CNY`，导致 USD/EUR 等外币行被静默跳过，无错误提示、无日志。

**对比：**
```python
# BAD
r'(.{2,30}?)\s+CNY\s*([\d,.]+)\s+(\d+)\s+CNY\s*([\d,.]+)'

# GOOD
_CURR = r'(?:CNY|USD|EUR|JPY|KRW|HKD|SGD|THB|MYR|TWD)'
r'(.{2,30}?)\s+(' + _CURR + r')\s*([\d,.]+)\s+(\d+)\s+' + _CURR + r'\s*([\d,.]+)'
```

**铁律：** 硬编码单一格式 + 无警告 = 定时炸弹。

---

## 部署与运维

### 开发环境启动

```bash
# 一键启动（推荐）
./start.sh

# 分别启动
cd backend && python3 app.py          # 后端 :5002
cd frontend && npm run dev            # 前端 :5000
```

### 初始化

```bash
cd backend
pip3 install -r requirements.txt
python3 seed.py    # 导入缅甸样例数据（已有数据时自动跳过）
```

### 环境变量

通过 `backend/.env` 或系统环境变量注入，`python-dotenv` 在 `app.py` 入口处加载：

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Claude API，解析长文本/PDF 时必填
AI_API_KEY=sk-...              # Vision API，解析图片时必填
AI_MODEL=gpt-4o                # Vision 模型名（可选）
AI_BASE_URL=https://...        # Vision API endpoint（可选）
```

### 日志

当前无结构化日志，Flask debug 模式输出到 stdout。规划中：
- 解析管道关键节点打 `logging.info`
- 外部 API 调用异常打 `logging.error` 含请求摘要

### 数据库维护

```bash
# 查看当前数据（SQLite）
sqlite3 backend/travel.db ".tables"
sqlite3 backend/travel.db "SELECT count(*) FROM trips;"

# 重置数据库（危险！）
rm backend/travel.db && cd backend && python3 seed.py
```

### 生产部署（规划中）

目前为纯开发环境。生产部署方向：

- 后端：gunicorn + nginx 反代
- 前端：`npm run build` 生成 `dist/`，nginx 静态服务
- 数据库：升级为 PostgreSQL（SQLAlchemy 无缝切换）
- 环境变量：通过 systemd 或 Docker env 注入

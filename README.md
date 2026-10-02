# 前沿进展调研报告自动生成系统（SurveyGen）

> 输入研究关键词 → arXiv 检索 → 勾选论文成集 → 下载解析 PDF → 中英翻译 → 自动生成报告目录与章节 → 在线编辑 → 一键导出 Markdown / Word / PDF。

一个**本地运行的 Web 系统**，用于把「读一批论文 → 写一篇领域前沿进展调研报告」这条链路自动化。前端 React 单页应用，后端 FastAPI + SQLite，大模型走任意 OpenAI 兼容接口。

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API 一览](#api-一览)
- [数据存储](#数据存储)
- [常见问题](#常见问题)
- [免责声明](#免责声明)

---

## 项目简介

写一篇「某某方向的前沿进展调研」通常要经历：检索文献、筛文献、读文献、整理综述、排版输出。这套系统把其中最机械的部分串成了一条流水线：

1. 在检索页输入关键词（支持 arXiv 字段语法与年份区间），拿到论文列表；
2. 勾选真正要读的论文，保存成一个**选择集**；
3. 后台任务批量下载 PDF 并抽取正文文本；
4. 用机器翻译或大模型把标题、摘要乃至全文译成中文，快速判断相关性；
5. 生成报告**目录**，逐节或一键生成**章节正文**，在网页里直接编辑；
6. 导出成 Markdown、Word 或 PDF 交稿。

系统默认面向本地单机使用（前后端都在 `127.0.0.1`），但代码按可分层的 Web 服务组织，改成服务器部署只需要调整环境变量与反向代理。

---

## 功能特性

### 1. 用户体系与数据隔离
- 注册 / 登录 / 获取当前用户（`/api/auth/*`）；
- 口令使用 **PBKDF2-HMAC-SHA256**（26 万次迭代 + 每用户随机盐）加盐哈希存储，数据库中不保存明文；
- 会话令牌为 **HMAC-SHA256 签名**的自包含 Token（`用户ID:用户名:过期时间:签名`），有效期 7 天，无需服务端会话表；
- 选择集、报告等数据均挂在用户下，接口通过 `Authorization: Bearer <token>` 鉴权。

### 2. arXiv 检索
- 支持简单关键词，也支持直接写 arXiv 查询语法（`all:`、`ti:`、`au:`、`cat:`、`AND`、`OR`）；
- 多关键词自动组装为 `OR` 组合，并支持 `year_from` / `year_to` 年份区间过滤；
- 排序支持 `relevance`（相关度）、`submittedDate`（投稿时间）、`lastUpdatedDate`（更新时间）；
- **服务端限流**：全局最小请求间隔 3 秒，避免触发 arXiv 的频率限制；
- **双域名回退**：`export.arxiv.org` 失败自动切换 `arxiv.org`，并带超时重试；
- **TTL 缓存**：检索结果内存缓存 10 分钟（最多 128 条），重复查询不再打网络；
- 错误按类型翻译成明确的状态码（429 频率限制 / 504 超时 / 502 上游不可用）。

### 3. 选择集管理
- 把勾选的论文保存为命名集合，可列出、查看、删除；
- 每个集合可查询其中每篇论文的**处理状态**（是否已下载、已解析、已翻译）。

### 4. PDF 下载与文本抽取
- 以**任务（Task）**为单位异步执行，支持 `创建 → 下载 → 抽取` 分步推进；
- 任务状态含 `status / step / progress / message`，前端轮询展示进度；
- 使用 `pdfminer.six` 抽取 PDF 正文，落盘为纯文本，供后续翻译与生成使用。

### 5. 中英翻译
- **双通道**：优先调用火山引擎机器翻译（快、便宜），失败自动降级到配置的大模型（OpenAI 兼容）；也可关闭降级直接暴露错误；
- 长文本按 `VOLC_TRANSLATE_MAX_CHARS` 分块，并用信号量控制 `VOLC_TRANSLATE_CONCURRENCY` 并发；
- 支持「只翻标题+摘要」的轻量速览模式，适合筛选阶段；
- 全文译文保存为 Markdown，可在线查看。

### 6. 报告生成与编辑
- 由选择集创建报告，生成**多级目录（章节树）**；
- 目录来源可选：内置模板，或让大模型依据论文集合生成；
- 章节正文支持**单节生成**与**一键生成全文**；
- 生成的正文是 Markdown，可在网页里直接编辑、保存；
- 支持章节的层级调整、重命名与删除。

### 7. 导出
- **Markdown**：按章节层级渲染为标题 + 正文；
- **Word（.docx）**：使用 `python-docx`，并把 Markdown 语法清洗为纯文本段落；
- **PDF**：用 Pillow 逐行排版渲染（自动换行、分页）。

### 8. 统计看板
- 汇总论文数、选择集数、报告数、任务进度等概览指标。

### 9. 无密钥也能跑通
未配置大模型 Key 时，目录使用内置模板、章节使用占位文本，整条「检索 → 选择 → 下载 → 生成 → 导出」的演示闭环依然完整可用。

---

## 技术栈

| 层次 | 选型 |
| --- | --- |
| 前端 | React 19 · TypeScript 5.9 · Vite 8 · 原生 CSS（无 UI 框架） |
| 后端 | FastAPI 0.118 · Uvicorn · Pydantic v2 / pydantic-settings |
| 数据层 | SQLAlchemy 2.0（全异步 ORM） · SQLite（`aiosqlite` 驱动） |
| 文献检索 | arXiv Atom API（`httpx` 异步请求 + 自建限流/缓存/重试） |
| 文档处理 | pdfminer.six（PDF 取文） · python-docx（Word 导出） · Pillow（PDF 渲染） |
| 大模型 | 任意 OpenAI 兼容接口（默认 DeepSeek），用于目录生成、章节撰写、翻译兜底 |
| 机器翻译 | 火山引擎翻译 API（`volcengine-python-sdk`） |
| 鉴权 | 标准库 `hashlib` / `hmac` 实现的 PBKDF2 口令哈希 + 签名 Token |

运行环境：**Python 3.11+**、**Node.js 18+**（开发时实测 Python 3.11.5 / Node 22.20.0）。

---

## 系统架构

```
┌────────────────────────────┐
│  浏览器（React SPA :5173）  │
│  检索 / 选择集 / 报告 / 导出 │
└─────────────┬──────────────┘
              │  /api/**（Vite 开发代理转发）
              ▼
┌────────────────────────────────────────────────────┐
│              FastAPI 后端（:8010）                  │
│                                                    │
│  api/arxiv    api/papers   api/tasks               │
│  api/reports  api/translate api/export  api/stats  │
│  auth（Bearer Token 鉴权 / 口令哈希）               │
├────────────────────────────────────────────────────┤
│  services/                                         │
│   arxiv_client + arxiv_cache + cache（限流/缓存）    │
│   downloader · pdf_extract · text_clean            │
│   llm（OpenAI 兼容）· translator（火山→LLM 降级）    │
│   exporter（md / docx / pdf）· storage（路径管理）   │
├────────────────────────────────────────────────────┤
│  SQLAlchemy 2.0 async  →  SQLite（backend/app.db）  │
└─────────────┬──────────────────────────────────────┘
              │
              ▼
   STORAGE_ROOT（默认 D:/survey2_storage）
     ├── papers/        下载的 PDF
     ├── text/          抽取的正文
     ├── translations/  中文译文（Markdown）
     └── reports/       导出的 md / docx / pdf
```

**一次典型请求的链路**：前端 `api.ts` 统一封装 `fetch` 并附带 Bearer Token → Vite 代理转发到 `127.0.0.1:8010` → FastAPI 路由做鉴权与参数校验 → `services/` 完成 arXiv 拉取 / LLM 调用 / 文件读写 → SQLAlchemy 异步会话读写 SQLite → 返回 JSON（文件类接口返回 `FileResponse`）。

**设计要点**

- **凭据只走环境变量**：`.env` 由 `pydantic-settings` 载入，`.env` 已在 `.gitignore` 中，不会进版本库；
- **缓存与并发**：arXiv 侧用进程内 TTL 缓存 + 全局锁限流；翻译侧用分块 + 信号量控制并发；
- **降级优先**：翻译失败降级到大模型，大模型不可用时报告生成退化为模板 + 占位文本，保证流程不中断。

---

## 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口、CORS、启动建表、/api/health
│   │   ├── settings.py          # 全部配置项（读 .env）
│   │   ├── db.py                # 异步引擎 / 会话 / 建表辅助
│   │   ├── models.py            # ORM：用户、论文、选择集、任务、报告、章节…
│   │   ├── schemas.py           # Pydantic 出入参模型
│   │   ├── auth.py              # 口令哈希、Token 签发校验、当前用户依赖
│   │   ├── api/                 # 路由层：arxiv / papers / tasks / reports
│   │   │                        #          translate / export / stats / auth
│   │   └── services/            # 业务层：arxiv 客户端与缓存、下载、PDF 取文、
│   │                            #          文本清洗、LLM、翻译、导出、存储路径
│   └── run_dev.py               # 后端快速启动脚本（backend 目录下执行）
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # 页面装配与路由切换
│   │   ├── api.ts               # 后端接口封装（统一鉴权与错误处理）
│   │   ├── types.ts             # 前端类型定义
│   │   ├── components/          # AuthPage / SearchPage / SelectionSetPage
│   │   │                        # ReportPage / Navbar / FileViewerModal
│   │   ├── hooks/               # useAuth / useSelectionSets / useReportEditor…
│   │   └── reportUtils.ts       # 报告结构处理辅助
│   ├── vite.config.ts           # 开发代理：/api → 127.0.0.1:8010
│   └── package.json
├── requirements.txt             # 后端依赖（含版本锁定）
├── .env.example                 # 配置模板（复制为 .env 后填写）
├── .gitignore
└── README.md
```

> `data/`、`backend/app.db*`、`frontend/dist/` 均为**运行期产物**，已在 `.gitignore` 中排除。

---

## 快速开始

### 0. 环境要求

| 依赖 | 版本 |
| --- | --- |
| Python | 3.11 及以上 |
| Node.js | 18 及以上（推荐 20+） |
| 操作系统 | Windows / macOS / Linux（PDF 导出的中文字体回退逻辑对 Windows 更友好） |

### 1. 克隆仓库

```bash
git clone https://github.com/yaoshunyu397/Automated-Research-Report-Generation-System.git
cd Automated-Research-Report-Generation-System
```

### 2. 启动后端（FastAPI）

在**项目根目录**执行：

```bash
# 创建并激活虚拟环境（可选但推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 安装依赖
python -m pip install -r requirements.txt

# 启动服务（端口 8010）
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010 --reload
```

健康检查：<http://127.0.0.1:8010/api/health> —— 返回数据库、存储目录、arXiv、大模型、翻译各通道的可用状态。

> 也可以 `cd backend` 后执行 `python run_dev.py`，该脚本以 `reload=True` 启动并监听 **8000** 端口；若用这种方式，请同步把 `frontend/vite.config.ts` 里的代理目标改成 `http://127.0.0.1:8000`。

### 3. 启动前端（Vite + React）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 <http://127.0.0.1:5173>（端口被占用时 Vite 会自动顺延），先**注册一个账号**再登录使用。

开发服务器已配置代理：所有 `/api` 开头的请求转发到 `http://127.0.0.1:8010`，因此不存在跨域问题。

### 4. 配置大模型（可选）

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

编辑 `.env`，填入 `LLM_API_KEY`。**不配置也能用**：目录走内置模板、章节走占位文本，流程照样跑通。

### 5. 生产构建（可选）

```bash
cd frontend
npm run build      # 产出 frontend/dist/
```

> 后端目前不托管前端静态资源，生产部署时请用 Nginx 等把 `dist/` 与 `/api` 分别指向静态目录和后端端口。

---

## 配置说明

所有配置通过项目根目录的 `.env` 注入（`backend/app/settings.py` 定义并带默认值）。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `SurveyGen` | 应用名，显示在 API 文档标题 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./backend/app.db` | 数据库连接串，注意相对路径基于**启动时的工作目录** |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 允许的前端来源，逗号分隔 |
| `SECRET_KEY` | `survey2-local-dev-secret` | Token 签名密钥，**正式部署必须改成随机长字符串** |
| `STORAGE_ROOT` | `D:/survey2_storage` | 运行期文件根目录（PDF / 文本 / 译文 / 报告），建议指向项目外的独立目录 |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容接口地址（`.env.example` 预设 DeepSeek） |
| `LLM_API_KEY` | 空 | 大模型密钥；为空时报告生成退化为模板 + 占位文本 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `ARXIV_PROXY` | 空 | arXiv 请求代理，形如 `http://127.0.0.1:7890`；国内网络环境建议配置 |
| `ARXIV_TIMEOUT_SECONDS` | `15.0` | arXiv 请求超时（秒） |
| `TRANSLATION_PROVIDER` | `volcengine` | 翻译通道：`volcengine` 或走大模型 |
| `TRANSLATION_FALLBACK_TO_LLM` | `true` | 火山翻译失败时是否自动降级到大模型 |
| `VOLC_ACCESS_KEY_ID` | 空 | 火山引擎 AccessKey ID |
| `VOLC_SECRET_ACCESS_KEY` | 空 | 火山引擎 Secret Access Key |
| `VOLC_REGION` | `cn-north-1` | 火山引擎区域 |
| `VOLC_TRANSLATE_SOURCE_LANGUAGE` | `en` | 源语言 |
| `VOLC_TRANSLATE_TARGET_LANGUAGE` | `zh` | 目标语言 |
| `VOLC_TRANSLATE_MAX_CHARS` | `4000` | 单次翻译请求的最大字符数（同时决定长文分块大小） |
| `VOLC_TRANSLATE_CONCURRENCY` | `5` | 长文分块翻译的并发上限 |

> ⚠️ **安全提醒**：`.env` 内含真实密钥，已被 `.gitignore` 排除，**不要**强制提交或贴进 Issue。若密钥曾经外泄，请到对应平台立即轮换。

---

## API 一览

除注册/登录与健康检查外，其余接口均需请求头 `Authorization: Bearer <token>`。

### 系统

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查：数据库、存储目录、arXiv、LLM、翻译通道状态 |

### 认证 `/api/auth`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册并直接返回 Token |
| POST | `/api/auth/login` | 登录获取 Token |
| GET | `/api/auth/me` | 获取当前登录用户 |

### 检索 `/api/arxiv`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/arxiv/search` | 关键词检索。参数：`q`（必填）、`max_results`(1–100)、`start`、`sort_by`、`year_from`、`year_to`、`any_keywords`（逗号分隔的 OR 关键词） |

### 论文与选择集 `/api/papers`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/papers/select` | 把选中的论文保存为选择集 |
| GET | `/api/papers/selection_sets` | 列出当前用户的选择集 |
| GET | `/api/papers/selection_set/{id}` | 查看选择集详情 |
| DELETE | `/api/papers/selection_set/{id}` | 删除选择集 |
| GET | `/api/papers/selection_set/{id}/statuses` | 查询集合内各论文的下载/解析/翻译状态 |
| GET | `/api/papers/{arxiv_id}/pdf` | 下载该论文 PDF |
| GET | `/api/papers/{arxiv_id}/translation_file` | 获取该论文的译文 Markdown |

### 任务 `/api/tasks`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/tasks/create` | 为选择集创建处理任务 |
| GET | `/api/tasks/{task_id}` | 查询任务状态与进度 |
| POST | `/api/tasks/{task_id}/download` | 执行「下载 PDF」步骤 |
| POST | `/api/tasks/{task_id}/extract` | 执行「抽取文本」步骤 |

### 报告 `/api/reports`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/reports/create` | 由选择集创建报告 |
| GET | `/api/reports/selection_set/{id}` | 列出某选择集下的报告 |
| DELETE | `/api/reports/{report_id}` | 删除报告 |
| GET | `/api/reports/{report_id}/outline/templates` | 获取内置目录模板 |
| POST | `/api/reports/{report_id}/outline/apply` | 套用指定目录模板 |
| POST | `/api/reports/{report_id}/outline/generate` | 由大模型生成目录 |
| GET | `/api/reports/{report_id}/sections` | 获取章节树 |
| PUT | `/api/reports/{report_id}/sections/{section_id}` | 保存章节内容（编辑） |
| POST | `/api/reports/{report_id}/sections/{section_id}/generate` | 生成单节正文 |
| POST | `/api/reports/{report_id}/generate_all` | 一键生成全部章节 |

### 翻译 `/api/translate`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/translate/summaries` | 批量翻译标题 + 摘要（筛选速览） |
| POST | `/api/translate/selection_set/{id}` | 翻译整个选择集的论文全文 |
| GET | `/api/translate/{arxiv_id}` | 查询单篇论文的翻译结果 |

### 导出 `/api/reports`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/reports/{report_id}/export?format=md\|docx\|pdf` | 生成导出文件 |
| GET | `/api/reports/{report_id}/export/download?format=md\|docx\|pdf` | 下载已生成的文件 |

### 统计 `/api/stats`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/stats/overview` | 论文、选择集、报告、任务等总览统计 |

> 后端启动后可直接访问 <http://127.0.0.1:8010/docs> 查看 FastAPI 自动生成的交互式 API 文档。

---

## 数据存储

**数据库**：SQLite，默认 `backend/app.db`（由 `DATABASE_URL` 决定）。启动时自动建表，无需手动迁移。主要数据表：

`users`（用户）、`papers`（论文元数据）、`selection_sets` / `selections`（选择集与集合成员）、`paper_assets`（PDF / 文本路径）、`paper_translations`（标题摘要译文）、`tasks`（下载解析任务）、`reports` / `report_sections`（报告与章节树）。

**文件**：由 `STORAGE_ROOT` 决定（默认 `D:/survey2_storage`，可用 `.env` 覆盖）：

| 子目录 | 内容 |
| --- | --- |
| `papers/` | 下载的论文 PDF，按 `{arxiv_id}.pdf` 命名 |
| `text/` | pdfminer 抽取的正文，`{arxiv_id}.txt` |
| `translations/` | 中文译文，`{arxiv_id}.md` |
| `reports/` | 导出的 `report_{id}.md / .docx / .pdf` |

> 项目根目录下的 `data/` 是早期版本遗留的本地数据目录，当前代码以 `STORAGE_ROOT` 为准，两者互不影响。

---

## 常见问题

**Q：没有大模型 API Key 能跑吗？**
可以。系统做了降级：目录用内置模板，章节生成写入占位文本，检索、下载、解析、导出等功能全部正常，适合先跑通流程再接入模型。

**Q：arXiv 检索超时或报 502 / 504 / 429？**
- 429：触发 arXiv 频率限制 —— 客户端已内置 3 秒最小间隔与 10 分钟缓存，稍等片刻重试即可；
- 502 / 504：上游不可达或超时。国内网络建议在 `.env` 中配置 `ARXIV_PROXY`，或适当调大 `ARXIV_TIMEOUT_SECONDS`。

**Q：翻译报「火山翻译 AccessKey 未配置」？**
说明 `TRANSLATION_PROVIDER=volcengine` 但没填火山密钥。要么补齐 `VOLC_ACCESS_KEY_ID` / `VOLC_SECRET_ACCESS_KEY`，要么把 `TRANSLATION_PROVIDER` 改为非 `volcengine` 的值，让翻译走大模型（此时必须有 `LLM_API_KEY`）。

**Q：Windows 上 `npm install` 报缓存目录权限错误？**
把缓存指到项目内目录再执行：

```bash
cmd /c "set npm_config_cache=%CD%\.npm-cache&& npm run dev"
```

**Q：导出的 PDF 里中文变成方块？**
PDF 导出使用 Pillow 逐行绘制，字体优先取 Windows 的 `C:\Windows\Fonts\msyhl.ttc`，取不到则回退到 Pillow 默认字体（不支持中文）。在 macOS / Linux 上运行请自行改用系统中文字体路径。

**Q：报告导出接口报 `No module named 'PIL'`？**
补装图像渲染依赖：`python -m pip install Pillow`（已在 `requirements.txt` 中声明）。

**Q：端口被占用？**
后端换端口时记得同步修改 `frontend/vite.config.ts` 的代理目标；前端端口被占用时 Vite 会自动顺延，无需处理。

**Q：为什么启动后 `data/` 目录是空的？**
因为文件默认写到 `STORAGE_ROOT`（默认 `D:/survey2_storage`）。检查 `.env` 中该变量的取值即可。

---

## 免责声明

- 本系统仅用于**个人学习与科研辅助**。通过 arXiv 获取的论文 PDF、正文与译文，其**版权归原作者及出版方所有**，请遵守 arXiv 的使用条款与所在机构的许可规定，不要用于再分发或商业用途。
- 系统会调用第三方服务（arXiv、大模型接口、火山引擎翻译），产生的内容与费用由使用者自行承担；请自行确认所用模型服务的数据合规要求，避免上传涉密或敏感材料。
- 大模型生成的目录与章节内容**可能存在事实错误或引用偏差**，务必人工核对后再使用。

## 许可证

本项目暂未指定开源许可证。如需转载、二次开发或商用，请先联系作者获取授权。

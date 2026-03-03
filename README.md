# DailyPaper

每日 AI 论文精选系统 — 自动抓取、评分、分析，每天早上 **7:00 北京时间**推送。

## 功能

每天自动执行完整流水线：

1. 从 **arXiv** 和 **HuggingFace Daily Papers** 抓取候选论文
2. 用 Claude AI 对每篇论文进行 6 维度评分，筛选出 Top 3
3. 用 Claude AI 生成**双语（中文 + 英文）**结构化解读（每篇 ≤ 5 分钟可读）
4. 自动过滤**已推送过的论文**（去重，不重复推送）
5. 发布至 **GitHub Pages** 静态网站（完整内容）
6. 发送 **Gmail 摘要邮件**（仅核心贡献 + 网页链接）

## 关注分类（共 12 篇/天）

| 分类 | 类型 | 篇数 |
|------|------|------|
| LLM 安全 / LLM Security | 最值得读 | 3 |
| 具身智能安全 / Embodied Intelligence Security | 最值得读 | 3 |
| LLM 发展动态 / LLM Development Trends | 最重要 | 3 |
| 具身智能发展动态 / Embodied Intelligence Development Trends | 最重要 | 3 |

## 每篇论文包含

- **一句话核心** (TL;DR)
- 科研问题
- 先前工作为何不够
- 解决方案
- 主要结论
- 值得关注的讨论点

## 快速开始

### 1. Fork 本仓库

### 2. 启用 GitHub Pages

Settings → Pages → Source: `main` branch → Folder: `/docs`

### 3. 配置 GitHub Secrets

Settings → Secrets and variables → Actions → New repository secret：

| Secret | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥（[获取](https://console.anthropic.com/)）|
| `GMAIL_USER` | Gmail 发件地址（如 `you@gmail.com`）|
| `GMAIL_APP_PASSWORD` | Gmail 应用专用密码（非登录密码）|
| `EMAIL_RECIPIENTS` | 收件人（逗号分隔，如 `a@x.com,b@x.com`）|
| `SITE_BASE_URL` | GitHub Pages 地址（如 `https://username.github.io/dailyPaper`）|

> **Gmail 应用密码：** Google 账号 → 安全 → 两步验证 → 应用专用密码

### 4. 手动触发测试

GitHub → Actions → **Daily Paper Digest** → **Run workflow**

### 5. 自动调度

每天 **07:00 北京时间**（23:00 UTC）自动运行。

## 去重机制

已推送的论文 ID 存储在 `data/seen_papers.json`，格式：

```json
{"2401.12345":"2026-03-03","2402.67890":"2026-03-04"}
```

- **O(1) 查询**：Python dict 键，不管多少条记录查询时间不变
- **紧凑存储**：无缩进 JSON，5 年约 500 KB
- **审计友好**：记录每篇论文首次推送日期
- **自动提交**：每次运行后 `data/seen_papers.json` 自动 commit 到仓库

## 本地开发

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
python scripts/main.py
```

运行测试：

```bash
python -m pytest tests/ -v
```

## 费用估算

| 环节 | 模型 | 每日费用 |
|------|------|---------|
| 论文评分（120篇候选）| Claude Haiku | ~$0.01 |
| 内容生成（12篇）| Claude Sonnet | ~$0.18 |
| **合计** | | **~$0.19/天（≈ ¥1.4）** |

## 项目结构

```
dailyPaper/
├── .github/workflows/daily.yml   # 每日 7AM 北京时间触发
├── scripts/
│   ├── main.py                   # 主流程编排
│   ├── fetch_papers.py           # arXiv + HuggingFace 抓取
│   ├── score_papers.py           # Claude Haiku 多维度评分
│   ├── generate_analysis.py      # Claude Sonnet 双语解读生成
│   ├── seen_papers.py            # 去重模块
│   ├── render_html.py            # Jinja2 HTML 渲染
│   ├── send_email.py             # Gmail SMTP 发送
│   └── models.py                 # 数据模型
├── templates/                    # Jinja2 模板
├── docs/                         # GitHub Pages 输出
├── data/seen_papers.json         # 已推送论文 ID（自动维护）
├── config.yaml                   # 关键词、模型、邮件配置
└── tests/                        # 26 个单元测试
```

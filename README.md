# DailyPaper — AI 驱动的每日论文精选

每天自动从 arXiv、HuggingFace Daily Papers 和 Semantic Scholar 抓取论文，用 Claude AI 筛选出最值得读的内容，生成双语深度解读，并通过 GitHub Pages 网站和 Gmail 邮件推送。

**关注方向：** LLM 安全 · 具身智能安全 · LLM 发展动态 · 具身智能发展动态

---

## 目录

- [功能概览](#功能概览)
- [数据流程](#数据流程)
- [论文来源与筛选策略](#论文来源与筛选策略)
- [评分机制](#评分机制)
- [内容生成](#内容生成)
- [输出形式](#输出形式)
- [项目结构](#项目结构)
- [部署配置](#部署配置)
- [成本估算](#成本估算)

---

## 功能概览

| 功能 | 说明 |
|------|------|
| 每日自动触发 | GitHub Actions 每天 07:00（北京时间）定时运行 |
| 多源抓取 | Semantic Scholar（会议论文优先）+ arXiv + HuggingFace |
| AI 评分筛选 | Claude Haiku 对每篇论文进行 6 维度打分，每分类取最优 3 篇 |
| 双语深度解读 | Claude Sonnet 生成中英文对照的结构化解读，每篇约 3-5 分钟可读完 |
| 静态网站 | GitHub Pages 托管完整内容，含历史归档 |
| 邮件推送 | Gmail SMTP 发送每日摘要邮件 |
| 去重机制 | 已推送的论文不会重复出现 |

---

## 数据流程

```
每天 07:00（北京时间）
         │
         ▼
  GitHub Actions 触发
         │
         ▼
┌─────────────────────────────────────┐
│         fetch_papers.py             │
│  ┌──────────────────────────────┐   │
│  │ Semantic Scholar API         │   │  ← 优先：近两年 top conference 录取论文
│  │ (按 semantic_query 搜索)     │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ arXiv API (过去 48h)         │   │  ← 补充：近期新论文
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ HuggingFace Daily Papers     │   │  ← 补充：社区热门（带点赞数）
│  └──────────────────────────────┘   │
│         合并去重 + 过滤已推送         │
└─────────────────────────────────────┘
         │ 每分类最多 50 篇候选
         ▼
┌─────────────────────────────────────┐
│         score_papers.py             │
│  Claude Haiku 6 维度评分             │
│  + 会议/年份加成 / arXiv 惩罚         │
│  + 最低分过滤（≥ 6.0 才发布）         │
│  → 每分类取评分最高的 3 篇             │
└─────────────────────────────────────┘
         │ 共最多 12 篇
         ▼
┌─────────────────────────────────────┐
│       generate_analysis.py          │
│  Claude Sonnet 生成结构化双语解读     │
│  （6 个板块，中英文对照）             │
└─────────────────────────────────────┘
         │
         ▼
┌──────────────┐    ┌──────────────┐
│ render_html  │    │ send_email   │
│ GitHub Pages │    │ Gmail SMTP   │
└──────────────┘    └──────────────┘
         │
         ▼
  git commit + push → GitHub Pages 自动部署
```

---

## 论文来源与筛选策略

### 三个来源，按优先级排序

**1. Semantic Scholar（最高优先级）**

从 S2 学术 API 搜索近两年（当前年份 - 2 至今）各大顶会录取论文。年份窗口随当前时间自动滑动，例如 2026 年范围为 2024-2026，2027 年自动变为 2025-2027。

支持的会议（26 个）：
> NeurIPS · ICML · ICLR · CVPR · ICCV · ECCV · AAAI · IJCAI · ACL · EMNLP · NAACL · COLING · CCS · USENIX Security · IEEE S&P · NDSS · RAID · AsiaCCS · ICRA · IROS · CoRL · RSS · HUMANOIDS · WACV · SIGGRAPH

- 自动处理 S2 全称与缩写的对应（如 "Advances in Neural Information Processing Systems" → NeurIPS）
- 过滤掉 workshop 论文
- 同名会议同年的论文优先展示更新年份（2026 > 2025 > 2024）

**2. arXiv（补充来源）**

按分类关键词搜索过去 48 小时内的新论文。若候选数量不足，自动扩展至 7 天回溯。

**3. HuggingFace Daily Papers（热度信号）**

抓取当天 HF 每日精选论文及其点赞数，作为社区热度信号参与评分。

### 四个关注分类

| 分类 | 关注重点 |
|------|---------|
| **LLM 安全** | Jailbreak、提示注入、对抗攻击、后门攻击、红队测试 |
| **具身智能安全** | 决策层攻击（VLA/世界模型）> 感知层攻击（LiDAR/点云）> 物理层 |
| **LLM 发展动态** | 推理能力、多模态、对齐、Chain-of-Thought、基础模型 |
| **具身智能发展动态** | VLA、世界模型、LLM 机器人规划、灵巧操作、3D 场景理解 |

具身智能相关分类特别关注**决策层**（VLA、世界模型、神经网络大脑），其次是**感知层**（3D 场景、SLAM），物理层论文仅在极其优秀时才选入。

---

## 评分机制

### 6 维度评分（Claude Haiku 执行）

| 维度 | 权重 | 说明 |
|------|------|------|
| 话题重要性 | 25% | 问题是否值得讨论 |
| 趋势契合度 | 20% | 是否符合当前前沿方向 |
| 社区关注度 | 15% | HF 点赞数信号 |
| 实际意义 | 20% | 是否有具体应用价值 |
| 作者/机构声望 | 10% | MIT、CMU、Google DeepMind 等 |
| 论文完整性 | 10% | 实验是否扎实 |

### 会议/来源加分/扣分

| 来源类型 | 调整分值 |
|---------|---------|
| 顶会录取（当年） | +2.0 |
| 顶会录取（去年） | +1.7 |
| 顶会录取（两年前）| +1.5 |
| HF 点赞 ≥ 20 | +1.0 |
| HF 点赞 ≥ 10 | +0.3 |
| 普通 arXiv（无会议、无热度）| -1.5 |

**最低分阈值：** 综合得分低于 6.0 的论文不会被发布（宁缺勿滥）。

同时，每篇论文的评分结果包含中英文双语的优缺点分析（pros/cons）。

---

## 内容生成

每篇选中的论文由 Claude Sonnet 生成以下 6 个结构化板块，中英文对照，每篇约 3-5 分钟可读完：

| 板块 | 内容 |
|------|------|
| **核心贡献（TL;DR）** | 一句话概括论文核心贡献 |
| **科研问题** | 论文试图解决什么问题，为何值得解决 |
| **先前工作为何不够** | 已有方法的核心局限 |
| **解决方案** | 本文提出方法的核心思路和主要贡献 |
| **主要结论** | 实验结果和关键发现（尽量有数字） |
| **值得关注的讨论点** | 3 个值得进一步思考的方向或问题 |

内容生成使用 Claude 的 **Tool Use** 功能强制输出结构化 JSON，避免解析失败。

---

## 输出形式

### GitHub Pages 网站

每日生成静态网页 `docs/YYYY-MM-DD/index.html`，展示当天所有论文的完整双语解读。首页 `docs/index.html` 提供历史归档导航，按日期折叠展示每日摘要。

网页特性：
- 响应式布局（PC + 移动端）
- 分类可折叠，论文各板块可独立折叠/展开
- 展示评分、发表日期、会议来源、HF 热度等元信息
- 提供原文链接（arXiv / HuggingFace / Semantic Scholar）

### Gmail 邮件推送

每日发送一封 HTML 格式邮件，包含每篇论文的标题（双语）+ 核心贡献一句话摘要 + 完整网页链接。邮件为纯摘要，详细内容在网站查看。

---

## 项目结构

```
dailyPaper/
├── .github/
│   └── workflows/
│       └── daily.yml          # GitHub Actions 每日定时任务
├── scripts/
│   ├── main.py                # 主流程编排
│   ├── fetch_papers.py        # 论文抓取（S2 + arXiv + HF）
│   ├── score_papers.py        # 多维度评分与筛选
│   ├── generate_analysis.py   # 结构化双语解读生成
│   ├── render_html.py         # Jinja2 HTML 渲染
│   ├── send_email.py          # Gmail 邮件发送
│   ├── seen_papers.py         # 已推送论文去重
│   └── models.py              # 数据模型（Paper / ScoredPaper / PaperAnalysis）
├── templates/
│   ├── daily.html.j2          # 每日页面模板
│   ├── index.html.j2          # 首页/归档模板
│   └── email.html.j2          # 邮件 HTML 模板
├── docs/                      # GitHub Pages 根目录（自动生成）
│   ├── index.html
│   └── YYYY-MM-DD/
│       ├── index.html
│       └── meta.json          # 供首页归档读取的轻量元数据
├── data/
│   └── seen_papers.json       # 已推送论文 ID 记录（去重用）
├── tests/                     # 单元测试
├── config.yaml                # 核心配置（分类、关键词、会议列表等）
└── requirements.txt
```

---

## 部署配置

### GitHub Secrets（必填）

| Secret | 用途 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 |
| `GMAIL_USER` | Gmail 发件账号（如 `xxx@gmail.com`） |
| `GMAIL_APP_PASSWORD` | Gmail 应用专用密码（非登录密码） |
| `EMAIL_RECIPIENTS` | 收件人邮箱，逗号分隔 |
| `SITE_BASE_URL` | GitHub Pages 地址（如 `https://username.github.io/DailyReading`） |

### 触发方式

- **自动触发：** 每天 UTC 23:00（北京时间 07:00）
- **手动触发：** 在 GitHub Actions 页面点击 "Run workflow"

### 本地运行

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
python -m scripts.main
```

### config.yaml 主要配置项

```yaml
schedule:
  lookback_hours: 48           # arXiv 回溯时间窗口
  s2_lookback_years: 2         # S2 会议论文年份窗口（自动随当前年份滑动）

llm:
  scoring_model: claude-haiku-4-5-20251001   # 评分用，速度快、成本低
  analysis_model: claude-sonnet-4-6          # 解读生成用，质量高
  max_candidates_per_category: 50            # 每分类最多处理的候选论文数

categories:
  llm_security:
    name_zh: "LLM 安全"
    papers_per_day: 3
    keywords: [...]
    semantic_query: "..."      # S2 搜索语句
    scoring_note: "..."        # 发给 Haiku 的额外评分指导
```

---

## 成本估算

| 步骤 | 模型 | 估算用量 | 日费用 |
|------|------|---------|--------|
| 论文评分 | claude-haiku-4-5 | ~200 篇 × ~800 tokens | ~$0.02 |
| 内容生成 | claude-sonnet-4-6 | ~12 篇 × ~4000 tokens | ~$0.18 |
| **合计** | | | **~$0.20/天（约 ¥1.5/天）** |

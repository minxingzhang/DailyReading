# DailyPaper — 每日论文精选

每天自动从 arXiv、HuggingFace 和顶会论文库中筛选出最值得读的论文，用 Claude 生成双语结构化解读，发布到 GitHub Pages 并通过邮件推送。

---

## 目标

覆盖 4 个研究方向，每方向每天精选 3 篇，共 12 篇：

| 方向 | 类型 | 关注重点 |
|------|------|------|
| LLM 安全 | 最值得读 | Jailbreak、prompt injection、对抗攻击、后门 |
| 具身智能安全 | 最值得读 | 决策层（LLM 被攻击）> 感知层（传感器/CV 攻击）> 物理层 |
| LLM 发展动态 | 最重要 | 推理、多模态、对齐、基础模型 |
| 具身智能发展动态 | 最重要 | 决策层（VLA/世界模型/LLM 控制）> 感知层 > 物理层 |

---

## 流水线

```
GitHub Actions (每天 UTC 23:00 = 北京时间 07:00)
    │
    ▼
Step 1: 抓论文 (fetch_papers.py)
    │
    ▼
Step 2: 评分筛选 (score_papers.py)
    │
    ▼
Step 3: 生成解读 (generate_analysis.py)
    │
    ├──▶ Step 4: 渲染网页 (render_html.py) ──▶ git push ──▶ GitHub Pages
    │
    └──▶ Step 5: 发送邮件 (send_email.py)
```

---

## 各步骤详解

### Step 1 — 抓论文

从三个来源抓取候选论文，每个分类最多取 50 篇候选：

**Semantic Scholar（顶会论文，优先级最高）**
- 用关键词搜索 Semantic Scholar API
- 只保留近 2 年内被顶会收录的论文（NeurIPS / ICML / CVPR / ICRA / CCS / USENIX Security 等共 30+ 会议）
- 排除 Workshop 论文
- 有速率限制，请求间加 3s 延迟，遇到 429 自动重试（15s / 30s / 60s）

**arXiv（近 48 小时新论文）**
- 用分类关键词组合搜索（如 `"jailbreak" AND (cat:cs.CR OR cat:cs.AI)`）
- 按发布时间降序，截取 48 小时内的结果

**HuggingFace Daily Papers（社区热度）**
- 抓取 huggingface.co/papers 当天全部论文及点赞数
- 点赞数作为社区关注度信号参与评分

三个来源合并去重（以 arxiv_id 为主键），同一篇论文优先保留顶会来源版本。

---

### Step 2 — 评分筛选

用 **Claude Haiku** 对每篇候选论文打分（0–10），再结合来源加权，选出 Top 3。

**LLM 评分维度（各有权重）：**
- 话题重要性：问题是否真正值得研究
- 趋势契合度：是否符合当前前沿方向
- 社区关注度：HF 点赞数归一化分值
- 实际意义：是否有具体应用价值
- 作者/机构声望：知名研究组加权
- 论文完整性：结构严谨、有实验支撑

**来源加权（在 LLM 分基础上叠加）：**
- 顶会论文（当年）：+2.0
- 顶会论文（去年）：+1.7
- 顶会论文（前年）：+1.5
- HF 点赞 ≥ 20：+1.0
- HF 点赞 ≥ 10：+0.3
- 纯 arXiv 无顶会背书：-1.5

**质量门槛：**
- 综合分 ≥ 6.0 才进入最终列表（宁缺勿滥）
- 若当天该分类没有任何论文达到 6.0，取最高分的 1 篇作为兜底，并在页面上标注黄色警告

---

### Step 3 — 生成解读

用 **Claude Sonnet** 为每篇选中的论文生成 6 个结构化板块，中英文对照：

| 板块 | 内容 |
|------|------|
| 一句话核心 (TL;DR) | 一句话说清核心贡献 |
| 科研问题 | 解决什么问题，为什么值得解决 |
| 先前工作局限 | 已有方法的关键痛点 |
| 解决方案 | 本文方法的核心思路 |
| 主要结论 | 关键实验结果（尽量用数字） |
| 讨论点 | 2–3 个值得进一步思考的方向 |

每篇解读控制在 5 分钟可读完，中文 ≤ 600 字。

---

### Step 4 — 渲染网页

用 **Jinja2** 将生成的内容渲染成静态 HTML，存入 `docs/` 目录：

```
docs/
├── index.html              # 重定向到最新日期
├── YYYY-MM-DD/
│   └── index.html          # 当日汇总页（4 个分类 × 3 篇）
└── archive/
    └── index.html          # 历史日期列表
```

渲染完成后 `git push`，GitHub Pages 自动部署。

---

### Step 5 — 发送邮件

通过 Gmail SMTP 发送当日摘要邮件，每篇论文仅包含：
- 标题（中英双语）
- 作者 & 机构
- 2–3 句中文摘要
- 网站完整版链接

---

## 项目结构

```
dailyPaper/
├── .github/workflows/daily.yml   # GitHub Actions 定时任务
├── scripts/
│   ├── main.py                   # 主流程：串联所有步骤
│   ├── fetch_papers.py           # Step 1：抓论文
│   ├── score_papers.py           # Step 2：评分筛选
│   ├── generate_analysis.py      # Step 3：生成解读
│   ├── render_html.py            # Step 4：渲染网页
│   ├── send_email.py             # Step 5：发送邮件
│   └── models.py                 # 数据模型定义
├── templates/
│   ├── daily.html.j2             # 每日网页模板
│   ├── index.html.j2             # 首页模板
│   ├── archive.html.j2           # 归档页模板
│   └── email.html.j2             # 邮件模板
├── docs/                         # GitHub Pages 根目录（自动生成）
├── data/
│   └── seen_papers.json          # 已推送论文记录（跨分类去重）
└── config.yaml                   # 关键词、分类、模型等配置
```

---

## 部署配置

**GitHub Secrets（必填）：**

| Secret | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 |
| `GMAIL_USER` | Gmail 发件账号 |
| `GMAIL_APP_PASSWORD` | Gmail 应用专用密码 |
| `EMAIL_RECIPIENTS` | 收件人列表（逗号分隔） |

**GitHub Pages：** 在仓库设置中将 Source 设为 `docs/` 目录。

**手动触发：** GitHub Actions 支持 `workflow_dispatch`，可在 Actions 页面手动运行。

---

## 成本估算

每日约 **$0.19**（约 ¥1.4）：
- 评分（Claude Haiku）：~120 篇候选 × ~800 tokens ≈ $0.01
- 解读（Claude Sonnet）：~12 篇 × ~4000 tokens ≈ $0.18

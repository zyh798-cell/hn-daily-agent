# HN Daily Agent｜每日 AI 技术简报

一个用于练习 Python、公开 API、大模型 API 与定时自动化的个人项目。脚本从 Hacker News 官方 Firebase API 获取热门文章，基于关键词初筛 AI 相关内容，按社区热度选出最多 10 条，并输出 Markdown 简报和 JSON 数据。

> 当前版本是“自动化工作流 + 可选 LLM 摘要”，不是具备自主规划能力的通用 Agent。关键词筛选会有漏判/误判，LLM 摘要也需要人工核对。

## 功能

- 从 Hacker News 官方 Firebase API 获取热门条目。
- 根据 AI / LLM / Agent 等关键词进行初步筛选。
- 按 points 和发布时间排序，默认保留 10 条。
- 可选调用 OpenAI 兼容的 Chat Completions API，生成中文标题、摘要、关注理由和难度。
- 即使不配置模型 API，也能生成基于标题与社区数据的简报。
- 输出 `output/digest-YYYY-MM-DD.md` 和 `.json`。
- GitHub Actions 每天北京时间 09:00 自动运行，并把生成文件提交到仓库；也支持手动触发。

## 目录结构

```text
hn-daily-agent/
├── .github/
│   └── workflows/
│       └── daily-digest.yml
├── tests/
│   └── test_main.py
├── .env.example
├── .gitignore
├── main.py
├── requirements.txt
└── README.md
```

## 本地运行

需要 Python 3.10 或更高版本。当前脚本只使用 Python 标准库，不需要安装第三方依赖。

```bash
git clone https://github.com/YOUR-USERNAME/hn-daily-agent.git
cd hn-daily-agent
python main.py
```

运行成功后检查 `output/` 文件夹中的 Markdown 和 JSON 文件。

### 启用大模型摘要（可选）

1. 复制 `.env.example` 为 `.env`。
2. 在本地终端中设置环境变量。脚本不会自动读取 `.env` 文件，因此可在终端手动导出变量，或使用你熟悉的环境变量管理方式。
3. 设置：
   - `LLM_API_KEY`：模型服务 API Key。
   - `LLM_BASE_URL`：兼容 OpenAI Chat Completions 的 API 地址。
   - `LLM_MODEL`：服务商支持的模型名。

macOS / Linux 示例：

```bash
export LLM_API_KEY="你的API密钥"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"
python main.py
```

不同服务商对 `response_format` 等参数的支持不同；如果服务商不兼容，程序会输出警告并回退到不调用模型的简报生成方式。不要把 API Key 写入代码或提交到 GitHub。

## 配置 GitHub Actions 每日运行

1. 将整个项目上传到 GitHub 仓库，仓库名可用 `hn-daily-agent`。
2. 打开仓库 **Settings → Secrets and variables → Actions**。
3. 如需大模型摘要，在 **Secrets** 中新增 `LLM_API_KEY`，值为你的 API Key。没有 Key 也可以运行。
4. 如需指定模型，在 **Variables** 中新增 `LLM_BASE_URL` 和 `LLM_MODEL`。
5. 打开 **Actions** 标签页，启用工作流；进入 `Daily AI Digest`，点击 `Run workflow` 可以手动测试。
6. 检查 Actions 运行结果以及 `output/` 下是否新增简报。

工作流 cron 为 `0 1 * * *`，即每天 01:00 UTC（北京时间 09:00）。GitHub Actions 的定时任务可能延迟，不保证精确到分钟。仓库需要允许 GitHub Actions 写入内容；工作流已声明 `contents: write`，如果推送仍失败，请检查仓库 Actions 的 Workflow permissions 是否允许读写。

## 输出示例

Markdown 简报包含：
- 中文标题（启用模型时由模型生成；未启用时使用原始标题）
- 原始标题、points、评论数、难度
- 摘要与关注理由
- 原文链接和 Hacker News 讨论链接

JSON 用于后续做网页展示、数据分析或接入其他工作流。

## 当前限制与下一步

- 当前仅检查 Hacker News 热门列表中的有限条目，不是全站搜索。
- 关键词规则会漏掉未包含明显 AI 词汇的文章，也可能误选。
- 不下载或复制文章全文；模型只处理标题、链接、社区数据和 API 返回的短文本字段。
- 没有实现自动修复代码；异常会记录日志并在必要时以非零状态退出。
- GitHub Actions 是定时运行环境，不是 24/7 服务。
- 下一步可加入去重历史、来源分类、摘要质量评估、邮件/Telegram 推送、单元测试和更严格的模型输出校验。

## 技术栈

Python 标准库、Hacker News Firebase API、可选 OpenAI-compatible Chat Completions API、GitHub Actions、Markdown、JSON。

## 免责声明

这是个人学习与作品展示项目，不隶属于 Hacker News。请遵守各 API 服务的使用条款，并妥善管理模型 API 密钥。

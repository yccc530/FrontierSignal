# FrontierSignal

**English** | [简体中文](README.zh-CN.md)

[![CI](https://github.com/yccc530/FrontierSignal/actions/workflows/ci.yml/badge.svg)](https://github.com/yccc530/FrontierSignal/actions/workflows/ci.yml)

**A local AI intelligence workspace for individual technical researchers.**

Discover open-source projects gaining stars quickly, follow model releases and research papers, and organize technical news through search, bookmarks, and traceable source links.

The application interface and AI-generated titles and summaries currently use Simplified Chinese. Original source content and links are preserved. This English README covers setup and the main workflows; the detailed guides linked below are currently in Chinese.

[Screenshots](#screenshots) · [Quick Start](#quick-start) · [AI Summaries](#ai-summaries) · [Maintenance](#maintenance) · [Development](#development-and-project-documents) · [Translations](#translations)

## Screenshots

These screenshots were captured from the running desktop application on October 23, 2026, at 1440 × 1000. Articles and metrics come from data collected in that local installation; a fresh installation does not include them. Screenshots illustrate the main workflows, and some interface details may differ from the current version. Click an image to view it at full size.

**Technical recommendations:** review projects with recent growth, Chinese summaries, star activity, and recommendation reasons.

[![Technical recommendations with research preferences, section quotas, and growing projects](docs/images/workbench.png)](docs/images/workbench.png)

<details>
<summary>View projects, model news, article details, and source management</summary>

### Open-Source Projects

Switch between growth signals, new projects, and the complete project list. Filter by technical topic and distinguish recent star growth from total stars.

[![Open-source projects with observed star growth, growth rates, and filters](docs/images/projects.png)](docs/images/projects.png)

### Model News

Filter by content type, technical topic, and publisher. This example shows video models with Chinese summaries, task types, and original resource links.

[![Video model news with topic filters, Chinese summaries, and source links](docs/images/models.png)](docs/images/models.png)

### Article Details

Read summaries alongside declared modalities, licenses, and source dates. Missing release dates and incomplete model cards are explicitly identified.

[![Model details showing summaries, metadata, license declarations, and evidence limitations](docs/images/model-detail.png)](docs/images/model-detail.png)

### Source Management

Manage enabled sources, automatic collection, and intervals. Review successful runs, query coverage, and ongoing observations.

[![Source management with collection status, intervals, switches, and coverage monitoring](docs/images/sources.png)](docs/images/sources.png)

</details>

## What You Can Do

| Workflow                    | Capabilities                                                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Discover emerging projects  | Rank projects using observed star growth, velocity, and acceleration; distinguish growth signals, new projects, and the full archive       |
| Follow models and research  | Aggregate model cards, official blogs, and papers across language, image, video, audio, 3D, robotics, and other technical topics           |
| Read technical intelligence | Generate Chinese titles, summaries, categories, and importance scores with a configurable LLM while retaining originals and evidence links |
| Build a research library    | Search, filter, bookmark, and track read status across recommendations, projects, and articles                                             |
| Set research priorities     | Configure collection scope, research interests, recommendation counts, and topic allocation independently                                  |
| Inspect collection activity | Review task results, errors, source coverage, star history, and model calls                                                                |

**An LLM is optional for collection, search, and reading.** Configure one to generate Chinese analysis. Failed model calls leave the original records intact and can be retried individually.

## Data Sources

The application includes **21 source configurations, 27 publisher entries, and 30 technical topics**. It uses official APIs, public RSS/Atom feeds, and reviewed public announcement pages. The xAI news-page source is disabled by default because it currently rejects requests.

| Source                   | Collected information                                                                                                   |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| GitHub                   | AI project discovery, star changes, and releases, including dedicated release tracking for vLLM and LangChain           |
| Hacker News              | AI technical posts, points, comment counts, and bounded comment samples                                                 |
| arXiv                    | `cs.AI`, `cs.LG`, `cs.CL`, `cs.CV`, and focused engineering and scientific research queries                             |
| Hugging Face             | Models, datasets, model cards, and official blog posts, with priority tracking for official GLM and Meta model accounts |
| Official technical blogs | OpenAI, Google DeepMind, Google AI, NVIDIA, Anthropic, Cohere, Amazon, and ByteDance Seed                               |

Topics include LLMs, agents, training and inference, RAG, multimodal and coding models, OCR, image/video/audio generation, 3D/CAD, world models, robotics, vibe coding, MCP/skills, development tools, and AI for science.

To browse GLM or Meta, open **Articles (资讯库)**, select **Model news (模型资讯)**, and filter the publisher to **智谱 / Z.ai** or **Meta**. These accounts share the existing request budget; collection does not download model weights. Source coverage reports the latest successful scan and any collection errors for each priority account.

The publisher catalog also includes Kimi, MiniMax, StepFun, Baidu, Intern, Hunyuan, and NVIDIA model accounts. A grouped grid lets you filter teams, topics, and categories without scrolling through long dropdowns. Sort by time, importance, technical relevance, paper citations, or source-specific popularity. Citation counts come from exact arXiv lookups in OpenAlex; unavailable counts remain unknown, and observations link to their source. New papers may not yet be indexed.

GitHub rankings are derived from official API data and recorded observations; they are not GitHub Trending rankings. Growth remains unknown until sufficient history exists, and high lifetime star counts do not automatically fill the growth list. X and Reddit are not integrated. xAI's public Hub models are tracked separately from the X social platform; its news pages remain unavailable. See [data sources and limitations](docs/data-sources.md) for details.

## Quick Start

### 1. Prerequisites

| Dependency    | Requirement                                                                                   |
| ------------- | --------------------------------------------------------------------------------------------- |
| Git           | Clone and update the repository                                                               |
| uv            | Install Python dependencies and manage the Python 3.11 environment                            |
| Node.js / npm | Node.js 22.22.2 or later in the 22.x series; install frontend dependencies from the lockfile  |
| PostgreSQL    | PostgreSQL 18 with pgvector, provided by Docker Desktop / Docker Compose in the default setup |
| Browser       | A desktop browser with a workspace at least 1024 pixels wide                                  |

On Windows, choose **WSL2** or **native PowerShell**. The complete local workflow has been verified with a user-managed PostgreSQL installation in WSL2. Docker Desktop deployment and the complete native Windows workflow have not been independently verified. The [installation guide](docs/installation.md) covers tools, existing databases, and alternative setup paths.

### 2. Clone and Start

Start Docker Desktop first. For WSL2, enable Docker Desktop's integration with your WSL distribution.

**WSL2 terminal:**

```bash
cd ~
git clone https://github.com/yccc530/FrontierSignal.git
cd FrontierSignal
bash scripts/start.sh
```

**Or Windows PowerShell:**

```powershell
git clone https://github.com/yccc530/FrontierSignal.git
cd FrontierSignal
.\scripts\Start.ps1
```

The startup script installs locked dependencies, creates a private `.env` with a random database password, starts the database, applies migrations, builds the frontend, and starts the application. Existing `.env` files are preserved. The initial setup downloads dependencies and the database image.

Open **http://localhost:8000** in your browser. Keep the terminal open; press `Ctrl+C` to stop the web service. Database contents are retained. Do not use `docker compose down -v` for routine shutdown because it deletes the database volume.

### 3. Collect Your First Articles

1. Open **Sources (信息来源)**, enable the sources you need, and select **Collect all (采集全部)**.
2. Check **Tasks (运行任务)** for completion, new records, duplicates, and errors.
3. Browse **Articles (资讯库)**. Select a title to read details or follow the original source link.
4. Open **Recommendations (技术推荐)** to review discoveries. Growth metrics in **Projects (开源项目)** accumulate as collection continues.

A fresh installation starts without demo articles. Queries rotate within a request budget, so the first run does not cover every topic. See the [usage guide](docs/usage.md) for filters and recommendation settings.

## AI Summaries

Set these values in the private `.env` at the repository root, then restart the backend:

```dotenv
FS_LLM_BASE_URL=https://your-provider.example/v1
FS_LLM_API_KEY=replace_with_your_own_key
FS_LLM_MODEL=your-model-id
```

These are placeholders. Use your provider's actual settings. The base URL must not include `/chat/completions`; the application appends that path.

Open **Settings (系统设置)** and select **Verify API (验证接口)**. Confirm success in **Tasks (运行任务)**, then select **Analyze pending (分析待处理)** in the article feed. When the scheduler is enabled and the LLM configuration is complete, pending articles are also analyzed automatically in batches, consuming provider usage.

The provider adapter supports configurable OpenAI-compatible Chat Completions services. JSON mode is disabled by default because compatible gateways can support different parameters. Credentials are read from local configuration or environment variables and are not returned in full to the browser. See [configuration](docs/configuration.md) for optional OpenCode gateway import, proxies, and request budgets.

## Maintenance

The detailed guides below are currently in Simplified Chinese.

| Task                                                      | Guide                                            |
| --------------------------------------------------------- | ------------------------------------------------ |
| Restart, run in the background, or update                 | [Installation and startup](docs/installation.md) |
| Manage sources, model cards, and recommendations          | [Usage](docs/usage.md)                           |
| Configure the LLM, GitHub token, proxy, or budgets        | [Configuration](docs/configuration.md)           |
| Back up or restore into a new database                    | [Backup and recovery](docs/backup-recovery.md)   |
| Diagnose blank pages, connection failures, or rate limits | [Troubleshooting](docs/troubleshooting.md)       |

FrontierSignal is designed for personal local use and binds to `127.0.0.1` by default. It has no remote account authentication. Data is stored in local PostgreSQL. With a cloud LLM enabled, article titles and bounded body excerpts are sent to your configured provider. Collection stops when the computer sleeps, WSL closes, or the backend stops; complete recovery of news missed during downtime is not guaranteed.

## Development and Project Documents

[GitHub Actions CI](https://github.com/yccc530/FrontierSignal/actions/workflows/ci.yml) runs Ruff, backend unit tests, frontend unit tests, and a production build on pushes to `main`, pull requests to `main`, and manual dispatches. It requires no business API secrets and does not call paid models or live collection services. See [development and testing](docs/testing.md#github-actions) for details.

The backend uses Python 3.11, FastAPI, SQLAlchemy, Alembic, and APScheduler with PostgreSQL and pgvector. The frontend uses React, TypeScript, Vite, Tailwind CSS, shadcn/ui, and TanStack Query. Collection runs in the background within a modular monolith using one application worker.

| Document                                                                | Contents                                                            |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [Architecture](docs/architecture.md)                                    | Module boundaries, data flow, and persistence                       |
| [Development and testing](docs/testing.md)                              | Local development, relevant checks, and live-service verification   |
| [Validation history](docs/validation-history.md)                        | Dated results, verified environments, and remaining validation gaps |
| [Project plan](PROJECT_PLAN.md)                                         | Current progress and planned work                                   |
| [Collection expansion](docs/collection-expansion-plan.md)               | Implementation and verification by topic                            |
| [Reuse assessment](REUSE_ASSESSMENT.md)                                 | Upstream audits and reuse decisions                                 |
| [Contributor rules](AGENTS.md) / [Design system](docs/design-system.md) | Engineering and interface conventions                               |
| [Changelog](CHANGELOG.md)                                               | Feature and documentation changes                                   |

Use [Issues](https://github.com/yccc530/FrontierSignal/issues) to report problems. Include your operating system, startup method, reproduction steps, and redacted error messages. Do not attach `.env`, credentials, or a full database backup.

## Translations

| Language | Entry point                        |
| -------- | ---------------------------------- |
| English  | [README.md](README.md)             |
| 简体中文 | [README.zh-CN.md](README.zh-CN.md) |

`README.md` is the default English entry point. Additional languages use `README.<language-tag>.md` at the repository root. A new translation should preserve the same sections, executable commands, and documented limitations, and add its link to the language navigation in every existing README. Link only to translations that exist.

All versions share screenshots from `docs/images/`; do not duplicate images per language. Keep existing translations synchronized when features or startup instructions change. README translations do not imply that the application interface is localized. Contributions through pull requests are welcome.

## License and Acknowledgments

Parts of the RSS parsing and SimHash logic were adapted from AI News Brief, and some interface components come from shadcn/ui. Attribution and upstream licenses are retained in [third-party notices](THIRD_PARTY_NOTICES.md) and [licenses](licenses).

FrontierSignal's project code and documentation are licensed under the [MIT License](LICENSE). Preserve the copyright and license notices when using or distributing the software. It is provided as is, without warranty.

Third-party code and dependencies retain their respective licenses. The project's license does not change the rights or license terms of collected articles, papers, model cards, or publisher trademarks.

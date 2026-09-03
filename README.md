# Market Research Full Workflow

> 本仓库为 [mounteee/market-research-full-workflow](https://github.com/mounteee/market-research-full-workflow) 的**增强分支**（MIT 协议），并吸收行业深度报告工程实践经验。

一个面向战略、投资与商业化决策的**标准行业深度研究工作流** Skill。输入调研主题后，自动完成任务路由、多源取证、证据台账、知识卡片、行业结构分析、判断主线、8 分片并行写作、按内容选型可视化、事实核查、质量审核、联合逻辑审查、润色和飞书交付。

## 核心设计

- **标准行业报告结构**：`references/industry-report-standard.md` 是唯一章节事实源；正文采用行业报告骨架，不套学术论文九章，也不使用历史 6 片结构。
- **可追溯证据**：三条采集通道并行，结果固化到 `evidence/source-ledger.jsonl`、`evidence/knowledge-cards.md`；公开原始资料下载到 `evidence/sources/`，失败如实记录。
- **8 片并行写作**：主线冻结后，8 个 Writer 并行写入各自分片，组装器按固定顺序拼接并执行章节/字数/引用/图号/Markdown 门禁。
- **AI 编写图表代码**：quick ≥5、standard 6-8、deep 8-12 张图；图表编码 Agent 按数据实际形态逐图亲手编写 matplotlib 脚本并在任务虚拟环境运行（图内不渲染主标题——标题唯一归属正文图名行，防重复标题/图片漂移）；`charts/chart-manifest.json` 每条目强制绑定 `card_id/source_id/year/unit/definition/base_period/source/position/script`。
- **完整质量关卡**：拼装校验 → 图表脚本布局自检 → 逐图视觉检查 → 事实核查 → 质量审核 → 联合逻辑审查 → 润色 → 最终门禁。
- **断点恢复**：`.workflow.json` 原子记录每阶段状态、产物路径和重试次数，中断后从最近失败阶段恢复。
- **统一重试**：每个 Agent/脚本最多两次重发，失败写入 `degraded` 并说明原因；审核“打回”与故障重试分离。
- **飞书交付**：生成绝对路径本地版，再自动转成 `@./charts/` 相对路径推送副本；上传前后校验图片和 Mermaid，回读核对块数。

## Agent 清单

| Agent | 职责 |
|-------|------|
| collector-industry / collector-competitor / collector-user | 三路并行采集事实 |
| knowledge-curator | 知识卡片、证据台账、原始资料下载清单 |
| analyzer-industry / analyzer-competitor / analyzer-user | 三路并行分析 |
| framework | 判断主线底稿 + 标准行业报告框架 |
| framework-reviewer | 框架审核 |
| writer | 标准行业报告单分片写作 |
| visualizer | 图表编码 Agent：逐图亲手编写绘图代码并在任务虚拟环境运行，产出 PNG 与 chart-manifest.json |
| fact-checker | 分片关键数字核查 |
| quality-reviewer | 逐章质量审核 |
| logic-auditor | 联合逻辑审查 |
| polisher | 全文润色 |

历史 `researcher-*` 文件仅作兼容保留，不属于正式入口。

## 调研深度

| 深度 | 数据/证据 | 正文净字数 |
|------|---------|-----------|
| quick | 核心维度各 ≥2 条独立证据 | 20000-25000 字 |
| standard | 政策 ≥5 行、总来源 ≥18 条 | 30000-35000 字 |
| deep | 多轮检索、来源扩容 | 40000-50000 字 |

正文净字数不含参考文献、免责声明和原始资料。

## 运行目录

**任务目录契约**：产物必须落在用户当前任务指定的文件夹，绝不默认 Desktop——由 `scripts/report/resolve_run_dir.py`（解析：显式 > 工作区 > CWD 判定）+ `prepare_run.py`（准备：任务级 .venv、目录结构、绘图脚本副本）完成；任务自带 `.venv`，绘图脚本在任务目录 `scripts/charts/` 内原地运行。

```text
{当前任务文件夹}/{date}_{topic_slug}_industry-analysis/
├── .workflow.json
├── .venv/                       # 任务级虚拟环境（Windows: .venv/Scripts/python.exe）
├── inputs/request.md
├── inputs/routing.json
├── evidence/source-ledger.jsonl
├── evidence/knowledge-cards.md
├── evidence/download-manifest.json
├── evidence/download-results.json
├── evidence/gaps.md
├── evidence/sources/
├── analysis/judgment-spine.md
├── analysis/framework.md
├── analysis/framework-review.md
├── parts/01-08
├── scripts/charts/fig_*.py     # 图表编码 Agent 逐图脚本（任务 venv 原地运行）
├── charts/chart-manifest.json
├── charts/inspection.json
├── reviews/
├── output/report.md
├── output/report.local.md
├── output/report.feishu.md
└── logs/
```

## 报告结构

```text
# {行业}行业深度研究——{一句话核心判断}
摘要 / 关键词
## 核心观点
## 可视化图表索引
## 一、行业定义、规模测算与历史坐标
## 二、行业结构、产业链与竞争格局
## 三、用户需求与行为洞察
## 四、核心驱动力、制约因素与政策环境
## 五、趋势研判与结构性机会
## 六、商业化路径、盈利质量与落地建议
## 七、风险提示、结论与展望
## 参考文献
## 附录：数据来源、方法与术语
```

对应生产分片：`01-executive-summary`、`02-industry-definition-scale`、`03-structure-competition`、`04-user-insight`、`05-drivers-policy`、`06-trends-opportunities`、`07-commercialization-roadmap`、`08-risk-conclusion-references`。

## 脚本

```text
scripts/
├── charts/
│   ├── gen_chart.py            # 模板参考/兜底渲染器（8 类图 + 布局预检，AI 编码不强制）
│   ├── render_visual_check.py  # 登记图表检查状态清单
│   └── pack_skill.py           # dist 重打包
└── report/
    ├── resolve_run_dir.py      # 运行目录解析（任务文件夹优先，禁 Desktop 默认）
    ├── prepare_run.py          # 任务级 .venv + 目录结构 + 绘图脚本副本（幂等）
    ├── chart_manifest.py       # 图表清单统一解析（chart-manifest.json 优先，兼容旧 specs.json）
    ├── deliver.py              # 一键交付：校验→索引→组装→视觉门禁→副本→上传→回读
    ├── quick_audit.py          # 一键诊断 run_dir 健康度（禁则/图文/图表/证据/协同提示）
    ├── assemble_report.py      # 8 片组装 + 字数/结构/引用/图号/Markdown 门禁
    ├── card_index.py           # 章节证据注入包（卡片 × 台账 → inject/cards 片段）
    ├── evidence_ledger.py      # 证据台账校验与汇总
    ├── forbidden_rules.py      # 禁则检测（正文项目列表/标签句式/数字小节等）
    ├── download_sources.py     # 公开资料下载 + SHA-256 记录
    ├── make_feishu_copy.py     # 绝对路径 → 飞书相对路径副本
    ├── upload_report.py        # 指数退避上传 + ticket 轮询 + 回读清单
    ├── validate_report.py      # 最终报告与产物门禁（含证据产物存在性）
    └── workflow_state.py       # .workflow.json 原子更新
```

## 环境初始化

**任务自带虚拟环境**（不复用本仓库 .venv）：编排者解析任务目录后运行

```text
{skill_python} {skill_root}/scripts/report/prepare_run.py --run-dir {run_dir}
```

脚本幂等完成：目录结构 → 创建 `{run_dir}/.venv`（Windows: `.venv/Scripts/python.exe`）→ 安装 matplotlib/pandas/numpy（官方源失败自动切阿里云镜像）→ 复制绘图脚本到 `{run_dir}/scripts/charts/`。

本仓库 .venv 仅供开发自测：

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install matplotlib pandas numpy -i https://mirrors.aliyun.com/pypi/simple/
./.venv/Scripts/python.exe scripts/charts/gen_chart.py --self-test
```

## 触发示例

```
帮我调研一下 AI 编程工具赛道
做一份本地生活行业市场分析，重点关注竞争格局与盈利模式
深度调研新能源汽车后市场，读者是投资人
```

触发关键词：市场调研、行业分析、竞品分析、用户调研、赛道摸底、项目可行性分析、商业调研、用户画像搭建、竞品优劣势拆解、盈利模式调研。

## License

MIT
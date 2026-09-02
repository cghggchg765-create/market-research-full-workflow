# Market Research Full Workflow

> 本仓库为 [mounteee/market-research-full-workflow](https://github.com/mounteee/market-research-full-workflow) 的**增强分支**（MIT 协议）：在原作者多 Agent 工作流基础上，新增分片并行写作（≥3 万字）、图表可视化（含程序校验与视觉检查）、学术规范（GB/T 7714 作者-年份引用）、飞书自动交付等能力。

一个为 Claude Code/ZCode 构建的多 Agent 市场调研工作流 Skill。输入调研主题，自动完成从数据收集到报告交付的全流程。

## 工作流程

```
用户输入调研主题
       ↓
  需求解析（主题、行业、深度、读者）
       ↓
  数据收集（3 个 Agent 并行）
  ├── 行业数据收集
  ├── 竞品数据收集
  └── 用户数据收集
       ↓
  数据分析（3 个 Agent 并行，交叉参考）
  ├── 行业数据分析
  ├── 竞品数据分析
  └── 用户数据分析
       ↓
  框架搭建 → 框架审核（不合格打回修改）
       ↓
  报告撰写
       ↓
  事实核查（独立搜索验证，不合格打回修改）
       ↓
  质量审核（不合格打回修改）
       ↓
  交付（本地文件 + 飞书文档）
```

## 核心设计

- **14 个专职 Agent**：收集、分析、框架、撰写、核查、审核各司其职，不混淆职责
- **并行执行**：数据收集和数据分析阶段各 3 个 Agent 同时工作
- **交叉参考**：分析 Agent 接收本领域完整数据 + 其他领域摘要，避免信息孤岛
- **三道质量关卡**：框架审核 → 事实核查 → 质量审核，不合格自动打回修改
- **事实核查独立验证**：核查 Agent 独立搜索数据源，不依赖原始收集结果

## Agent 清单

| Agent | 职责 |
|-------|------|
| `collector-industry` | 行业数据收集 |
| `collector-competitor` | 竞品数据收集 |
| `collector-user` | 用户数据收集 |
| `analyzer-industry` | 行业数据分析 |
| `analyzer-competitor` | 竞品数据分析 |
| `analyzer-user` | 用户数据分析 |
| `framework` | 报告框架搭建 |
| `framework-reviewer` | 框架审核 |
| `writer` | 报告撰写 |
| `fact-checker` | 事实核查（独立验证） |
| `quality-reviewer` | 质量审核 |
| `researcher-industry` | 行业深度研究 |
| `researcher-competitor` | 竞品深度研究 |
| `researcher-user` | 用户深度研究 |

## 调研深度

| 深度 | 搜索轮次 | 数据来源 | 报告字数 |
|------|---------|---------|---------|
| `quick` | 2 轮 | 5+ 来源 | 20000-25000 字 |
| `standard` | 3-4 轮 | 8-12 来源 | 30000-35000 字 |
| `deep` | 5+ 轮 | 15+ 来源 | 40000-50000 字 |

**报告为分片并行结构**：8 个章节分片由 8 个撰写 agent 同步写作（`parts/`），再由组装脚本拼接校验（章节齐全/字数达标/图号连续/词汇重复检测），并自动生成「可视化图表索引」表。默认 ≥30000 字。

## 报告结构

输出报告遵循标准结构：

1. **执行摘要** — 核心结论、关键数据、机会与风险、战略建议
2. **行业概况** — 市场规模、增速、发展周期、政策环境
3. **竞争格局** — 市场份额、头部玩家分析、竞争矩阵
4. **用户洞察** — 用户画像、决策链路、核心痛点、付费意愿
5. **盈利模式** — 商业模式、成本结构、利润空间
6. **风险与机会** — 风险评分卡、差异化机会、窗口期判断
7. **落地建议** — 战略定位、分阶段行动计划、KPI、预算框架
8. **附录** — 数据来源清单、方法论说明、图表缺口说明

## 可视化能力

每份报告自动生成 **≥5 张图表**（按调研深度动态配额：quick ≥5 / standard 6-8 / deep 8-12），由可视化专员 SubAgent 按 `references/chart-guidance.md` 选型矩阵从真实调研数据中产出：

- **PNG 数据图**（matplotlib）：市场规模折线、份额环形、竞品雷达、价格带对比、风险矩阵、LTV/CAC 对比等
- **mermaid 图**：产业链流程图、决策链路、分阶段甘特图
- 每张图带标题/单位/数据年份/来源/可信度标记，图号连续（图1~图N）
- 本地 Markdown 报告与飞书交付文档双端显示；数据不足的主题不硬画，列入「图表缺口说明」

### 环境初始化（首次运行前）

图表生成依赖 skill 内置的 Python 虚拟环境（`.venv`，matplotlib/pandas/numpy）。若缺失，在 skill 目录执行：

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install matplotlib pandas numpy
# pip 安装失败时追加阿里云镜像：
# ./.venv/Scripts/python.exe -m pip install matplotlib pandas numpy -i https://mirrors.aliyun.com/pypi/simple/
```

图表脚本自测：`./.venv/Scripts/python.exe scripts/charts/gen_chart.py --self-test`

## 使用方式

在 Claude Code 中直接输入调研需求即可自动触发：

```
帮我调研一下 AI 编程工具赛道
```

```
做一份本地生活行业的市场分析，重点关注竞品格局和盈利模式
```

```
深度调研新能源汽车后市场，读者是投资人
```

支持的触发关键词：市场调研、行业分析、竞品分析、用户调研、赛道摸底、项目可行性分析、商业调研、用户画像搭建、竞品优劣势拆解、盈利模式调研。

## 安装

将此仓库克隆到 Claude Code 的 skills 目录：

```bash
git clone https://github.com/mounteee/market-research-full-workflow.git ~/.claude/skills/market-research-full-workflow
```

## 目录结构

```
market-research-full-workflow/
├── SKILL.md                    # 编排器（Orchestrator）主文件
├── agents/                     # 各专职 Agent 的 prompt
│   ├── collector-*.md          # 数据收集 Agent（3个）
│   ├── analyzer-*.md           # 数据分析 Agent（3个）
│   ├── researcher-*.md         # 深度研究 Agent（3个）
│   ├── framework.md            # 框架搭建 Agent
│   ├── framework-reviewer.md   # 框架审核 Agent
│   ├── writer.md               # 报告撰写 Agent（含图表占位约定）
│   ├── visualizer.md           # 图表可视化 Agent（新增）
│   ├── fact-checker.md         # 事实核查 Agent（含图数抽查）
│   └── quality-reviewer.md     # 质量审核 Agent（含图表规范检查）
├── references/                 # 参考资料
│   ├── methodology.md          # 调研方法论与数据来源
│   ├── report-structure.md     # 报告标准结构（含图表规范）
│   └── chart-guidance.md       # 图表选型矩阵与方法规范（新增）
├── scripts/
│   ├── charts/
│   │   ├── gen_chart.py        # 通用图表生成器（matplotlib，9 类图 + 布局自动校验 WARN）
│   │   └── pack_skill.py       # dist 重打包脚本
│   └── report/
│       └── assemble_report.py  # 分片组装器（拼接 parts/ → report.md + 字数/图号/重复校验 + 图表索引）
├── .venv/                      # Python 虚拟环境（matplotlib/pandas/numpy，不随包分发）
└── dist/                       # 编译产物
    └── market-research-full-workflow.skill
```

## License

MIT

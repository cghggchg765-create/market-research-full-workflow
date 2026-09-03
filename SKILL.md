---
name: market-research-full-workflow
description: 面向战略、投资与商业化决策的标准行业深度研究工作流。通过任务路由、多源取证、证据台账、知识卡片、行业结构分析、判断主线、8片并行写作、按内容选型可视化、视觉检查、事实核查、质量审核、联合逻辑审查、润色和飞书交付，生成可追溯的行业报告。
---

# 标准行业深度研究工作流

## 1. 规则优先级

1. `references/industry-report-standard.md` 是**唯一章节结构事实源**。它定义标准行业报告骨架和 8 个生产分片；不得改成学术论文九章，也不得恢复历史 6 片结构。
2. `references/academic-style.md` 只约束证据、引用、研究透明度、语言和 Markdown，不定义行业报告目录。
3. `references/data-collection-protocol.md`、`data-grading-and-citation.md` 定义取证通道、证据等级和数据核验纪律。
4. `references/knowledge-cards.md` 定义证据台账、知识卡片、原始资料下载和 Agent 联动。
5. `references/chart-guidance.md`、`chart-inspection.md` 定义图表选型、生成和视觉检查。
6. 正文不得暴露 Agent、lane、tier、门禁、检索轮次或本 Skill 名称；不得出现 `[n]` 编号引用、`【事实】`/`【推断】` 等内部标签或 `**关键词**：内容` 句式。

## 2. 适用范围与路由

先读取 `references/task-router.md`，判断用户是否需要中长期完整行业报告。提取并落盘 `inputs/routing.json`：

### 流程总览（含同步等待门）

```
Step 0 需求解析与路由（落盘 inputs/routing.json）
   ↓
[WAIT] 路由通过
   ↓
Step 1a 证据采集（3 collector 并行）
   ↓ [WAIT] 3/3 返回并核验来源条目，缺一不推进
Step 1b 数据分析（3 analyzer 并行）＋ Step 1c 知识固化（1 curator 并行）
   ↓ [WAIT] 4/4 返回；analysis/*.md、knowledge-cards、source-ledger 全部落盘
Step 2 判断主线与框架（judgment-spine.md + framework.md）
   ↓ [WAIT] 主线与框架冻结
Step 2b 框架审核
   ↓ [WAIT] framework-review.md 生成且判定通过
Step 3 八片写作（8 writer 并行）∥ 3b 图表编码（visualizer 逐图写绘图代码并运行，只读分析+框架+台账）
   ↓ [WAIT] 8/8 分片落盘且单片校验通过；chart-manifest + PNG 就绪（≥5）
Step 3-2 组装（assemble_report.py --spec → output/report.md，一次注入图表索引）
   ↓ [WAIT] 组装门禁通过（字数/图号/索引/引用/语法）
Step 3-3 图文审阅（漂移/重复标题/图文对应；Agent 编辑修复）→ 3c 图表回填
   ↓ [WAIT] 漂移/重复标题检查通过；inspection.json 落盘；回填编辑后重新组装并 validate exit 0（后续评审与交付对象=最新 report.md）
Step 4a 事实核查 ∥ Step 4b 质量审核（两审并行，各自落盘）
   ↓ [WAIT] fact-check.md 与 quality-review.md 均生成
Step 4c 联合逻辑审查（依赖 fact 结论）
   ↓ [WAIT] logic-review.md 生成且判定通过
Step 4d 润色 → 重新组装 + validate
   ↓ [WAIT] polish-report.md 落盘，validate exit 0
Step 5 交付（make_feishu_copy → 上传回读，与交付摘要并行推进）
```

**任何 `[WAIT]` 未满足时，不得启动其下一个阶段；先重试/补齐前置产物，再继续。** 详细门槛见 3.5 节。

- `topic`、`industry`、`focus`、`depth`、`audience`、`context`
- `report_type`：行业全景/子赛道/技术路线/周期位置/政策主题
- `industry_structure`：产业链型/网络型/资产负债型/单店模型型
- `decision_question`：投资/进入/战略落地/观望/退出
- `exclusions`：明确不回答的窄问题

以下任务不触发本流程：单公司、单日涨跌、单一财报、单一宏观事件、一句话科普、翻译。若路由不通过，简要说明应使用其他场景，不强行生成长报告。

## 3. 运行目录、任务虚拟环境与状态（任务文件夹优先，禁止默认 Desktop）

**run_dir 解析（在任何 mkdir/Write/绘图/交付之前必须完成）**，优先级从高到低：

1. 用户在本次对话中显式指定的任务文件夹（最优先，原样使用）；
2. 宿主明确标记为当前任务工作区的目录；
3. 当前工作目录——仅当其已是任务工作区（含 `inputs/`、`parts/`、`evidence/` 或 `.workflow.json`）；
4. 都无法确定 → **停下来询问用户指定文件夹**；不得按模板默认创建 `C:/Users/.../Desktop/...`。

解析与准备命令（幂等，先跑这两步再开始任何产出）：

```text
{python} {skill_root}/scripts/report/resolve_run_dir.py [--run-dir {用户任务文件夹}]
{python} {skill_root}/scripts/report/prepare_run.py --run-dir {run_dir}
```

`prepare_run.py` 在 `{run_dir}` 内完成（幂等）：

- 创建标准目录结构（inputs/evidence/analysis/parts/charts/reviews/output/logs/scripts）；
- 创建**任务级虚拟环境** `{run_dir}/.venv`（Windows: `.venv/Scripts/python.exe`；安装 matplotlib/pandas/numpy，失败切阿里云镜像）；**绝不复用 skill 安装目录的 .venv**；
- 把**审计与检查登记脚本**复制到 `{run_dir}/scripts/charts/`（figlib_audit.py、render_visual_check.py）；gen_chart.py 保留在 skill 内仅作字体/布局工具**参考**——正式图表一律由 Agent 按数据手写代码（{run_dir}/scripts/charts/fig_*.py，同目录 import figlib_audit 做 bbox 审计），**不复制、不调用固定生成器**；
- 输出运行时信息 JSON（task_python 绝对路径、Python 版本、脚本副本清单）。

目录结构（`{run_dir}/` 内，与此前目录树一致，另含 `scripts/charts/`、`{run_dir}/delivery.json`）。使用 `scripts/report/workflow_state.py` 原子更新 `.workflow.json`（`--state {run_dir}/.workflow.json --step {阶段} --status done [--retries n] [--artifact {路径}]`）：记录每阶段 status/retries/artifact/value 与更新时间；`--show` 查看全量。中断后先读状态：产物存在且重新运行对应阶段校验通过 → 跳过该阶段；产物缺失或校验失败 → 从该阶段恢复。

{python} = 运行 report 脚本与一键交付的解释器（report 脚本仅用标准库，编排环境 python 即可）；{skill_root} = skill 安装目录（源码与参考文件位置）；{run_dir} = 本次任务产物位置；{task_python} = {run_dir}/.venv/Scripts/python.exe（图表运行与审计专用）。四者不可混用：脚本从 {skill_root}/scripts 或 {run_dir}/scripts 取，产物只进 {run_dir}；图表运行/审计用 {task_python}，report 脚本与一键交付用 {python}，均以 {run_dir} 为 CWD。

## 3.5 阶段同步与进入门槛（必须先等齐再推进）

编排者是**串行调度器**：同一个并行组内的子 agent 并行执行，但**组与组之间必须严格串行**，且下游阶段只有在**全部前置产物就绪并通过校验**后才能启动。不得"先写着、后面再补数据"，不得在子 agent 未返回时提前创建下一阶段的产物。

### 同步原则

1. 每次启动一个并行组后，编排者**必须等待该组全部成员返回**，逐份检查结果：非空、格式合法、关键字段齐全。
2. 任一副产物不满足门槛时：先按第 4 节重试补齐；重试后仍失败 → 该阶段标记 `degraded`，**依赖它的下游阶段不得正常启动**；确需继续时，必须把降级影响写入交付摘要。
3. 产物检查以「文件存在 + 非空 + 能通过对应校验」为准，不以子 agent 的自述为准；校验命令见下表。
4. 每个并行组结束后，编排者在 `.workflow.json` 把该阶段写为 `done`，才允许进入下一阶段。

### 阶段依赖与门槛表

| 阶段 | 并行组 | 启动前提（全部满足才可启动） | 就绪校验 |
|---|---|---|---|
| 1a 采集 | 3 个 collector 并行 | 任务路由通过 | 3/3 返回；来源条目非空且含 URL/数值/口径 |
| 1b 分析 + 1c 知识固化 | 3 analyzer + 1 curator 并行 | 1a 的 3 份结果全部落盘；source-ledger 初稿可读 | 4/4 返回；`analysis/industry.md`、`analysis/competitor.md`、`analysis/user.md`、`evidence/knowledge-cards.md`、`evidence/source-ledger.jsonl` 存在且非空 |
| 2 框架 + 主线 | framework | 3 份分析落盘；知识卡片就绪；行业结构类型确定 | `analysis/framework.md` 与 `analysis/judgment-spine.md` 存在且包含主线/三情景/T 信号 |
| 2b 框架审核 | framework-reviewer | 框架与主线冻结 | `analysis/framework-review.md` 落盘且含评分/通过判定 |
| 3 八片写作 ∥ 3b 图表编码 | 8 writer + 1 chart-coder 并行 | 主线冻结；框架冻结；章节规划表生成（图号预分配）；知识卡片/台账就绪；task venv 就绪 | 8/8 `parts/*.md` 校验通过；`charts/chart-manifest.json` + PNG（≥5）生成、脚本落 `{run_dir}/scripts/charts/` |
| 3-2 组装（带 spec） | 编排者 | 8 片与 specs 均就绪；PNG 已生成 | `report.md` 生成；字数/图号/索引/引用/语法门禁全过 |
| 3-3 图文审阅 + 3c 回填 | 审阅 Agent + 编排 Agent 编辑 | 组装通过；PNG 存在 | 漂移/重复标题/图文对应检查通过；`charts/inspection.json` 落盘；回填编辑后**重新组装并 validate exit 0** |
| 4a 事实核查 ∥ 4b 质量审核 | fact-checker ∥ quality-reviewer（并行） | 3-3 回填后的重新组装通过（评审对象为最新 `report.md`；两者互不依赖输出） | `reviews/fact-check.md`、`reviews/quality-review.md` 均落盘 |
| 4c 联合逻辑审查 | logic-auditor | 4a/4b 均完成 | `reviews/logic-review.md` 落盘且判定通过 |
| 4d 润色 | polisher | 4c 通过 | `reviews/polish-report.md` 落盘；润色后必须重新组装并 validate exit 0 |
| 5 交付 | 编排者 | 最终门禁全部通过 | `scripts/report/validate_report.py` exit 0；`report.feishu.md` 生成；飞书回读通过（可与交付摘要并行） |

### 等待动作示例（编排者必须执行）

- 启动 1a 后，**等待 3/3 收集返回再进入 1b/1c**；若只有 2/3 返回，绝不开始分析或写作。
- 启动 1b/1c 后，**等待 4/4 返回再进入框架**；knowledge-cards 或任一分析文件缺失时，不推进。
- 框架与主线未冻结、规划表未生成前，**不启动 Writer 与 visualizer**。
- 8 个 Writer 与 visualizer 是同一并行组：**等待 9/9 全部就绪**（8 片 + specs）才组装；visualizer 只读分析/框架/台账，不依赖正文。
- 4a 事实核查与 4b 质量审核是并行组：**两审都落盘后**才进入 4c；不要等 fact 完成才开始 quality。
- 下载 `download_sources.py` 属于后台任务：启动后不阻塞 Step 2/3，只需在 4a 前完成。
- 任一并行组出现成员未返回时：不要把"未返回"当作"已完成"，也不要基于部分结果先写下游章节；按第 4 节重试该成员，重试后仍失败则标记 `degraded` 并暂停依赖该产物的一切下游产出。

## 4. 统一重试策略

每个阶段最多两次重发：

1. 原样重试一次，处理瞬时网络、模型和文件系统故障。
2. 策略重试一次，补上下文、拆小任务、换检索词或换备用 Agent。
3. 仍失败则写入 `degraded` 状态并说明原因，不伪造成功。

审核“打回”是质量轮次，不与故障重试混计。论文付费墙、未授权资料、不存在的 URL 不反复重试。

## 5. 证据采集与知识固化

### 5.1 三路并行采集（按报告需求规划 + 分域卡片就地产出）

读取 `data-collection-protocol.md`、`data-grading-and-citation.md` 和 `references/industry-report-standard.md`，在同一响应中并行启动：

- 行业证据 Agent：定义、规模、增速、产业链、政策、周期。
- 竞争证据 Agent：玩家、产品、价格、份额、经营指标、融资、反馈。
- 用户证据 Agent：用户分层、场景、痛点、付费、流失、替代方案。

每个采集 Agent 必须完成四件事（均落盘到 `{run_dir}/evidence/`）：

1. **按报告需求规划搜索**：对照行业报告六个主体板块列出本域问题清单，写入 `collection-plan.{domain}.md`，再按问题搜索，以覆盖度停机。
2. **返回结构化数据表**：每条来源含标题/作者机构/日期/URL/DOI/类型/原始值/单位/口径/基期/取数通道/证据等级/可下载性/对应章节。
3. **分域知识卡片就地产出**：搜索完成后立即把关键证据整理为 `knowledge-cards.{domain}.md`（domain=industry/competitor/user），不经过主 Agent 转述，避免知识遗漏。
4. **分域证据盘点报告**：写 `collection-report.{domain}.md`，含问题对照、来源 A/B/C 汇总、关键冲突、数据缺口和建议支撑章节。

核心维度（规模、增速、格局、价格、盈利、政策、需求）各至少两条独立证据；政策至少五条；总来源 18-25 条、单域卡片 ≤15 张。**覆盖度停机 + 证据饱和即停 + 时间盒（单域 ≤30 分钟价值量）**，防止过度收集：每问题 2 条独立证据即覆盖，连续 2 问题无新增即收尾，缺口写入盘点报告而不是继续加搜。缺数据不得用常识补齐。

### 5.2 分域卡片合并归一与原始资料

**同步门：必须等 5.1 的 3 路采集全部返回、且三份分域卡片与盘点报告均已落盘后，才与三路分析 Agent 一起启动** `agents/knowledge-curator.md`。knowledge-curator 不再接收主 Agent 转述，而是直接读取分域产物并做**合并归一**：

- 读 `evidence/knowledge-cards.{industry,competitor,user}.md`，按 URL/DOI/标题去重，统一编号为 `evidence/knowledge-cards.md`（K01…Kn，保留 domain 字段）。
- 生成 `evidence/source-ledger.jsonl`（source_id/card_id/title/author_or_org/year/url/source_level/source_value/unit/definition/base_period 为必填；正文用途/验证状态可选）。
- 生成 `evidence/download-manifest.json` 和 `evidence/gaps.md`。

编排者随后执行：

1. `{python} {skill_root}/scripts/report/evidence_ledger.py --ledger {run_dir}/evidence/source-ledger.jsonl` 校验台账合法性。
2. `{python} {skill_root}/scripts/report/card_index.py --cards {run_dir}/evidence/knowledge-cards.md --ledger {run_dir}/evidence/source-ledger.jsonl --out {run_dir}/evidence/card-index.json` 生成卡片索引（供按章节拆解）。
3. `{python} {skill_root}/scripts/report/download_sources.py --manifest {run_dir}/evidence/download-manifest.json --outdir {run_dir}/evidence/sources --result {run_dir}/evidence/download-results.json [--timeout 30]` 下载公开、合法、无需绕过访问控制的论文 PDF、官方报告、CSV/XLSX 到 `evidence/sources/`（**并发下载、单文件 ≤50MB、默认超时 30s、失败重试一次**），记录 SHA-256/字节数；失败、登录、付费或反爬资料保留卡片并写明原因，不伪造文件。**该步骤是后台任务：启动后不阻塞 Step 2/3，只需在 4a 前完成。**

知识卡片的文件路径统一是 `evidence/knowledge-cards.md`，禁止在同一运行目录另建 `knowledge/` 平行目录。

## 6. 行业结构分析与判断主线

**同步门：启动分析前必须确认 3 路采集结果、`evidence/source-ledger.jsonl` 初稿、`evidence/knowledge-cards.md` 均已就绪；启动框架前必须等待 3 路分析 Agent 与知识主管全部返回。**

读取 `references/industry-structure-playbooks.md`、`references/analysis-framework.md`、`references/insight-spine.md`。三路分析 Agent 并行消费完整证据、结构化跨域摘要、知识卡片和行业类型 playbook，输出到 `analysis/`。

框架 Agent 生成 `analysis/judgment-spine.md`，至少包含：

- 决策问题与研究范围。
- 一句话主线（可验证、可推翻，含时间窗口）。
- 市场共识、非共识判断、3-5 个核心数据锚点。
- 因果链、利润池/价值迁移。
- 乐观/中性/悲观三情景及结果。
- T1…Tn 验证/证伪信号。
- 六个主体板块的子命题、证据和 Kxx 映射。

框架 Agent 再依据 `industry-report-standard.md` 生成标准行业报告大纲；框架审核 Agent 输出 `analysis/framework-review.md`，低于 7/10 最多打回一轮。

## 7. 8 片并行写作（与图表规划组成同一并行组）

**同步门：主线与框架冻结、章节规划表生成后，在同一个 response 中**并行启动 8 个 Writer + 1 个 visualizer**；图片编号在规划表中预分配，两方共用，避免并行冲突。等待 9/9 就绪后才组装。**

- 01：核心观点、摘要、关键词、共识/非共识、主线论证链。
- 02：行业定义、规模测算、增速、生命周期、历史坐标。
- 03：产业链、利润池、供需、竞争格局、玩家、终局。
- 04：用户分层、需求、决策链路、付费意愿和行为证据。
- 05：五维驱动—制约、技术路线、政策时间线与监管边界。
- 06：趋势、预期差、反方观点、三情景与验证信号。
- 07：商业模式、单位经济、盈利质量、现金流、落地路径与 KPI。
- 08：风险提示、结论、展望、参考文献、方法、术语、免责声明。

这些职责必须映射到固定分片文件名（与 `industry-report-standard.md` 和脚本一致，章节 token「一、…七、」对应 02…08）：`02-industry-definition-scale.md`、`03-structure-competition.md`、`04-user-insight.md`、`05-drivers-policy.md`、`06-trends-opportunities.md`、`07-commercialization-roadmap.md`、`08-risk-conclusion-references.md`。

### 章节证据注入与图号预分配（并行组开工前完成）

1. 编排者用 `scripts/report/card_index.py` 按章节生成**证据注入包**：
   ```text
   {python} {skill_root}/scripts/report/card_index.py --cards {run_dir}/evidence/knowledge-cards.md \
     --ledger {run_dir}/evidence/source-ledger.jsonl \
     --out {run_dir}/evidence/card-index.json --chapter "{章节名}"
   ```
   产出 `evidence/inject.{02|03|…}.json`（本章卡片 + 台账行）与 `evidence/cards.{02|03|…}.md`（卡片片段）。
2. **图号预分配**列入章节规划表：每章分配连续图号（如 02 章图1、03 章图2、04 章图3…），visualizer 按规划表逐图编写代码（每图 `id=chart-NN`、`display_name=图N …`，见第 8 节），Writer 按同一张表写占位 `![图N 标题]({run_dir}/charts/待定.png)`。
3. 每个 Writer 收到：绝对分片路径、本章配额、全文主线、全局大纲、本章证据注入包、章节 Kxx、**本章图号区间**、证据台账摘要、术语表，以及**「本章关键数据点（内嵌必用）」**——编排者把注入包中该章每张卡片的「关键数据点 + 解读策略 + 使用建议 + 反证与边界」原文直接粘贴进 Writer prompt，**不是只给文件路径**。Writer 必须把至少 80% 的论点建立在粘贴的数据点上并写入正文数值；**每个引用的数据点须配一句解读（数据意味着什么、与哪个指标印证、决策含义）**，有局限的卡片顺带说明边界；缺证据写入待核问题。
4. **单片即时校验（写作完成即执行）**：每个 Writer 落盘后，编排者立即运行
   ```text
   {python} {skill_root}/scripts/report/validate_report.py --stage part --file {run_dir}/parts/{分片}.md
   ```
   校验不过（标签句式/数字小节/禁则/清单化/非 canonical 命名）→ 打回该 Writer 修改，**不得进入组装**；8/8 通过后才运行组装。
5. 编排者检查 8 片 UTF-8/文件名/mtime/字数/章节职责，并核对 `charts/chart-manifest.json` 图号与规划表预分配一致；任一未就绪不得进入组装。

标准档正文净字数 30,000-35,000 字；quick 20,000-25,000；deep 40,000-50,000（组装时对 quick 用 `--target-words 20000`、deep 用 `--target-words 40000` 显式传参，防止被 standard 门槛误杀）。参考文献、免责声明和原始资料不计入正文净字数。组装脚本按 8 片固定顺序生成 `output/report.md`。

## 8. 图表编码、运行与审阅（与 8 片写作同一并行组）

可视化 Agent（`agents/visualizer.md`）在框架冻结后与 8 个 Writer **同一响应并行启动**，职责是**亲手编写每张图的绘图代码并运行生成 PNG**，不使用固定死模板：

- 依据注入包真实数据与规划表预分配图号，逐图编写 `{run_dir}/scripts/charts/fig_{NN}_{slug}.py`（中文字体注册、双轴/误差线/区间带等按需设计；**不在图内渲染主标题**——标题由正文图名行唯一承载，避免重复标题）；图型选择不限清单：先读 `references/chart-guidance.md`（基础矩阵 + **扩展图型决策库**：瀑布桥/堆叠面积/情景扇带/气泡定位/TAM-SAM-SOM/漏斗/排名棒棒糖/斜率/哑铃区间/金字塔/箱线/桑基等约 20 种，每类注明适用场景与报告章节落点），再按数据实情定图型——可自由组合或自定义，**gen_chart.py 不是生成入口**；
- 用任务虚拟环境逐个执行：`{task_python} {run_dir}/scripts/charts/fig_{NN}_*.py`；运行失败读报错修改重跑（每图 ≤3 轮）；
- 产出 `{run_dir}/charts/图N_标题.png`（≥5 张，standard 6-8，deep 8-12）与图表清单 `{run_dir}/charts/chart-manifest.json`（图号/标题/position/PNG 文件名/script/card_ids/source/unit）；
- 数据必须来自注入包卡片，PNG 内不渲染主标题，来源以小字标注在图内底部；
- 完成后运行 `render_visual_check.py` 登记 `{run_dir}/charts/inspection.json` 初始状态。
- **代码级审计**：每个 fig 脚本尾部接入 `from figlib_audit import audit; audit(fig, "图N …")`；渲染后用 `figlib_audit.py audit --script …` 逐脚本检查（`[FAIL]` 必须修复）；运行模型无视觉能力时按 `references/chart-inspection.md` §6 强制替代流程执行（audit + pixel + contact 拼版 + 人工清单），如实记录、不假装通过。

**审阅与修复（用 Agent 编辑，不用修复脚本）**：编排者用视觉能力逐张查看 PNG 与其在正文中的位置，重点检查——图片是否位于 position 对应章节（图片漂移）、图名行是否唯一（无重复标题）、图与前后文字是否对应、有无截断/乱码/遮挡。发现问题 → 派编辑 Agent 直接修改对应分片或绘图脚本并重跑；**禁止用脚本批量改写正文/分片**。

## 9. 事实、质量、逻辑与润色

依赖关系：**fact-checker 与 quality-reviewer 并行**（两者输入相同、互不依赖输出）→ logic-auditor（需要 fact 结论）→ polisher（需要逻辑通过）。

1. `fact-checker` 与 `quality-reviewer` **同一并行组启动**：
   - fact：每章 3-5 个关键数字，优先读取 `evidence/sources/` 原文，再联网补证；写 `reviews/fact-check.md`。
   - quality：8 片逐章 + 全局检查结构、数据、表格、图表、Markdown；写 `reviews/quality-review.md`。
2. **等待两审都落盘**后启动 `logic-auditor`：检查分项/总计、趋势、单位/基期、同指标跨章、主线、风险-建议、图文方向；写 `reviews/logic-review.md`。
3. `polisher`：只改术语、语气、衔接、句式和格式，不改事实/数字/结论/图号；写 `reviews/polish-report.md`；润色后必须重新组装并 validate。

任何打回按问题定位到具体分片；**多片打回时并行重写对应分片**（同一 response 内多个 Writer），修改后重新组装并运行相应门禁。每类审核最多 2 轮打回，超过则在交付摘要记录未决问题。

## 10. Markdown 与交付门禁

使用 `scripts/report/assemble_report.py`、`scripts/report/evidence_ledger.py` 和 `scripts/report/validate_report.py`（若已存在则先确认参数）执行：

- 标准行业报告章节和 8 片完整。
- H1 唯一、标题层级正确、列表使用有序 `1.`/`①`（正文禁 `-`/`*`/`•` 项目列表）、无纯文本伪标题。
- 正文净字数达到档位下限。
- 每个主体板块有论述、表格和 `回扣主线`（按 canonical schema）。
- 表名在表上方并空一行；图名在图下方并空一行。
- 作者/机构+年份引用与参考文献双向勾稽，禁止 `[n]`。
- 每个关键数字可追溯到 source_id/card_id、单位、口径、基期。
- 代码块闭合、表格列一致、图片路径存在、图号/索引连续。
- 不出现 `【事实】`、`【推断】`、`**关键词**：内容`、原始 HTML、裸 URL、base64 图片。
- 事实、质量、逻辑、润色结果均已落盘。

## 11. 飞书交付（受硬门禁保护的唯一交付通道）

本地版即 `output/report.md`（绝对图片路径，图片与正文同盘）；运行 `scripts/report/make_feishu_copy.py` 生成 `output/report.feishu.md`，自动校验图文件并把绝对路径转换为 `@./charts/`，含空格或括号的路径使用尖括号（display_name 以「图N 」开头必然命中）。

**一键交付（唯一交付通道，禁止散装跳步）：**

交付 = 运行单个脚本，串行完成全部前置清单，任一项失败立即中止并退出非 0，**不执行 lark-cli**：

```text
{python} {skill_root}/scripts/report/deliver.py \
  --run-dir {run_dir} --target-words {target} --title "{报告标题}" [--dry-run]
```

`deliver.py` 执行序列（与下面的前置清单一一对应）：

1. 8 片单片校验（`validate_report.py --stage part`）——不过即中止；
2. 生成/校验 `evidence/card-index.json`（缺则用 `card_index.py` 补生成）；
3. 图表产物校验：`charts/chart-manifest.json` 存在、PNG ≥5、PNG 文件齐全（manifest 与磁盘一一对应）；**视觉门禁：`charts/inspection.json` 存在且 `visual_status=passed`（或 `degraded` 且 `notes` 记录原因）**——仅登记未确认（pending）→ 中止；
4. `assemble_report.py` 组装（带 `--spec`，注入图表索引 + 图号门禁）；
5. `validate_report.py --stage final` 整篇校验（含图表硬门禁）；
6. `make_feishu_copy.py` 生成飞书副本；
7. `upload_report.py` 上传（自带重试、ticket 轮询、回读校验），写 `delivery.json`。

**禁止跳步**：未运行 `deliver.py`（或它返回非 0）时，不得调用 `lark-cli`/lark-doc 创建飞书文档，也不得把 `report.md` 当作最终交付物宣称完成。跳过可视化/视觉检查即视为流程违规；确因数据不足无法成图时，须在 `charts/inspection.json` 与交付摘要记录缺图原因，并经编排者确认后（图数 <5 或降级为表格）才允许在摘要中说明。

## 12. 断点续跑与输出摘要

### 断点续跑

每个阶段开始前读取 `.workflow.json`：

- `status=done` 且产物存在、哈希未变、对应校验通过 → 跳过该阶段。
- `status=failed` → 按统一重试策略重试，不从头重跑其他已完成阶段。
- `status=degraded` → 继续前先在交付摘要记录缺口，并把受影响结论/图表标为有限证据。
- Agent 写入文件后由编排者检查绝对路径、UTF-8、文件大小、修改时间和内容摘要，再将状态写为 done。

### 输出摘要

必须汇报：本地报告路径、飞书 URL、正文净字数、8 片状态、证据/卡片/下载数量、图表数量及视觉检查结果、事实/质量/逻辑/润色结果、重试和打回轮次、未解决缺口。报告正文不暴露这些内部流程字段。

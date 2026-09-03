# 知识卡片规范（资料下载与固化）

调研过程中搜索到的论文、报告、数据与网页资料，统一**固化为知识卡片**并**下载可获取的原始文件**，形成可复用的知识库，供后续所有写作/审核 agent 直接消费。

## 两个生产阶段

1. **分域采集卡片（每个 collector 就地整理）**：行业/竞品/用户三个收集 Agent 在各自搜索完成后，立即把本域关键证据整理为分域知识卡片并落盘，不经过主 Agent 转述，避免传递遗漏。
2. **合并归一（knowledge-curator）**：curator 读取三份分域卡片，按 URL/DOI/标题去重、统一 K01…Kn 编号，产出全量 `knowledge-cards.md` 与 `source-ledger.jsonl`。

分域卡片文件名：

```text
{run_dir}/evidence/knowledge-cards.industry.md
{run_dir}/evidence/knowledge-cards.competitor.md
{run_dir}/evidence/knowledge-cards.user.md
```

## 目录结构（交付目录内）

```
{交付目录}/
├── evidence/
│   ├── source-ledger.jsonl       # 一行一条可核验数据证据
│   ├── knowledge-cards.md        # 知识卡片库（全部卡片，K01…K0n）
│   └── sources/                  # 已下载的原始资料
│       ├── K01_市场规模报告_2026.pdf
│       └── K02_行业数据.csv
```

## 卡片格式（knowledge-cards.md 内，每条一张卡片）

```markdown
## K01｜政策监管动态：金融AI应用规范

- 类型：政策文件                     # 政策文件|行业报告|学术论文|新闻|统计数据|财报|官网/百科
- 主题词：监管、AI应用、数据合规
- 来源机构：国家金融监督管理总局
- 年份：2026
- 本地文件：evidence/sources/K01_金融AI应用规范.pdf   # 已下载；未下载填"未下载"
- 原文链接：https://…
- metric_key：policy_ai_2026               # 同一指标在不同章节/图表复用的键
- source_id：SRC-003                       # 证据台账主键（收集阶段以域+序号临时编号）
- 核心要点：
  - 要点一（≤40 字）
  - 要点二
- 关键数据点：
  - {数值}{单位}——{口径说明}（{基期}，{来源}）
- 解读策略：该数据/事实该怎么读——口径含义、与哪些指标互相印证、使用时的坑（如"全球口径含非目标市场""同比受低基数影响"）
- 使用建议：在正文中的典型写法与适用章节（如"作为一、规模章节的基准值，可与 K03 交叉验证"，给出可仿写示例）
- 反证与边界：数据局限（覆盖范围/年份/方法/样本）、可能推翻本判断的条件
- supports_claim：支持"合规壁垒利好头部"判断 / 反证X
- 章节关联：四、核心驱动力、制约因素与政策环境 / 七、风险提示、结论与展望
```

- 编号连续 K01 起；卡片总数 = 收集结果中去重后的资料来源数（同一 URL 多次引用合并一张）
- 主题词 3-6 个，供 writer 按主题检索
- **关键数据点**：每条含数值/单位/口径/年份——这是后续 writer 引用、（来源，年份）标注、visualizer 数据一致性的直接来源
- **解读策略 / 使用建议 / 反证与边界 是写作 Agent 的解读入口**：writer 必须基于解读策略把每个引用的数据转化为正文论述（含自己的补充解读），不能只搬运数值或只给来源名

## 下载规则（能下载的一律下载）

| 可下载 | 行为 | 命名 |
|--------|------|------|
| 论文 PDF / 报告 PDF / 官方文档 | 下载到 sources/ | `K0X_主题词_年份.pdf` |
| 数据文件（CSV/XLSX） | 下载 | `K0X_主题词.csv/xlsx` |
| 网页/新闻（无文件可下） | 不下载，仅卡片 | — |
| 需要登录/付费/反爬 | 尝试一次失败后标记"未下载+原因"，不纠缠 | — |

下载动作由编排者执行（curator 只产出「待下载清单」）：
```
curl -L --max-time 30 -o "{交付目录}/evidence/sources/K01_主题.pdf" "{url}"
```
下载失败（HTTP 非 2xx / 超时 / 404）→ 卡片保留，本地文件标记"未下载（原因）"；不得伪造下载。

## 拆解与分发（卡片索引）

- 合并后由 `scripts/report/card_index.py` 生成 `evidence/card-index.json`（每卡片实际键：id/title/type/source/year/metric_key/source_id/local_file/supports_claim/interpretation/usage_note/limitation/key_points/data_points/raw/chapter_hint/chapter_hints——与脚本输出一致，勿按旧字段名读取）。`raw` 为整卡原文，`data_points`/`key_points` 为多行要点原文；编排者注入 Writer 提示词时直接粘贴这些原文，不只给文件路径。
- 章节规划（Step 3 开工前）用 `chapter_hints`（多章节数组）把卡片路由到各章：同一卡关联多章时每章各得一份注入，不丢失。
- visualizer 每个数据系列绑定 `card_id` + `source_id`（manifest 条目字段，口径/单位/基期随卡）；`metric_key` 为跨章同名指标辅助索引（供审核核对同指标口径，非 manifest 门禁字段）。
- fact-checker / logic-auditor 以台账与卡片口径核对跨章一致性：`metric_key` 相同的条目口径应一致，不一致需在 reviews 中说明。
- `card_index.py --chapter "四、核心驱动力、制约因素与政策环境"` 可输出该章相关卡片片段（cards.{slug}.md），供 Writer 直接嵌入上下文。

## 联动（卡片被谁消费）

| 环节 | 如何使用 |
|------|---------|
| Step 3 章节规划 | 每章主用数据标注对应卡片 id（Kxx）；`card_index.py --chapter` 按 `chapter_hints` 路由注入 |
| Step 3 writer | 写作时按需 Read evidence/knowledge-cards.md，并从 evidence/source-ledger.jsonl 取关键数据点、（来源机构，年份）标注与参考文献条目 |
| Step 4a 核查 | 优先用 evidence/sources/ 原始文件（Read PDF/CSV）交叉验证卡片数据点；无本地文件才联网验证 |
| Step 3b visualizer | chart-manifest 条目的 card_id/source_id/source/definition/base_period 挂接证据，图数据与卡片一致 |
| Step 4c 逻辑审查 | 术语/数据口径以卡片为准核对 |
| 参考文献 | GB/T 7714 条目由卡片字段直接生成（作者/机构. 标题. 出版者/媒体, 年份. URL） |

## 质量要求

- 卡片内容只记录收集结果中**真实存在**的信息，不扩写、不编造数据点
- 同一来源跨收集结果重复 → 合并一张卡片，交叉时补"多源印证"
- 卡片总数与「数据来源清单」（附录）一一对应，引用即来源
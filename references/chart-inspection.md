# 图表视觉检查规范

图表生成后的质量闸门：**程序化校验（各 fig 脚本内置布局自检的 [WARN] 输出 + 退出码）+ 人工视觉检查（编排者用 Read 工具逐张看图）** 双通道。检查对象是 `charts/` 下的全部 PNG。

## 1. 检查流程

```
Step 3b 生成完成后
   ↓
① 程序化校验：运行每个 `scripts/charts/fig_*.py`，读取其布局自检输出（bbox 重叠/出界/图例/轴标签的 [WARN] 行）；退出码非 0 = FAIL；基于 `gen_chart.py` 工具函数编写的脚本，其自检行同样读取
   ↓
② 视觉检查：用 Read 工具逐张查看 charts/*.png，按下方清单过检；若 Read 返回“模型不支持图像输入”→ 执行第 6 节强制替代流程
   ↓
③ 汇总问题 → 有 Critical 问题 → 重绘（最多 2 轮）→ 仍不合格 → 该图降级并在图表缺口说明记录
```

## 2. 视觉检查清单（逐张过）

### A. 文字与标注
- [ ] **文字重叠**：标题/副题/数据标签/图例/来源说明互相遮挡（程序校验的 WARN 行优先复核）
- [ ] **文本截断**：分类名/数值标签被画布边缘切掉半个字
- [ ] **中文乱码**：出现 □/豆腐块/问号（字体注册失败）
- [ ] 数值标签与柱高/折线点位置相符（标签值 ≠ 视觉高度 → 数字标错）
- [ ] 负号显示正常（非乱码方块）

### B. 布局与可读性
- [ ] **图例**：不遮挡数据区、系列数 ≤5、名称不截断
- [ ] **坐标轴**：类别标签不重叠（长分类名常见）、刻度密度合理
- [ ] 图内无主标题（标题唯一归属正文图名行）；单位/年份/来源（图内底部小字）完整且不与图内容冲突
- [ ] 数据密集时标签不挤成一团（可读性）

### C. 内容与数据
- [ ] 图内数字与注入包卡片/证据台账一致（脚本数据必须来自卡片，以台账口径为准）
- [ ] 颜色区分度：相邻系列颜色可区分（同色相相邻 → 调整）
- [ ] 单位/量纲与图型匹配（百分比图不出现非百分比数值等）

### D. 特殊图型
- 环形图：中心文字不与扇形/标签重叠
- 雷达图：维度标签不重叠、数值轴刻度合理（0-10 评分多轴共用）
- 热力图：色阶图例存在、数值格内文字不溢出格子
- 散点图：象限分割线与标注不重叠、点标签不互相压住

## 3. 问题分级与处置

| 级别 | 定义 | 处置 |
|:----:|------|------|
| 🔴 Critical | 乱码、文字遮挡数据、标签截断、数值标错、图例盖住数据 | **必须重绘** |
| 🟡 Warning | 字号偏小、对比度不足、标签略挤但不误读 | 记录，可不重绘 |
| ✅ 通过 | 无问题 | 进入 Step 3c |

## 4. 重绘流程（编排者派图表编码 Agent 执行；禁止手工 PS、禁止脚本批量改正文）

1. 定位 `charts/chart-manifest.json` 中对应条目（按 `script`/`display_name`）
2. 修改该图脚本（可行手段）：
   - 分类名过长 → 缩短标签 / `notes` 注明全称
   - 标签拥挤 → 减少系列数（合并次要系列进"其他"）
   - 字号/尺寸 → 调整 `figsize`/字号参数或 `dpi`
   - 图例遮挡 → 调整系列名长度、减少系列或移图例到外置
3. 用任务虚拟环境重跑该图脚本，覆盖 PNG；清单字段如有变化（title/position/文件名）同步更新
4. 重新视觉检查该图；**每张图最多 2 轮**
5. 仍不合格 → 派编辑 Agent 从正文移除该图引用（占位与图名行），改用表格/文字表达，清单同步删除条目，并在「图表缺口说明」记录原因

## 5. 边界说明

- 程序化校验是**辅助**：它只能抓 bbox 级问题（重叠/出界/截断类），抓不到画风/对比度/语义错误——必须叠加视觉检查
- 视觉检查策略（提速不降质）：**程序 WARN 图必检 + 每类图型首张必检 + 其余按 30% 抽样**；也可拆 2 个子 agent 各检查一半，检查结论合并写入 `charts/inspection.json`
- 若当前模型无法读图（无视觉能力）：**执行第 6 节强制替代流程**，如实记录 `visual_capability: "unavailable"`；不得把“未执行”写成“通过”
- mermaid 块不在此检查范围（呈现代码块，由 lark-doc 在飞书端渲染；语法问题在质量审核的 mermaid 合法项检查）

## 6. 模型无视觉能力时的强制替代流程（不允许假装通过）

当编排者/检查模型**无法读取图片**（读图被拒、无视觉输入）时，视觉检查降级为下面四步。任何一步都不得跳过，不得把“未执行”写成“通过”：

1. **如实声明**：登记 inspection.json 时写入根字段 `visual_capability: "unavailable"`——`render_visual_check.py --charts-dir … --spec … --out {run_dir}/charts/inspection.json --visual-status pending --capability unavailable`；交付摘要注明“视觉检查=PENDING（人工）”。（schema：根 `checked_at/visual_status/visual_capability/notes`，`charts[]` 每图 `id/file/exists/bytes/status/note`；人工核验可在 charts[] 条目增补 `manual_check`/`checklist`，门禁只认根 `visual_status`。）
2. **代码级 bbox 审计**（正式工具 `scripts/charts/figlib_audit.py`）：
   - 每个 fig 脚本在 savefig 后调用 `from figlib_audit import audit; audit(fig, "图N …")`；
   - 对每个 fig 脚本逐次运行（按实际文件名）：`{task_python} {skill_root}/scripts/charts/figlib_audit.py audit --script {run_dir}/scripts/charts/fig_01_xxx.py`；
   - 输出含 `[FAIL]`（文本/图例/刻度越出画布）→ 修改脚本重跑（每图 ≤2 轮）；`[WARN]`（相邻刻度重叠）记录并优先人工复核。
3. **像素健全性**：`{task_python} {skill_root}/scripts/charts/figlib_audit.py pixel --dir {run_dir}/charts --glob "图*.png"`——非空白、非纯白、尺寸正常；FAIL 视为生成异常需重跑。
4. **拼版图 + 人工检查清单**：`… figlib_audit.py contact --dir {run_dir}/charts --out {run_dir}/charts/_contact_sheet.png`；
   为每张图在 inspection.json 的 charts[] 条目增补 `manual_check: "PENDING"` 与 checklist（预期图题、关键数值、来源、图号、所在章节），由人工对照拼版图/原图逐张确认后，把根 `visual_status` 改为 `passed`（或 `degraded` 并写 notes）；人工未确认前，报告不得宣称“视觉检查通过”。

数值侧兜底：脚本数据必须来自注入包卡片并在头部注释 `# 来源卡片: Kxx (SRC-xxx)`；关键数字可在脚本内断言，与台账口径一致——捕获“画得出来但数值错”一类问题。画风/对比度/语义类问题只能由人工或视觉模型完成。
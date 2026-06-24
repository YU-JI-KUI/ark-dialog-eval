# dialog-eval skill

平安多 BU 对话日志评测 skill,供平安 One(或任何能解析 skill 的 Agent)使用。

## 它解决什么

让 AI 评测对话日志的结果**可信、可被认可**——即使评测者不懂具体业务。核心是一套
「不依赖业务知识也能验证 AI 判断」的方法论(SKILL.md 的四条铁律)。

## 结构

```
dialog-eval/
├── SKILL.md                      # 灵魂:评判方法论 + 流程 + 输出契约(四条铁律)
├── scripts/                      # 确定性脚本(平安 One 调用,不靠 LLM 逐条解析)
│   ├── prepare.py                  Excel → 过滤+会话重组+解析 → 干净样本 JSON
│   └── metrics.py                  AI判断 vs 人工金标 → κ/F1/混淆矩阵(带可信度判定)
└── reference/                    # 各 BU 要调的就是这里(纯文本)
    ├── report_template.md          统一的报告结构与口径
    ├── securities_rubric.md        证券:意图清单 + 可观察解决度判据
    └── life_rubric.md              寿险:意图清单 + 可观察解决度判据
```

## 怎么用(给平安 One)

把整个 `dialog-eval/` 目录作为 skill 提供给平安 One,然后:

> "用 dialog-eval 评测这份证券对话日志 {附 Excel},出一份报告。"

平安 One 会:读 SKILL.md → 加载 securities_rubric → 调 prepare.py 解析 → 逐条按四条铁律评测 → (有金标则)调 metrics.py 算 κ → 按 report_template 出报告。

## 不同 BU 要改什么

只改 `reference/<bu>_rubric.md` 里的**意图清单**和**解决度判据**(纯文本)。
四条铁律、脚本、报告模板都不动。新增 BU = 复制一份 rubric 填内容。

## 脚本依赖

`pandas`、`openpyxl`(prepare)、`scikit-learn`(metrics)。内网走私服安装。

## 与 FastAPI 平台的关系

scripts/ 里的解析与指标逻辑,和 ark-dialog-eval 后端共享同一套实现(同源)。
skill 适合:探索、新格式、临时分析、规则未沉淀阶段;平台适合:每天大批量、要复现、要看板。
评判标准以本 skill 的 SKILL.md + rubric 为唯一事实源,平台逐步对齐。

# Ark 对话评测平台 · 多 BU LLM-as-a-Judge 自动评测流水线

> 一句话:**选 BU(证券 / 寿险)→ 喂日志平台导出的对话 Excel → 系统自动评测 → 产出「BU 分发准确率(含两类错误)+ 端到端解决率 + 优化建议」;有人工金标时额外算 κ/F1 证明结果可信。**

把运营**手动**给对话日志打标(该不该本 BU 承接、答案有没有解决用户、属于什么业务)的工作,做成一条 **LLM-as-a-Judge 自动评测流水线**。核心不是「让模型多聪明」,而是「让模型的判断**可被信任**」——即使评测的人不懂证券 / 寿险业务。

**核心价值**

- **无标注也能评**:不是「必须有人工标注才能对比」。少量标注校准一次,证明 Judge 可信后,放心让它跑海量无标注日志。
- **多 BU 可插拔**:证券、寿险共用同一套流水线骨架,领域知识全封装在 `BUConfig`。新增产险只需加一个配置文件,引擎零改动。
- **外网开发、内网落地**:评测逻辑与模型调用彻底解耦。外网用 mock 桩把逻辑用单测钉死;内网只换一个环境变量切到平安大模型。

---

## 🛣️ 两条使用路线(选哪条?)

项目提供两条路线,**共享同一套解析 / 指标逻辑(同源实现)**,只是承载形态不同。

| | 🅰️ Skill 路线 | 🅱️ FastAPI 平台路线 |
|---|---|---|
| 目录 | `skill/dialog-eval/` | `backend/` + `frontend/` |
| 跑在哪 | 给**平安 One**(内网桌面 Agent,底层 Qwen3.6-35B)直接读 | Web Dashboard(浏览器) |
| 怎么判断 | 平安 One 读 `SKILL.md` 的方法论,逐条按四条铁律判 | 后端程序化调用大模型 / mock 桩 |
| 适合 | **探索期**:规则未沉淀、临时分析、新数据格式、想用对话方式迭代评判标准 | **生产期**:每天大批量、要复现、要看板、要断点续跑 |
| 形态 | `SKILL.md`(灵魂)+ `scripts/`(确定性脚本)+ `reference/`(各 BU rubric) | REST API + React 看板 + SQLite 落盘 |

**怎么选**

- 刚拿到一份新格式日志、规则还没和业务方对齐 → 走 **Skill**。把 `skill/dialog-eval/` 整个目录交给平安 One,用「对着 case 聊」的方式把业务方脑子里的隐性规则钓进 `reference/*_rubric.md`(详见 `skill/dialog-eval/ROADMAP.md` 的从 0 到 1 路线)。
- 评判标准稳定了、要每天跑几万行、要给团队一个可点的看板 → 走 **平台**。

> **两条路线的事实源关系**:评判标准以 skill 的 `SKILL.md` + `reference/*_rubric.md` 为唯一事实源;平台侧的 `BUConfig` 与之逐步对齐(意图清单两边各有一份副本,改一处要同步另一处,代码里已加 ⚠️ 交叉提示)。

---

## 🎯 评测做什么(最新口径)

> ⚠️ 这是项目经过多轮演进后的**最新口径**。早期的「意图分发对不对」已升级为下面的「**BU 分发漏斗**」,请以此为准。

整个评测是**一个漏斗**:

```
全部样本 N 条
  │
  ├─ 维度① BU 分发评测(对全部 N 条)
  │     LLM 判:这个问题(结合上下文)该不该由【本 BU(如证券)】承接?
  │       · 该承接   → 期望日志「分发BU = 本BU」
  │       · 该拒识   → 期望日志「分发BU ≠ 本BU」
  │     与日志事实比对 → 分发对 / 错 → 算 BU 分发准确率 + 两类错误
  │
  └─ 维度② 端到端解决度(★只评「分发BU = 本BU」的子集 —— 漏斗)
        · 维度③ 给问题打业务类型标签(只切片,不判分类对错)
        · 判答案是否解决用户,没解决给原因
        → 每个业务类型的解决率 + 整体端到端解决率 + 未解决原因聚类
```

### 三个维度

| 维度 | 判什么 | 评测范围 | 真值来源 |
|------|--------|----------|----------|
| **① BU 分发** | LLM 判「该不该本 BU 承接」(`should_dispatch_to_bu`),与日志「分发BU」比对 | **全部样本** | 日志「分发BU」列 = 是否分给本 BU |
| **② 端到端解决度** | 答案是否解决用户(`yes/partial/no/unknown`),没解决给原因 | **仅「分发到本BU」的子集** | 无真值,靠可观察代理信号 |
| **③ 业务类型** | 打一个业务类型标签 | 仅子集 | **无真值,只切片不判对错** |

**口径锁定(不可漂移)**

- **「拒识」= 日志「分发BU」列的值不代表本 BU**(空 / 其他 BU),**不是某个意图类别**。
- **BU 分发准确率**由代码算,不是 LLM 给:把 LLM 的 `should_dispatch_to_bu`(该不该承接)与日志事实 `dispatched_to_bu`(是否真的分给了本 BU)比对,一致即正确。
- **两类错误**:
  - **漏收**(`miss_should_accept_but_rejected`):LLM 说该承接,日志却拒识了 → 本应承接却被拒。
  - **误收**(`over_should_reject_but_accepted`):LLM 说该拒识,日志却承接了 → 他业务问题被本 BU 错收(如「手机充值」被分进证券)。
- **解决率分母 = 只算「分发到本BU」的样本**(拒识 / 分错的不进分母)。这是「端到端漏斗口径」:既要分对,又要答好。

### 产出物

1. **BU 分发准确率** + 漏收 / 误收两类错误计数。
2. **每业务类型的端到端解决率** + 整体端到端解决率。
3. **未解决原因聚类**(答非所问 / 信息不全 / 事实存疑 …)。
4. **优化建议**(作用域 / 严重度 / 根因 / 动作 / 依据;有模型走模型,无模型走规则兜底)。

### 两种模式(系统自动判定)

| 模式 | 触发条件 | 额外产出 | 频率 |
|------|----------|----------|------|
| **校准模式** | 数据里有人工金标列且含「是/否」实际值 | 对二值金标算 **准/召/F1 + 混淆矩阵 + Cohen's κ** | 低频(证明可信那一次) |
| **生产模式** | 无可用金标 | **不需人工标注**,Judge 直接出洞察 + 建议 | 高频(每天的海量日志) |

> **逻辑链**:先用少量标注算 κ 证明 Judge 够准(κ ≥ 0.6 可信,≥ 0.8 高度一致)→ 信任它 → 放心让它跑海量无标注数据。**生产模式根本不需要金标**,金标只在校准那一次用。模式由 `pipeline.detect_gold()` 自动判定:不只看金标列存不存在,还看列里有没有实际的「是/否」值。

---

## 🏢 多 BU 扩展

证券和寿险共用**流水线骨架**(过滤 → 会话重组 → 答案解析 → Judge → 洞察 → 建议),不共用的是**领域知识**。这些被抽成可插拔的 `BUConfig`(`backend/app/core/bu/`)。

> Java 类比:`BUConfig` 是领域**策略对象**(Strategy Pattern),引擎是上下文,运行时按上传选择的 BU 注入对应策略。

### BUConfig 的 5 个可配项

| 字段 | 作用 | 例(证券) |
|------|------|-----------|
| `judge_persona` | Judge 的系统角色话术(专家身份) | 「你是平安证券对话系统的评测专家…」 |
| `intents` / `groups` | 业务分类清单 + 定义 + 所属业务大类 | 13 类:交易 / 查持仓 / 问诊股 / 拒识 … |
| **`dispatch_aliases`** | **日志「分发BU」列里代表本 BU 的取值(可多个)** | `("证券", "证券业务")`,真实环境可补 `"PA_SEC"` |
| `mock_intent_rules` / `mock_module_map` | mock 桩用的关键词规则(仅 mock 后端用) | `["持仓","盈亏"] → "查持仓"` |
| `sample_calib` / `sample_prod` | 内置样例文件名 | `pa_dialog_eval_sample.xlsx` |

### ⭐ `dispatch_aliases` 是关键

真实日志「分发BU」列里的值,**常常不是中文展示名**(可能是 `PA_SEC` 这种内部代码)。`dispatch_aliases` 就是把「这一列里哪些值代表本 BU」配置化:

```python
# backend/app/core/bu/securities.py
SECURITIES = BUConfig(
    code="securities",
    name="证券",
    dispatch_aliases=("证券", "证券业务"),  # ← 拿到真实日志后,在这里补实际列值,如 "PA_SEC"
    ...
)
```

判定逻辑(`base.py` 的 `matches_dispatch`):配了 `dispatch_aliases` → 精确相等匹配(最安全);没配 → 回退到「展示名子串匹配」(兼容旧数据)。**真实日志列值≠展示名时,只改这一个 tuple,不用碰任何通用代码。**

### 新增一个 BU(如产险)只需 3 步

1. **加配置**:复制 `backend/app/core/bu/securities.py` → `property_insurance.py`,填入产险的 5 个字段(`code="property"`、意图清单、`dispatch_aliases`、mock 规则、样例文件名)。
2. **登记一行**:在 `backend/app/core/bu/registry.py` 的 `_REGISTRY` 里加 `PROPERTY.code: PROPERTY`。
3. **加 rubric**(skill 路线用):复制一份 `skill/dialog-eval/reference/property_rubric.md`,填该 BU 的意图清单与解决度判据。

**引擎、Judge、指标、建议、前端选择器全部零改动**——它们都通过 `bu` 参数拿领域知识。

> 寿险意图体系目前是**按常见业务设计的合理占位**(保单查询 / 理赔 / 缴费 / 保全 …)。拿到真实意图标注文档后,替换 `life_insurance.py` 的 `_INTENTS` / `_GROUPS` 即可,无需动其他代码。

---

## 🧱 关键设计原则(为什么这么设计)

### 1. 评测逻辑与模型调用彻底解耦

这是「外网开发、内网落地」能成立的前提:

```
┌──────────────────────────────────────────────────────────┐
│  评测逻辑层(纯确定性 Python,任何环境可 100% 验证)         │
│    样本过滤 · 会话重组 · 答案JSON解析 · 指标κ/F1 · 不一致导出 │
│                          │                                 │
│            ── 唯一边界:judge_one(sample, bu) ──            │
│                          ▼                                 │
│  模型调用层(仅这一层依赖内网)                              │
│    mock  : 内置规则桩,无需模型即可端到端跑通(默认)        │
│    pingan: 平安内网大模型(双签名鉴权,改一个环境变量切换)   │
└──────────────────────────────────────────────────────────┘
```

Java 类比:评测逻辑是 `Service` 层,模型调用是注入的 `LLMClient` 接口。开发期注入 `MockLLMClient`(规则桩)把整条链路跑通 + 单测覆盖;内网把实现换成 `PinganLLMClient`,**Service 层一行不动**——只改环境变量 `JUDGE_BACKEND=pingan`(见 `app/core/llm/judge_runner.py` 的 `judge_one`)。

### 2. 会话重组:每轮一条带上下文的样本

日志是逐轮的平铺行。流水线按「应用会话ID」分组、按「客户咨询轮次」排序,把每一轮还原成一条样本,并拼上**前文上下文**(`context`)。关键:`context` 不只含前文用户问,还含**前文 AI 的回答**(同样经过答案解析)。

> **为什么**:多轮里当前问题常**指代上一轮 AI 的答案**。例:第 1 轮「我的持仓」→ AI 返回列表(1. 平安银行 2. 贵州茅台 …);第 2 轮「详细说一下**第二个**的走势」。不带上一轮 AI 答,judge 判不出「第二个」= 贵州茅台。单轮 / 多轮统一走这套重组(单轮 = `context` 为空的样本)。

### 3. 数据边界(铁律六):禁止「数据穿越」

被评测的 agent(线上当时)和做评测的你(事后复盘)信息边界不同,不能混:

| 判断维度 | 允许看 | 禁止看 |
|----------|--------|--------|
| 意图 / 分发(①③) | 当前轮 + `context`(前文) | ❌ `next_user_turn`(未来) |
| 答案解决度(②) | 当前轮 + 答案 + **`next_user_turn`** | — |

`next_user_turn`(用户下一轮)只用来评「上一轮的效果」,**绝不能用于反推意图 / 分发**(agent 当时还不知道用户下一轮会说什么)。

### 4. 可信方法论的四条铁律(skill `SKILL.md` 的灵魂)

让评测**不依赖评测者的业务知识**也能可信:

1. **每个判断必附「依据」**:每个 yes/no/对/错,都要给一句基于对话本身可观察事实的依据(`*_reason`)。没有依据的判断视为无效。
2. **解决度靠可观察代理信号**:只看相关性 / 完整性 / 下游轨迹(用户下一轮重问、转人工、不满 → 倾向 no/partial),不靠业务对错。
3. **不判业务事实**:没有知识库,prompt 不让模型判金额/条款/对错这类业务事实;涉及事实的疑点直接转人工。
4. **不确定就转人工**:意图置信低 / 需核事实 / 疑似合规 / 拿不准 → `needs_human_review=true`。目标是「只让人看难的那部分」。

---

## 🚀 快速开始(本地 / 外网,mock 零配置)

前置:`uv`(Python 包管理)、`node ≥ 18`。**mock 后端无需任何模型,开箱即跑。**

```bash
# 1) 后端依赖
cd backend && uv sync

# 2) 生成内置样例数据
uv run python scripts/make_sample.py            # 证券小校准集(13 行,有金标,逐条精心构造)
uv run python scripts/make_large_sample.py      # 证券+寿险 各 3000 行生产集 + 2000 行校准集

# 3) 前端依赖
cd ../frontend && npm install

# 4) 一键起前后端(回到项目根)
cd .. && ./dev.sh
```

打开 **http://127.0.0.1:5234**,选 BU(证券 / 寿险),点「用内置样例一键体验」即可看到完整评测流程,无需任何模型。

- 前端开发地址(热更新):**http://127.0.0.1:5234**
- 后端 API 文档(Swagger):**http://127.0.0.1:8848/docs**

### 只想跑命令行(不开 Web)

```bash
cd backend
# 对证券校准集跑评测并打印 κ/F1
uv run python -m scripts.run_calibration data/sample/pa_dialog_eval_sample.xlsx

# 指定 BU、并导出不一致 case
uv run python -m scripts.run_calibration data/sample/life_dialog_calib.xlsx --bu life --export 不一致.xlsx
```

Web 和 CLI 共用同一套评测引擎,结果一致。

---

## 🏢 内网部署(平安环境,有 npm + uv)

工作流:**外网写码 → push → 内网 `git pull` → 内网一键启动**。内网自带 npm、uv,无需在外网预编译——脚本现编译现起。**一个脚本搞定:编译前端 → 后端单进程托管 dist + API**,本地不用单独开前端。

### 一键启动(推荐)

```bash
./start.sh            # 默认 0.0.0.0:8848:编译前端 → uv 装依赖 → 起后端(已挂 dist)
./start.sh 9000       # 指定端口
```

脚本做三件事:① `npm ci && npm run build` 编译前端到 `frontend/dist` → ② `uv sync` 装后端依赖 → ③ `uvicorn` 起后端。后端 `app/main.py` 检测到 `frontend/dist` 存在就自动托管(前端 + API **同源单进程**,无跨域,无需常驻 node 进程)。打开 `http://<本机IP>:8848` 即用。

> 依赖走内网私服时,uv/npm 各自配好源即可(uv:`--index-url http://maven.paic.com.cn/repository/pypi/simple`)。
> 首版用 `JUDGE_BACKEND=mock` 零配置就能跑通看效果;接平安大模型见下方「配置凭据」。

### 配置平安大模型凭据

```cmd
copy backend\.env.sample backend\.env
```

编辑 `backend\.env`,把后端切到平安模型并填入科技网关 + 应用申请的凭据(变量名与 `ark_navigator` 一致,便于复用同一套凭据):

```ini
JUDGE_BACKEND=pingan
JUDGE_CONCURRENCY=4

OPEN_AI_URL=http://eagw-gateway-sf.paic.com.cn:80/pingan/bigModel/api/v1/chat/completions
RSA_PK=...            # RSA 私钥(十六进制)
CRE_ID=...
OPEN_API_CODE=...
LLM_APP_KEY=...
LLM_APP_SECRET=...
LLM_SCENE_ID=...
LLM_TIMEOUT=30
LLM_MAX_RETRIES=3
```

> 平安变量不全时,`active_backend()` 会自动降级回 mock(`pingan_ready()` 检查 7 个必填项),不会硬崩。

### 4. 内网验收清单(按序验,精确定位问题)

| 步骤 | 命令 | 验证什么 | 失败说明 |
|------|------|----------|----------|
| ① 逻辑 | `uv run pytest` | 评测逻辑(36 测试) | 与模型无关,逻辑被环境带坏 |
| ② 流水线 | `uv run python -m scripts.run_calibration data/sample/pa_dialog_eval_sample.xlsx` | mock 全链路接线 | 流水线编排问题 |
| ③ **签名** | `uv run python scripts/check_pingan.py` | **签名能否过网关 + 模型应答能否解析** | 凭据 / 端点 / scene_id 授权 |
| ④ 真实 | 配好 `JUDGE_BACKEND=pingan` 后跑校准 | 真实模型 JSON 能否被正确解析 | 模型输出格式不符 → 调 prompt |
| ⑤ 看 κ | 看校准输出的 κ | 真实数据校准数字 | κ 低 → 改意图定义 / prompt 迭代 |

> ①② 在外网已验证通过;**③ 往后才是内网独有的**。`check_pingan.py` 会把「网络 / 凭据 / 签名」问题和「评测逻辑」问题彻底隔离,逐步打印每一步结果。
>
> **`dispatch_aliases` 提醒**:跑真实数据前,先看一眼真实日志「分发BU」列的实际取值,在对应 BU 的 `dispatch_aliases` 里补上(如 `PA_SEC`),否则维度① 会因列值≠中文展示名而漏判。

### 手动启动(备选,等价于 start.sh 的第 1、3 步)

若想分步执行或不重新编译前端:

```bash
cd frontend && npm run build && cd ..   # 编译前端(dist 已存在可跳过)
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8848
```

打开 `http://<本机IP>:8848`(前端由后端托管,API 同源)。

> **大数据量保障**:任务逐批落盘 SQLite,跑一半中断可**断点续跑**(`POST /api/eval/tasks/{id}/resume`,跳过已完成行)。所有样本一律走真实大模型精判,不做快层粗筛——要的是评测准确性,夜间用自有推理服务跑,机器空闲不算浪费。

### 6. Skill 路线的内网交付

走 skill 路线时,把 `skill/dialog-eval/` **整个目录**作为 skill 提供给平安 One,然后对它说:

> 「用 dialog-eval 评测这份证券对话日志 {附 Excel},出一份报告。」

平安 One 会:读 `SKILL.md` → 加载对应 `reference/<bu>_rubric.md` → 调 `scripts/prepare.py` 解析(过滤 + 会话重组 + 答案解析)→ 逐条按四条铁律评测 →(有金标则)调 `scripts/metrics.py` 算 κ → 按 `reference/report_template.md` 出报告。脚本依赖 `pandas`、`openpyxl`(prepare)、`scikit-learn`(metrics),内网走私服安装。真实日志「分发BU」列值非中文时,用 `prepare.py --dispatch-alias 证券 --dispatch-alias PA_SEC` 传入。

---

## 📁 目录结构

```
ark-dialog-eval/
├── backend/
│   ├── app/
│   │   ├── core/bu/                 # ⭐ BU 领域知识层(可插拔)
│   │   │   ├── base.py                 BUConfig 抽象 + matches_dispatch(dispatch_aliases 判定)
│   │   │   ├── securities.py           证券 BU(13 类意图)
│   │   │   ├── life_insurance.py       寿险 BU(12 类意图,占位待替换)
│   │   │   └── registry.py             BU 注册表(新增 BU 登记一行)
│   │   ├── core/eval/               # 评测引擎(纯逻辑,与模型/BU 无关)
│   │   │   ├── answer_parser.py        答案 JSON 渲染卡 → 语义文本(两种 schema + HTML 容错)
│   │   │   ├── judge.py                Judge prompt 构造(注入 BU 意图,新口径契约)+ 输出解析
│   │   │   ├── pipeline.py             列解析 / 过滤 / 会话重组 / 模式判定 / dispatched_to_bu
│   │   │   ├── metrics.py              准召F1 + Cohen's κ + 混淆矩阵
│   │   │   └── advisor.py              优化建议(prompt 构造 + 规则兜底,含两类错误建议)
│   │   ├── core/llm/                # 模型调用层(唯一依赖内网)
│   │   │   ├── signature.py            平安双签名(RSA-SHA256 + HMAC-SHA1)
│   │   │   ├── pingan_client.py        平安大模型客户端
│   │   │   ├── mock_judge.py           规则桩 Judge(产 should_dispatch_to_bu 等新契约字段)
│   │   │   └── judge_runner.py         调度入口 judge_one(mock/pingan)+ 建议生成
│   │   ├── services/                # 任务编排
│   │   │   ├── evaluator.py            双模式评测 + BU 分发漏斗 + 业务洞察 + 断点续跑
│   │   │   ├── task_manager.py         任务管理(SQLite backed)
│   │   │   └── store.py               SQLite 持久化(任务 + 逐条结果)
│   │   ├── api/routes.py            # REST 接口(upload/sample/tasks/result/export/meta)
│   │   ├── config.py               # 配置(环境变量 / .env)
│   │   └── main.py                 # FastAPI 入口(含前端 dist 托管)
│   ├── scripts/
│   │   ├── make_sample.py             证券小校准集(逐条精心构造,覆盖各 schema/失败 case)
│   │   ├── make_large_sample.py       大数据样例(各 BU 生产集 + 校准集,可控注入错误率)
│   │   ├── check_pingan.py            内网单条试水(验收第 ③ 步)
│   │   └── run_calibration.py         命令行校准入口
│   ├── tests/                      # 36 个单元/契约测试
│   └── .env.sample
├── frontend/                       # React + Vite + Tailwind v4 + Recharts
│   ├── src/components/             # BU选择器/上传/进度/指标卡/洞察表/建议卡/图表/明细表/详情抽屉
│   └── dist/                       # 构建产物(后端托管;外网构建后带进内网)
├── skill/dialog-eval/              # ⭐ Skill 路线(给平安 One)
│   ├── SKILL.md                       灵魂:四条铁律 + 三维度漏斗 + 输出契约
│   ├── ROADMAP.md                     从 0 到 1 落地路线图(给"不知从哪开始"的人)
│   ├── README.md                      skill 使用说明
│   ├── scripts/                       与后端同源的确定性脚本
│   │   ├── answer_parser.py
│   │   ├── prepare.py                 Excel → 干净样本 JSON(支持 --bu / --dispatch-alias)
│   │   └── metrics.py                 校准 κ/F1 + 新口径 aggregate(BU分发+解决度漏斗)
│   └── reference/                     各 BU 评判细则(纯文本,事实源)
│       ├── report_template.md         统一报告结构与口径
│       ├── securities_rubric.md       证券:意图清单 + 承接判据 + 解决度判据
│       └── life_rubric.md             寿险:同上
├── start.sh                        # 内网一键:编译前端 + 后端单进程托管(推荐)
├── dev.sh                          # 本地分离开发:同时起前后端(热更新)
├── build.sh                        # 仅构建前端产物
└── README.md
```

---

## 🗂️ 字段映射(Excel 关键列 → 评测角色)

日志平台导出列 + 运营人工标注列。系统用「**列名精确匹配优先,再退化到包含匹配**」自动定位(`pipeline.resolve_columns`),兼容细微差异。关键列:

| 角色 | 列名 | 作用 |
|------|------|------|
| 评测输入 | `客户问题` / `答案` | 用户问 / **AI 答(JSON 渲染卡,需先解析)** |
| 会话主键 | `应用会话ID` / `客户咨询轮次` | 会话重组的分组键 + 排序键 |
| **BU 分发事实** | **`分发BU`** | **日志把这条分给了哪个 BU。经 `dispatch_aliases` 判定是否 = 本 BU → `dispatched_to_bu`(维度① 的真值)** |
| 系统预测(辅助) | `模型意图` / `智能体分类` / `分发BU理由` | 系统识别到的意图 / 承接模块 / 分发理由 |
| 人工金标(可选) | `分发是否正确` / `一键场景分发是否正确` / `答案是否解决客户问题` | 校准模式算 κ/F1 的真值(有「是/否」才触发校准) |
| 过滤 | `日志环境` / `是否测试账号` / `当前问题是否有效` | 剔除测试环境 / 测试账号 / 无效问题 |

> **`分发BU` 列的新作用(最新口径核心)**:这一列是维度① 的真值来源。它的值经 `BUConfig.dispatch_aliases` 判定是否代表本 BU,得到每条样本的 `dispatched_to_bu`(bool)。真实日志这一列的值若不是中文展示名(如 `PA_SEC`),**在对应 BU 的 `dispatch_aliases` 里补一个取值即可**,不用碰通用代码。

---

## 🧪 测试

```bash
cd backend && uv run pytest -q     # 36 passed
```

覆盖(`tests/` 8 个文件 36 个用例):

- **答案解析**两种 schema(活动权益卡 / FAQ 双层嵌套 + HTML)+ 容错兜底。
- **列解析**精确匹配优先(防「答案」误命中「标准问答案」这类含子串列的串列回归)。
- **会话重组**(context 带前文 AI 答)、**模式自动判定**(空标注列不算金标)。
- **指标**计算与混淆矩阵方向、**Mock Judge** 规则、**建议解析容错**(模型吐脏 JSON 也能救回大部分建议)。
- **BU 抽象**(registry / dispatch_aliases 匹配)、**业务洞察聚合**(BU 分发漏斗两类错误)、**评测逻辑契约测试**——证明「只要模型按约定格式返回,评测链路就一定算对」,与模型好坏 / 连通性无关。

---

## ⚙️ 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · uv · pandas · scikit-learn · httpx · pycryptodome / cryptography(双签名) · SQLite |
| 前端 | React · Vite · Tailwind v4 · Recharts |
| 模型 | mock 规则桩(默认)/ 平安内网大模型(底层 Qwen3.6-35B,双签名 RSA + HMAC 鉴权) |
| Skill | 纯 Python 确定性脚本(`pandas`/`openpyxl`/`scikit-learn`)+ markdown 方法论 |

---

## ⚠️ 已知缺口(诚实标注)

> 把边界明明白白写出来,比假装全能更让人信任。

| 缺口 | 现状 | 怎么补 |
|------|------|--------|
| **寿险意图是占位** | `life_insurance.py` / `life_rubric.md` 的 12 类意图是按常见业务设计的合理框架,非真实标注 | 拿到真实意图标注文档后,替换 `_INTENTS`/`_GROUPS`(代码侧)+ rubric 表(skill 侧),引擎不动 |
| **真实「分发BU」值需配 `dispatch_aliases`** | 当前别名是中文展示名(`"证券"`/`"证券业务"`等);真实日志列值可能是内部代码 | 拿到真实日志后,在对应 BU 的 `dispatch_aliases` 里补实际取值(如 `"PA_SEC"`) |
| **分错时「正确意图」无真值** | Excel 没有一列记录「分错时本应分到哪个意图」,维度③ 只切片不判分类对错 | 业务方复核不一致 case 时顺手补「本应分到 X」(见 `ROADMAP.md` §4) |
| **事实正确性不判** | 无知识库,涉及金额 / 条件 / 条款对错的一律不判,有疑点转人工(铁律三) | 接入业务知识库后才可放开,当前刻意不碰 |
| **真实模型未实测** | judge.py 的 prompt 与输出契约已对齐新口径(`should_dispatch_to_bu`/`business_type`),但只在 mock 下验证过,真实 Qwen 应答格式需内网实测 | 内网验收第 ③④ 步用 `check_pingan.py` + 小批量校准实测,不符再调 prompt |

# RookieQ-行业分析工作台

一个**单文件、零依赖**的网页应用，用于对一个行业做结构化拆解与「从业者视角」拷问，并输出带**证据分级（A/B/C）**的分析报告。直接调用 Anthropic Messages 兼容的流式 API。

> 纯原生 HTML/CSS/JS，无构建步骤、无第三方库、无前端框架。配合一个极简的本地代理 `server.py` 即可解决浏览器跨域（CORS）问题。

**写在前面**：

+ 因为阴差阳错歪打正着的种种原因，我初次实习的行业在先前并没有专门接触了解过，对很多行业的细节一知半解，就算面对热情帮助的同事伙伴，往往又可能不知从何问起，或者问题细碎而繁杂也多少有点不好意思太过麻烦人家抓着问。
+ 所以其实像是这个demo，我的本意就是希望刚刚进入某一个特定行业的人，能够快速地对自己的行业有一个初步的认知，并且能够在“老炮”们看似刻薄但直击要害的拷问下对行业产生更深的理解（拷问环节的设置由来）。
+ 另外，大模型并不是完全准确的，所以其实这个工具的更深一层意义，还是希望让人在能够稍微言之有物一点的情况下，更好地更有效率地和同事沟通交流，知道问题的关键，当然了，也包含我本人的一点恶趣味——就是当你接受了重重拷问之后，想必看身边的哪个同事都会感到如沐春风了:-D

---

## ✨ 功能特性

- **五步固定分析流水线**（Step 0 → Step 4 → Step 5），按预设 prompt 链串行推进：
  - Step 0 · 边界切分（先给出若干候选行业边界，由你选定后再下钻）
  - Step 1 · 结构层（产业链/参与者/价值分布）
  - Step 2 · 三条流转链（信息流 / 资金流 / 物流）
  - Step 3 · 议价能力（谁卡谁脖子）
  - Step 4 · 约束 / 节奏 / 异常
  - Step 5 · 从业者拷问（多轮对话，逼问报告里「心虚」的字段）
- **证据分级**：正文中每段标注 `A / B / C` 档，C 档不得进正文，只能进结尾「待验证清单」。
- **流式输出（SSE）**：逐字渲染，支持「停止」随时中止。
- **即时诊断**：点「停止」后，基于已有内容立即生成「诊断报告（从业者视角）」独立卡片（四部分：空栏清单 / 外行用语 / 优先补的 3 块知识 / 你还不知道的 10 件事）。
- **轮数实时可调**：Step 5 的拷问轮数可在运行中随时修改（设置面板或卡片内输入框，1–50 轮），到达目标轮数自动收尾并出诊断。
- **导出 .md**：一键把全流程（含诊断卡片）导出为 Markdown 文件。
- **设置持久化**：API 地址 / Key / 模型 / 认证方式 / 代理开关 / 轮数等保存在浏览器 `localStorage`，下次免填。
- **输入框回车即开始**：在顶部行业输入框按 Enter 等同点击「开始分析」。

---

## 📁 目录结构

```
aiIndustryAnalysis/
├── index.html     # 主应用（单文件，含全部 UI / 逻辑 / prompt）
├── server.py      # 本地代理：托管静态文件 + 转发 API 请求并注入 CORS 头
├── start.bat      # 一键启动脚本（Windows，双击运行）
└── README.md      # 本文档
```

---

## 🔧 环境要求

- **Python 3.7+**（仅 `server.py` 需要，用于本地代理；若关闭代理直连上游则不需要）
- 现代浏览器（Chrome / Edge / Firefox）
- 可用的 AI 网关 API Key（默认已预填越秀网关 Key，可在设置中更换）

---

## ⚙️ 设置面板说明

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| API Base URL | `https://yourapi/v1` | 网关地址（不含 `/messages` 后缀，代理会智能拼接） |
| API Key | 自行填写 | 仅存于浏览器 localStorage，不离开本机 |
| 模型 | `deepseek-v4-pro` | 按网关支持的模型 ID 填写 |
| 认证方式 | 自动 | `auto`：官方用 `x-api-key`，三方用 `Bearer`；可强制 `Bearer` |
| 检索工具 (web_search) | 关闭 | 开启后标 A 档需先检索核实；若网关不支持，会自动降级为「最高 B 档」 |
| 使用本地代理 | 开启 | 关闭则直连上游（需上游支持 CORS） |
| 拷问轮数 | 15 | Step 5 目标轮数，范围 1–50，可运行中途改 |

> 切换三方中转平台时：把地址改成中转地址、认证方式选「强制 Bearer」、模型 ID 用中转平台要求的写法即可。

---

## 🧭 分析流程与产物

1. **Step 0 边界切分**：模型给出 2–4 个候选行业边界（如「跨境电商-出口 B2C」vs「跨境电商-进口保税」），你在卡片内选择其一，后续步骤才真正下钻。
2. **Step 1–4 串行分析**：每步一张卡片，流式输出，正文强制带 `evidence: A/B/C` 标注。
3. **Step 5 从业者拷问**：多轮对话，模型扮演「在这个行业干过 10 年的老手」反问你，专挑报告里 B/C 档与「未获取」的栏猛攻；轮数一到自动收尾。
4. **诊断报告**（独立卡片）：四部分自包含输出，附完整性校验（过短会提示「重试诊断」）。
5. **导出**：「导出 .md」把全部卡片（含诊断）合并为一份 Markdown。

### 证据分级规则（摘要）

- **A** = 已核实（有公开出处 / 检索到具体文件）。开启 web_search 时须写出文件名+年份。
- **B** = 行业常识推断，必须写出推断链条（从已知事实经什么逻辑推到结论）。无检索工具时最高只能到 B 并注明「凭记忆，未核实」。
- **C** = 纯推测，一律不进正文，只进结尾「待验证清单」。

---

## 📝 技术要点

- **网关兼容**：同时兼容官方 `x-api-key` 与三方 `Bearer`；URL 智能拼接（避免 `/v1` 重复）；参数 400 时自动剥离 `tools / cache_control / web_search` 降级重试。
- **SSE 解析**：完整处理 `message_start / content_block_* / message_delta（含 usage）/ message_stop / ping`；该网关把 `input_tokens` 放在 `message_delta`，已适配。
- **断流与续传**：支持 `stop_reason` 分支（refusal / max_tokens / end_turn）、断流重试 + 快照回滚、`pause_turn` 续传。
- **代理转发**：`ThreadingHTTPServer` 多线程（避免被浏览器 preconnect 空闲连接卡死），流式 SSE 边读边写（4KB chunk），并注入 `Access-Control-Allow-Origin: *`。

---

## 📊 度量与评估（无真实用户样本也可复现）

简历要求补充「试点用户数 / 报告可信度评分 / 纠错量」。本工作台采用**双模态统一幻觉治理评估基准**：
覆盖「无检索 / 有检索」两种模型，分别测试幻觉治理的两个失败模式——

- **无网模型（消融基线 `--live`）**：不能联网，只能靠 B/C/「未获取」。脚本强制 A 档降为 B（避免模型用记忆冒充「已核实」），并关闭 URL 加成 → 无网 A 档占比恒为 0。测「不知道却编造事实」→ 看 Tier B 弃答率、Tier A 事实准确率。
- **有网模型（主结果 `--live --web`）**：可联网检索，A 档应带真实出处链接。测「编造引用 / 假出处」→ 额外算**引用真实率**（独立抓取核验，钳制 citation hallucination）。

两模态正好覆盖幻觉的两大模式，构成简历里 **main + ablation** 的严谨叙事。
经 `verify_gateway.py` 实测，本项目网关 `aigw.yuexiuproperty.cn`（deepseek-v4-flash，底层 SGLang）
**不支持 web_search**，故当前 key 走「无网基线」；后续补上联网模型后加 `--web` 即得主结果。

### GOLDEN 评测集（domain，**180 题**，来自 `domain_golden_210_v1-180test.csv`）

**主测试集为 CSV 驱动**，换题集无需改代码：`--golden-csv <file>` 或环境变量 `AI_GOLDEN_CSV`
（列：`id,domain,tier,trap_type,question,expected_answer,key_correction,scoring_notes`）。
CSV 不存在时自动回退内置题集。

| 层 | 题数 | 测什么 | 正确行为 | 对应标准评测概念 |
| --- | --- | --- | --- | --- |
| **Tier A 可回答事实** | 60 | 事实准确率 / 幻觉率 | 答对应事实 | 闭卷事实基准（SimpleQA / CMMLU） |
| **Tier B 不可回答** | 60 | 弃答率 / 不确定性披露 | 标 C/未获取（不编造） | 弃权与不确定性披露（IPIPP unanswerable） |
| **Tier C 对抗误区** | 60 | 抗误区率(truthful rate) | 识破错误前提+给结论+指纠偏 | 抗误区率（TruthfulQA） |

分层结构：6 行业 × 30 题（跨境电商 / 工业软件 / 社区团购 / 储能 / 宠物医疗 / SaaS CRM）。
Tier C 的 `trap_type` 分布：绝对化 18 / 因果跳跃 14 / 概念偷换 13 / 条件遗漏 15。

Tier A 采用**双轨判分**：规则锚点子串（免费、完全可复现）+ 可选 LLM 判定
（SimpleQA grading 口径，容忍同义表述与缩写展开）。两者都输出、可互相印证——
CSV 中不少期望答案是短语（如「在目标市场提前备货并提供仓储、分拣、履约等服务」），
纯子串比对会因表述差异误判，故以 judge 为准、规则作对照。

#### Tier C / TruthfulQA 的判分来源（三级优先）

判分拆三步：**① 拒绝错误前提 ② 给出正确结论 ③ 指出纠偏点**，三点全满足才计通过。
**不采用朴素子串匹配**——只回答一个「否。」会判 `explain=0` 而整题失败（抗误区 ≠ 猜否定词）。

| 优先级 | 来源 | 启用方式 | 可信度 |
| --- | --- | --- | --- |
| ① | **人工抽检** | `--export-human` 导出评分表 → 打勾回填 → `--human-grades` | 最高，可直接写简历 |
| ② | **独立网关 LLM judge** | `--judge-base-url` + `--judge-model`（推荐异族模型） | 高，破除同模型护短 |
| ③ | 规则兜底 | 自动降级 | 仅作兜底 |

**没有更强模型也能报数**：关键在 `--human-grades`。人工批改一批题后，脚本会额外算出
**judge 与人工的一致率（judge–human agreement）**——一致率高，就证明 judge 可信，
可以放心用它判全量 42 题；一致率低，则只报人工批改过的那部分。这把「judge 强不强」
的争论，转成了「judge 与人工是否一致」这个**可量化、可验证**的问题。

### 标准 backbone（`--standard`，方案1：对齐权威公开基准）

| 基准 | 题数 | 测什么 | 判分 |
| --- | --- | --- | --- |
| **CMMLU**（中文多选） | 50 | 事实准确率 | 确定性（零语言偏差） |
| **TruthfulQA**（对抗误区） | 30 | 抗误区率 | LLM-as-judge |

数据来自方案1 抓取的真实切片 `_golden_standard.json`（CMMLU/TruthfulQA；SimpleQA 仅作方法学引用）。

### 报告级指标（同一份「断言清单」派生，口径一致）

| 指标 | 无网 | 有网 | 对应标准评测概念 / 含义 |
| --- | --- | --- | --- |
| 证据分级结构化合规率 | ✓ | ✓ | 带 `evidence:A/B/C` 的**断言**占比 = structured-output / schema 合规 |
| 不确定性披露率 | ✓ | ✓ | (C 档 + 显式「未获取/推测」) 断言占比 = abstention / uncertainty disclosure |
| 平均报告可信度评分 | ✓ | ✓ | A×1+B×0.55 加权 0–100（产品内同款）→ 全 C 即低分（诚实保守） |
| 红队质疑密度 | ✓ | ✓ | 从业者红队逼出质疑 / 每 100 条断言 = red-teaming challenge density |
| A 档占比 | ✓ | ✓ | A 档断言占比（无网恒 0 属设计保证；有网应显著更高，是机制价值对照） |
| **引用真实率** | — | ✓ | 出处「可达 + 页面含所述事实」比例 = citation grounding / source faithfulness |

> **可靠性保证**：报告级指标由 `parse_claims()` 切出的同一份「断言清单」派生，分母统一为断言条数，
> 不存在单位不一致或内部矛盾（已通过「全 C 报告得分=0」「C=N 但合规率=100%」等自检）。
> 红队为同模型自评，定位为「质疑信号密度」而非「已纠正错误数」，简历中据实表述。
> 所有正确率均输出 **Wilson 95% 置信区间**（`wilson_ci()`），不再用写死的 ±11%。
> 参考：**n=60 全对 → CI [94.0%, 100%]**（当前主测试集每层规模）；
> n=42 全对 → [91.6%, 100%]；n=18 全对 → [82.4%, 100%]。
> **样本量越小，「100%」越不可信**——n=18 的 100% 实际只等于「≥82%」。

### 用法
```bat
:: 离线演示：内置样例 + golden 三层结构，不耗 token，验证指标形态
python eval_harness.py
::   → 产出 eval_report.json + eval_summary.md

:: 无网基线（本项目的 OpenAI 网关）：跑 N 行业 self-pilot + GOLDEN 三层
set AI_BASE_URL=https://aigw.yuexiuproperty.cn/v1/chat/completions
set AI_API_KEY=sk-xxx
set AI_MODEL=deepseek-v4-flash
python eval_harness.py --live --industries "跨境电商,工业软件,社区团购,储能,宠物医疗,SaaS CRM"

:: 标准 backbone（方案1）：额外跑 CMMLU+TruthfulQA（需 _golden_standard.json）
python eval_harness.py --live --standard --industries "跨境电商,工业软件,社区团购,储能,宠物医疗,SaaS CRM"

:: 有网主结果（需联网检索能力的模型）：额外独立核验引用真实率
python eval_harness.py --live --web --industries "跨境电商,工业软件,社区团购,储能,宠物医疗,SaaS CRM"

:: ⭐ 推荐：用「独立网关 + 异族模型」当裁判，破除同模型自评护短
::   （bailian 网关有 deepseek-v4-pro / glm-5.2 / kimi-k2.7-code，建议选 glm-5.2 或 kimi-k2.7-code）
python eval_harness.py --live --standard ^
  --judge-base-url https://aigw.yuexiuproperty.cn/bailian/v1/chat/completions ^
  --judge-api-key sk-xxx --judge-model glm-5.2

:: 被测模型回答温度（默认 0=确定性可复现）。若某网关在 temp=0 行为异常
:: （如大面积 abstain/空答），改用 --temperature 0.2；换温度会让旧缓存全部 miss 并重拉。
python eval_harness.py --live --standard --temperature 0

:: 被测模型回答会自动缓存到 eval_cache.json（仅缓存被测模型，不缓存 judge）。
:: 缓存带 schema 版本戳：任何改动评分口径的代码都会令旧缓存自动作废并重拉，
:: 不会出现「多版本 harness 共用一份缓存 → 答案-题目错位 → 分数全废」的坑。
:: 想强制重拉：--no-cache；想隔离不同被测模型：--cache-file xxx.json

:: ⭐ 人工抽检闭环（没有强 judge 时的标准解法）
::   ① 导出对照评分表（对照 domain_golden_v2.md 的「正确结论 / 关键纠偏点」）
python eval_harness.py --export-human human_grading_sheet
::      → 产出 human_grading_sheet.md（逐题打勾）+ human_grading_sheet_template.json（回填模板）
::   ② 先实跑一次，把模型原回答落到 human_samples.json（再导出评分表即可三栏并列对照）
python eval_harness.py --live --standard
::   ③ 打勾后另存为 human_grades.json，重跑载入 → 人工判定优先，并输出 judge-人工一致率
python eval_harness.py --live --standard --judge-model glm-5.2 ^
  --judge-base-url https://aigw.yuexiuproperty.cn/bailian/v1/chat/completions ^
  --human-grades human_grades.json

:: 可选：--consistency 测关键数字自洽率
```

> ⚠️ 必须在能访问该网关的网络环境运行（企业内网网关无法从外部环境直连）。
> `--web` 的引用核验由本机独立抓取 URL，故运行机需有公网访问能力。
> 注：`--industries` 含空格的行业名（如 `SaaS CRM`）必须用英文双引号整体包裹，否则 argparse 会把空格后的词当第二个参数。
> 两套都跑后，`eval_baselines.json` 保留各自均值，`eval_summary.md` 末尾自动渲染「双模态对比」表。

汇总报告示例（`eval_summary.md`，离线样例）：

| 行业 | 可信度 | 覆盖率% | A档% | 不确定性% | A | B | C | 纠错 | 引用真实% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 跨境电商-出口 B2C | 77 | 90.0 | 44.4 | 50.0 | 4 | 4 | 1 | 5 | — |

### 试点用户数（诚实处理，不编数字）
- 产品已在前端埋入可信度评分与红队纠错逻辑，**遥测即产品能力本身**；上线后每个真实报告都自带评分，试点用户数 = 真实运行次数。
- 简历写法（双模态）：「构建覆盖无检索/有检索的双模态幻觉治理评测基准，以证据分级+五步 prompt 链+从业者拷问机制，在 6 行业 self-pilot 下量化——**无检索基线**不确定性外显率 X%、事实准确率 Y%；**有检索主结果**引用真实率 Z%、平均报告可信度 W/100、自动纠错量 K 项/行业。两模态分别覆盖『编造事实』与『编造引用』两大幻觉模式。」上述数字由 `eval_harness.py --live`（及 `--web`）跑出，**真实可复现**。



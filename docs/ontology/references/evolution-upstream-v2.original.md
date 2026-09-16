# 上游数据对接说明 （暂定）

- 日期：2026-09-16
  
  

---

## 1. 变更摘要

| #   | 变更                                                          | 类型     | 解决的真实问题                    |
| --- | ----------------------------------------------------------- | ------ | -------------------------- |
| 1   | `tool_call/tool_result` 允许多个并行未闭合（多槽配对）                     | 放宽     | 真实 agent 并发调多个工具，v0 会整文件拒收 |
| 2   | 新增可选 `call_id` 关联字段                                         | 新增（可选） | 配对不再依赖位置，乱序/并行可精确定位        |
| 3   | `llm_output`/`tool_result` 新增可选 `status`（ok/error）与 `error` | 新增（可选） | 工具超时、LLM 报错、失败后重试的真实轨迹     |
| 4   | `task_end.status` 增加 `cancelled`                            | 扩展     | 超时/人为取消的轨迹                 |
| 5   | **钉死 turn 语义**：turn = 模型调用轮次，llm_call 严格递增                  | 明确     | 训练评估模型需要明确的步进结构            |
| 6   | 新增可选批次清单 `upstream_manifest.json`                           | 新增（可选） | 上游声明"本批 N 条已投完"，收集端核对完整性   |
| 7   | 原子投递约定（临时文件 + rename）                                       | 约定     | 半写文件被收集导致整条轨迹误隔离           |
| 8   | `ts` 格式要求（ISO-8601 带时区）                                     | 明确     | v0 只查存在不查格式                |
| 9   | 评价新增可选 `violations` 违规码标注                                   | 新增（可选） | 为训练评估模型提供细粒度标签             |

所有新增字段均为**可选**——上游不埋也不拒收，但建议按 v2 埋点以获得完整轨迹能力。

---

## 2. 总览：

```
上游 agent 运行并埋点记录
  → 写 executions/run-<id>.jsonl（每条轨迹一个文件，含并行/失败/重试全记录）
  → 写 reviews/*.jsonl（人工评价，可含违规码标注）
  → 原子完成投递（.tmp 写完 rename；跨机先传 incoming/）
  → 写 upstream_manifest.json 声明批次清单（推荐）
  → 框架 ① 收集：核对 manifest → 校验 → 规范化入库
```

**上游职责一句话**：按本契约埋点产出轨迹文件 + 评价文件，原子投递，附批次清单。其余由框架处理。

---

## 3. 执行记录契约 v2

### 3.1 文件与格式

- 位置：`executions/`（gitignored）
- 命名：`run-<id>.jsonl`（`<id>` 全局唯一，仅字母/数字/`.`/`_`/`-`；同 run_id 两份文件双双隔离）
- 格式：每行一个 JSON 事件，UTF-8；**一条轨迹一个文件**

### 3.2 公共字段（所有事件必带）

| 字段       | 说明                                                                         |
| -------- | -------------------------------------------------------------------------- |
| `event`  | 事件类型（见 3.3）                                                                |
| `ts`     | **ISO-8601 字符串，必须带时区偏移**（如 `2026-09-16T10:00:00+08:00`；epoch 数字或其他格式 → 隔离） |
| `run_id` | 与文件名一致                                                                     |

### 3.3 事件词汇（6 类核心 + 字段）

| 事件            | 必选字段                             | 新增可选字段（v2）                                       | 说明                        |
| ------------- | -------------------------------- | ------------------------------------------------ | ------------------------- |
| `task_start`  | `task_id`、`task_input`、`harness` | —                                                | 首事件且唯一                    |
| `llm_call`    | `turn`、`messages`                | `call_id`、`model`、`temperature`                  | 调用模型；`messages` 为该轮完整输入快照 |
| `llm_output`  | `turn`、`content`                 | `call_id`、`status`、`error`、`usage`、`duration_ms` | 模型输出；失败时 `content` 可为空串   |
| `tool_call`   | `turn`、`tool`、`args`             | `call_id`                                        | 工具调用                      |
| `tool_result` | `turn`、`tool`、`result`           | `call_id`、`status`、`error`、`duration_ms`         | 工具返回；失败时 `result` 可为空对象   |
| `task_end`    | `status`、`answer`、`duration_ms`  | `error`                                          | 末事件且唯一                    |

- `status`（llm_output / tool_result）：`ok`（默认，缺省视为 ok）/ `error`
- `task_end.status`：`success` / `failed` / `cancelled`（新增）；`failed` 或 `cancelled` 时可带 `error` 说明
- `usage`：`{"input_tokens": N, "output_tokens": N}`（训练/成本分析用）
- `model`：模型标识（如 `"forestry-agent-v3"`）

### 3.4 turn 语义

**turn = 模型调用轮次**（第几次 llm_call），规则：

1. 每次 `llm_call` 开启一个新轮次，turn 从 1 起**严格递增**（第一轮 llm_call 的 turn=1）
2. 配对的 `llm_output.turn` = 其 `llm_call.turn`
3. `tool_call.turn` = 发起调用时所在轮次；`tool_result.turn` ≥ 对应 `tool_call.turn`（工具通常同轮返回；异步工具允许跨轮返回）
4. 校验：turn 必须为正整数；llm_call 的 turn 序列严格递增（跳跃 → 隔离）

> 重试 = 新一轮 llm_call（turn+1），见 3.6。

### 3.5 call_id 关联规则

- `call_id` 为字符串，**同一 run 内唯一**
- `llm_output.call_id` 必须等于其配对 `llm_call.call_id`
- `tool_result.call_id` 必须等于其配对 `tool_call.call_id`
- `call_id` 缺省时退化为 v0 位置配对（向后兼容）；**并行调用必须带 call_id**

### 3.6 并行、失败与重试的表达

| 真实场景     | 表达方式                                                                             |
| -------- | -------------------------------------------------------------------------------- |
| 并发调多个工具  | 同一 turn 内多个 `tool_call` 未闭合即再发起，各自带唯一 `call_id`，`tool_result` 按 call_id 配对（顺序任意） |
| 工具失败     | `tool_result.status="error"` + `error` 描述；失败结果也**必须投递**（评估器需要知道"试过错工具"）          |
| 失败后重试    | 失败结果（status=error）后，同一 turn 或下一轮再次 `tool_call`（新 `call_id`）→ 成功 `tool_result`    |
| LLM 调用失败 | `llm_output.status="error"` + `error`；重试 = 新 turn 的 `llm_call`                   |
| 任务超时/取消  | `task_end.status="cancelled"` + `error` 说明                                       |

### 3.7 harness 版本哈希（与 v0 相同，必填）

`task_start.harness` 含 6 键 SHA-256（64 位十六进制）：`tasks / prompts / tools / rules / knowledge / ontology`。只校验格式与键完整性；历史版本合法。

### 

---

## 4. 人工评价契约

与 v0 相同：`reviews/*.jsonl`，字段 `review_id / exec_id / verdict / annotations / corrected_answer(可选) / reviewer / ts`；annotations 词汇 aspect（引用准确性/事实正确性/格式合规/完整性/其他）× severity（info/minor/major/critical）；`verdict=fail` 须带 annotations；`exec_id` 必须指向已收集轨迹。

**v2 新增可选字段 `violations`**——违规码级细粒度标注（训练评估模型用）：

```json
{"review_id": "rev-0001", "exec_id": "real-0001", "verdict": "fail",
 "annotations": [{"aspect": "引用准确性", "severity": "critical", "comment": "引用的法条不在检索结果中"}],
 "violations": [
   {"code": "citation_unverified", "evidence": "answer.law_refs[0]", "severity": "major", "suggestion": "移除该引用或补充检索"}
 ],
 "corrected_answer": {"decision": "许可", "law_refs": [{"law": "中华人民共和国森林法", "article": "第五十六条"}], "conditions": ["申请材料齐全"]},
 "reviewer": "审核员A", "ts": "2026-09-16T11:00:00+08:00"}
```

- `violations[].code`：与框架违规码一致（`citation_unverified / bad_law_ref / bad_decision / answer_not_object / status_answer_mismatch / empty_answer / assess_error / decision_reasons_missing`）
- 与 `annotations` 并存不冲突：annotations 面向人看，violations 面向模型训练
- 无 violations 不拒收（可选）

---

## 5. 批次清单 `upstream_manifest.json`（可选，强烈推荐）

上游投完一批后，在仓库根写清单声明"本批文件齐全"，收集器核对后才能确认批次完整：

```json
{
  "batch_id": "b-20260916-01",
  "deliverer": "forestry-agent-prod",
  "ts": "2026-09-16T10:30:00+08:00",
  "files": [
    {"name": "executions/run-real-0001.jsonl", "sha256": "…(64位hex)", "size": 14207},
    {"name": "executions/run-real-0002.jsonl", "sha256": "…(64位hex)", "size": 9801},
    {"name": "reviews/reviews-b01.jsonl", "sha256": "…(64位hex)", "size": 3120}
  ]
}
```

收集器核对规则：

- 清单内每个文件的 sha256/size 与磁盘实际一致 → 齐全
- 缺失或哈希不一致 → 报告「批次不完整」+ 差异清单，退出码 1，**不进行收集**（宁缺毋滥，等上游补投）
- 无 manifest 时退化为 v0 目录扫描行为（不核对完整性）

---

## 6. 原子投递约定（防半写文件）

| 场景                     | 约定                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------ |
| 上游与本仓库同机               | 先写 `executions/run-<id>.jsonl.tmp`，写完 **rename** 为正式文件名；收集器忽略 `*.tmp`                |
| 跨机投递（scp/rsync/对象存储同步） | 先传 `executions/incoming/`、`reviews/incoming/`，全部传完后移动到正式目录（或等收集器移动）；收集器不扫描 incoming/ |
| manifest 写入时机          | **最后写**——manifest 出现即代表该批投递完毕                                                        |

半写文件（截断 JSON）若被收集，整条轨迹会进隔离区——上游必须遵守原子投递，避免误隔离。

---

## 7. 校验规则汇总

**error 级（任一命中 → 整文件/整条隔离）**：

| 规则                                                                                     |                          |
| -------------------------------------------------------------------------------------- | ------------------------ |
| 首事件 task_start 唯一、末事件 task_end 唯一                                                      | 不变                       |
| 每类事件必选字段齐备；ts 为 ISO-8601 带时区                                                           | ts 格式校验为**新增**           |
| llm_output 必须有配对 llm_call（turn 一致；有 call_id 时按 call_id）                                | call_id 匹配为**新增**        |
| tool_result 必须有配对 tool_call（有 call_id 时按 call_id 且 tool 名一致）                           | 多槽并行 + call_id 匹配为**变更** |
| task_end 前无未闭合配对；文件截断补报 unclosed_pair                                                  | 不变（多槽同理）                 |
| llm_call 的 turn 严格递增、从 1 起；llm_output.turn = 配对 llm_call.turn                          | **新增**                   |
| status 枚举：llm_output/tool_result ∈ {ok, error}；task_end ∈ {success, failed, cancelled} | **新增**（缺省按 ok 处理）        |
| call_id 同一 run 内唯一                                                                     | **新增**                   |
| harness 6 键 SHA-256 格式                                                                 | 不变                       |
| run_id 同文件一致、跨文件唯一                                                                     | 不变                       |

**warning 级（告警不拒收）**：未知事件类型、未知 harness 键、未知 aspect、verdict=fail 无 annotations、call_id 缺失（退化位置配对）。

---

## 8. 错误处理场景（v2 新增场景加粗）

| 场景                            | 框架处理                | 上游应对                            |
| ----------------------------- | ------------------- | ------------------------------- |
| **manifest 文件缺失/哈希不一致**       | 报告批次不完整，退出码 1，不收集   | 补投后重写 manifest                  |
| **半写文件（未遵守原子投递）**             | 截断文件进隔离区            | 改用 .tmp + rename / incoming/ 约定 |
| **并行 tool_call 未带 call_id**   | 按位置配对（退化），告警        | 补 call_id 埋点                    |
| **tool_result.status=error**  | 正常入库（不隔离），评估器可见失败轨迹 | 失败结果必须投递，勿丢弃                    |
| **task_end.status=cancelled** | 正常入库                | 带 error 说明原因                    |
| 单行 JSON 解析失败                  | 整文件隔离 + .error.json | 修复后移回重跑                         |
| exec_id 重复                    | 双双隔离                | 保证 run_id 全局唯一                  |
| 评价指向不存在轨迹                     | 仅该条隔离               | 先投轨迹后投评价                        |
| 目录为空                          | 告警，退出码 0            | 合法空批次                           |

---



---

## 9. 投递清单（上游实施要点）

1. **埋点**：记录完整事件流——每个 llm_call/output（含失败）、每个 tool_call/result（含失败与重试）、并行调用全部记录
2. **关联**：并行工具调用必须带 `call_id`；建议全部事件带 call_id
3. **turn**：llm_call 从 1 严格递增；llm_output 同 turn；工具结果 turn ≥ 调用 turn
4. **时间**：ts 一律 ISO-8601 带时区（+08:00）
5. **投递**：原子写（.tmp → rename；跨机走 incoming/），manifest 最后写
6. **不要**：丢失败事件、合并多条轨迹到一个文件、复用 run_id/call_id、修改 collected/ 与 quarantine/

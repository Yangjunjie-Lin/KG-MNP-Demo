# TXT、Word 与 Excel 混合资料建模

适用范围：离线、证据绑定、人工审核的本体工程。这里的“多格式输入”不是自动 OCR、语音识别或通用自然语言理解。本页描述的映射 Provider 不调用在线模型；新增五阶段范围提案可显式连接 Qwen，但不改变本页的确定性映射边界，也不承诺任意材料能自动生成唯一且业务正确的本体。

Word 和 Excel 解析需安装 `ingestion-documents` 可选依赖（开发环境的 `dev` 依赖已包含）。支持的是 DOCX / XLSX；旧 DOC / XLS、扫描图像中的文字不会被静默当作已解析内容。缺少依赖或不支持的格式将明确阻断解析。

## 工作台流程

1. 创建并选择项目。选择具有所需类、属性、约束和查询的领域包。
2. 在“资料与证据”分别上传 UTF-8 TXT、DOCX、XLSX（或 CSV），勾选资料创建同一批次，生成并运行解析计划。
3. 检查解析质量和证据。DOCX 段落、Word 表格号、Excel 工作表名及单元格坐标均保留。公式不执行；图片、扫描件不自动变成语义事实。
4. 在五阶段操作台 1.3 创建范围、1.4 批准范围并保存能力问题、准备基线；范围版本保存于 URL，刷新不丢失已提交记录。
5. 在 3.1“混合资料建模”展开要建模的具体表格，填写目标类、共享身份空间、主键字段、数据属性与类型，以及跨来源对象关联；2.1 可以回查旧基线／字段映射候选。
6. 对 TXT 或 DOCX 段落添加文本模板，例如 `实体 {id} 的标签为 {label}。`。模板必须匹配完整行或段落；不接受用户正则表达式。不能匹配的段落可用“原文记录”选择主键和事实值的原文片段并映射到属性。
7. 若不同来源使用不同主键，只在确有依据时填写“原始主键 → 统一主键”和合并理由。系统不会通过同名、相似词或相同行号自动决定对象相同。
8. 生成候选并选择审核队列，检查“来源覆盖与身份核对”。未映射的输入条目必须补充映射，或以理由明确排除后重新生成提案。覆盖表示条目被使用，不代表理解了段落中的所有语义。
9. 在 4.4 逐项审核类断言、属性、身份与关系。4.1／4.2 新增实际联合语义检查，但尚未绑定旧 finalize 为必需门。矛盾值不会以最后写入覆盖；它们进入原有冲突与审核流程。拒绝的依赖、未解决冲突和未审核候选不能确认。
10. Finalize 后，绑定实际 Query/Oracle，运行真实编译与 OWL、SHACL、CQ、Provenance 验证，导出 `.kgop`。可继续本地 Registry、Release 和对象来源追溯。

映射配置提交后是提案的一部分，修改规则需生成新提案并重新审核。它不能修改已发布包。当前浏览器编辑中的未提交表单不是持久化配置；提交成功的规则、提案、原文片段及任务由服务器保存。

## 身份和去重的准确含义

| 输入情况 | 行为 |
| --- | --- |
| 不同文件、工作表或 Word 表的第 2 行 | 默认规则使用完整 Source/表/行身份摘要，不因行号相同混合 |
| 显式映射使用相同身份空间和主键 | 一个统一 IRI；相同事实合并并保留全部来源 |
| 同名但不同主键 | 不自动合并 |
| 有依据的主键别名 | 显式映射到同一规范主键，保留判断依据 |
| 别名循环、相互矛盾的目标或一个身份空间声明不同类 | 阻断，不猜测 |
| 同一实体同一数据属性出现不同值 | 保留不同候选并报告冲突，不自动选择其中一个 |
| 有多个可用基线类 | 要求明确记录映射，不按 IRI 字母顺序选择类 |
| 无明确属性对应或最高分并列 | 默认字段映射不选择目标；使用明确映射 |

V2 的统一 IRI 是 `命名空间 + 身份空间 + ':' + 百分号编码主键`。主键大小写有意义，不隐式改写或模糊匹配。身份在同一规则/同一命名空间下可跨文件复用；不会自动修改已存在的其他批次或已发布包。全库跨版本去重需要复用同一业务身份规则并使用现有版本比较与审核。

## API / SDK / CLI

继续使用已有 `modeling.prepare` 和 `modeling.proposal`，没有第二套建模入口。资源 API 为项目内 `POST .../modeling/proposals`；SDK 的 `OperationRequest` 与服务 CLI 使用同一个严格请求类型。

`modeling.prepare` 返回 `input_inventory`：已验证的具体表格、首行字段、文本条目和数据条目 ID。V2 直接使用这些 Source/Item ID，不能提交本地服务器路径。其配置类型定义在 `providers/record_profile.py`，同时出现在实际 OpenAPI 中。

请求示例中的 ID 需替换为当前项目准备结果；IRI 需使用当前锁定基线：

```json
{
  "bundle_id": "<modeling_input_bundle_id>",
  "providers": ["manual-candidate-provider"],
  "record_mapping": {
    "profile": "evidence-record-mapping-v2",
    "tables": [{
      "record_id": "records-sheet",
      "source_id": "<source_id>",
      "locator": {"locator_kind": "spreadsheet-cell", "sheet": "Records"},
      "class_iri": "<baseline class IRI>",
      "identity_space": "entities",
      "id_field": "id",
      "identity_aliases": [{"value": "old-001", "canonical": "T001", "rationale": "来源对照表明确记录同一对象"}],
      "literals": {"label": {"predicate_iri": "<baseline data property IRI>", "datatype": "string"}},
      "references": []
    }],
    "text_templates": [],
    "text_records": [],
    "exclusions": []
  }
}
```

Word 表选择器为 `{"locator_kind":"document-table-cell","table_index":0}`（API 从 0 开始，界面从第 1 表显示）；CSV 使用 `{"locator_kind":"delimited-cell"}`。表格当前要求首行为非空、唯一字段名，不猜测合并单元格或跨行表头的业务含义。

每条跨来源关系使用 `field`、`target_space` 和锁定的 `predicate_iri`，目标业务主键必须在本次映射记录中存在。文本模板继承记录配置并加入 `source_id` / `template`；证据文本标注记录加入 `fields`，每个字段包含 `field,item_id,start,end,quote`。偏移按已验证 KG-IR 规范化文本的 Unicode 码点计算，必须逐字匹配该文本；浏览器选择文字会自动计算。它不是原文件的字节偏移，也不是规范化前字符偏移。报告明确记录 `coordinate_basis` 和 `transformation_refs`；NFC、换行规范化与原始观察值均可通过证据／转换记录追溯，不能把 `é` 的一个码点误称为原始 `e` 加组合重音的两个码点。

数据类型支持 `string,integer,decimal,boolean,date,dateTime`。类型必须声明，不从外观猜测。整型、小数和布尔值按受控规则规范化；非法日期、非有限值、指数形式的小数和公式数字转换被拒绝。Excel 原生布尔值及日期/时间的保留文本可在声明类型后转换成相应规范形式，不猜时区，不截掉非零时间来伪造日期。缺少声明表头、主键或关联目标会阻断；稀疏表格中缺少普通字面值的单元格按 OMIT 省略，不伪造证据或默认值。属性是否必需仍由领域约束和 CQ 验证。

V1 `evidence-record-mapping-v1` 仍保留原有请求与冻结领域包行为。多工作表源需使用 V2 明确选择；V1 不静默选择第一张表。

## 审核和完整性

V2 规则通过已有 PluginSnapshot 的配置摘要绑定；Provider Request 引用该快照，因此规则变化会产生不同请求身份。实际建模实现文件也纳入快照摘要，不能只哈希重导出类的薄入口。规则摘要同时写入候选的 `provider_rationales`，受核心提案/确认包摘要保护。原有冻结 Provider Request 1.0 契约未修改；这不等于任意 Provider context 都已被请求摘要绑定。V2 在确认前校验已保存规则、候选摘要及对应快照，再基于验证过的 KG-IR 重算覆盖报告。只篡改配置侧文件不能改变已审判断。

`source-extraction-report.json` 是可再生成的审阅辅助报告，不能作为独立批准权威。原文事实仍通过已有 EvidenceRecord 与 Source Blob 追溯，文本偏移和映射细节保存于项目提案。独立 `.kgop` 的标准追溯边界仍以包内既有 provenance 工件为准，不承诺包含用户原始文档或所有编辑配置。

未解析段落、无法分辨的实体、业务上是否合适的类/关系，以及本体是否过度或不足建模，都需要领域审核与明确 CQ/Oracle。OWL 一致性、SHACL Conforms 与 CQ Pass 不等于来源内容真实或全行业语义正确。

## 回归入口

```text
python -m pytest tests/modeling_alignment/test_mixed_source_identity.py tests/modeling/test_mixed_mapping.py tests/services/test_mixed_source_workflow.py
npm --prefix workbench test
python tools/run_browser_verification.py --selected-test mixed
```

最后一项是独立的实际浏览器增量场景，不代表所有浏览器场景或正式发行验收已完成。固定修订全量验收继续使用 `python tools/verify_candidate.py`，并单列 Linux、人工视觉/键盘与交付包一致性证据。

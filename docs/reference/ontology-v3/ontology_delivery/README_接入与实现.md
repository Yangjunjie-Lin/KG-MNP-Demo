# 建模输出交付协议 3.0.0 · 规范参考版

## 先明确本包的采用边界

本包以 GB/T 48000.3—2026《标准数字化 第3部分：本体建模要求》为检索目标，采用“有来源、分版本、可核验”的参考方式，不声明通过该标准的完整符合性评定。

**已核实的资料：**国家标准馆的标准研制表列明正式标准号、名称、2026-01-28 发布和 2026-08-01 实施的日期；中国标准化研究院公开的 2025-04-29 征求意见稿正文已经阅读。正式版全文尚未取得，不能把草案章节号、内容或附录结构直接当作正式版条款。题录页部分状态标签滞后，本包记录日期与核验范围，不作最新废止/修订状态保证。

**适用方式：**官方草案范围针对标准数字化中的标准本体。本例是员工—部门的业务本体，因此参考通用的术语描述、类型区分、标识与扩展思路，不导入“标准、章、条款”等领域专用类型，不把它们作为业务数据的强制基类。后续若处理标准文档，应另外核实正式版全文并建立针对该领域的完整模型。

**技术层的依据：**OWL/RDF/Turtle 与 SHACL 的语义以相应 W3C 文档为准；本包的目录、JSON/JSONL 字段、清单、SHA-256 和验收基线是工程约定，不是国标指定格式。公理索引是对已有 OWL 声明和定义域/值域的整理，不因新增该文件而增加业务逻辑。

官方来源入口（版本和核验状态还保存在 `standardization/references.json`）：

- 正式版题录：https://www.ndls.org.cn/standard-digit/index?index=2
- 官方征求意见通知：https://www.cnis.ac.cn/wap/dh/bydt/bzyjzq/gbzqyj/202504/t20250430_59942.html
- 官方草案：https://www.cnis.ac.cn/wap/dh/bydt/bzyjzq/gbzqyj/202504/P020250430358066515464.pdf
- OWL 2：https://www.w3.org/TR/2012/REC-owl2-primer-20121211/
- SHACL：https://www.w3.org/TR/2017/REC-shacl-20170720/
- Turtle：https://www.w3.org/TR/turtle/

不随包转载标准全文。`standardization/crosswalk.json` 中的 `draft_clause` **仅指官方草案**，`final_clause` 明确为 `null`，不伪造正式条款对应关系。

## 1. 这次规范化增加什么

保留原本的本体结构、实例事实、业务约束、字段映射、多源证据、校验审核、查询验收、版本与加载契约。新增八个文件，不加入操作台、Agent 源码或演进实现。

| 文件 | 内容 | 接收端用途 |
|---|---|---|
| `model/terms.json` | 类和属性的完整术语元数据 | 读取标识、名称、双语标签、定义及域/值域，并回查规则 |
| `model/metadata.json` | 本体版本 IRI、命名空间、参考配置 | 识别本体快照及采用边界 |
| `model/axioms.json` | 已有类型声明与域/值域公理索引 | 核查 OWL 结构；不是额外规则引擎 |
| `standardization/references.json` | 正式题录、草案和 W3C 来源分开登记 | 判定引用版本及证据级别 |
| `standardization/profile.json` | 参考配置、适用范围和排除项 | 避免把选择性借鉴误判为完整符合性 |
| `standardization/crosswalk.json` | 草案参考点与实际文件的映射 | 沿来源、文件和检查项追踪 |
| `quality/standardization.json` | 已执行元数据检查、被检文件摘要和异常测试结果 | 读取真实质量状态 |
| `acceptance/standardization_cases.json` | 缺定义、IRI 冲突、错值域、伪称符合等异常用例 | 在副本上重复验证检查器 |

`contracts/delivery.schema.json` 同时增加这些文件的 JSON Schema。`manifest.json` 登记全部文件与其 Schema 引用。交付以 `integration/load_contract.json` 为入口，不能只加载三个 TTL 就跳过来源、参考边界和审核关联。

## 2. 关键字段应该怎样理解

每个术语都具有以下字段，字段名是本包约定：

```json
{
  "iri": "https://example.org/ontology/belongsToDepartment",
  "name": "belongsToDepartment",
  "kind": "ObjectProperty",
  "labels": [
    {"language": "zh", "value": "所属部门"},
    {"language": "en", "value": "Belongs to department"}
  ],
  "definition": {
    "language": "zh",
    "value": "把员工对象关联到其在当前快照中所属的已登记部门对象；不表达历史任职。"
  },
  "domain": "https://example.org/ontology/Employee",
  "range": "https://example.org/ontology/Department",
  "constraint_refs": ["RULE-belongsToDepartment"]
}
```

上例是字段摘录；可验证的完整记录以 `model/terms.json` 为准。类型有 `Class`、`DatatypeProperty` 和 `ObjectProperty` 三种，不能把部门对象当作普通字符串。数据属性仍使用 XSD 数据类型，员工编号不会因为都是数字字符就转换成数字。

类的 `property_refs` 列出关联属性；`super_terms`、`sub_terms`、`equivalent_terms` 和 `characteristics` 在本例中为空，含义是**未批准且未声明额外公理**，不等于证明父类或等价类绝不存在。以后添加这些公理，需要独立依据、编译能力和审核，不得单靠填表进入正式图。

定义由本地业务范围与映射草拟，`definition_origin` 明确为 `LOCAL_SCOPE_AND_MAPPING_DRAFT`，不是标准原文或经过外部专家认证的定义。中英文标签是展示层元数据，不改变对象身份。

## 3. 为什么还要保留 OWL 和 SHACL 两套表达

`ontology.ttl` 表达类、属性及已确认的语义关系；`shapes.ttl` 表达当前数据必须满足的检查要求。OWL 的域和值域支持类型推论，不等同于“检查某字段必须存在”。本例“每个员工恰好一个已登记部门”来自 `evidence/snapshots/requirements.json`，不是本次检索到的国家标准规定员工只能属于一个部门。

`axioms.json` 索引 7 条类型声明和 10 条域/值域表达，不自动添加员工与部门互斥、关系传递性或 `owl:FunctionalProperty`。相同事实的所有证据仍合并保留，SHACL 中的 `minCount=1`、`maxCount=1` 及已有独立答案也不变。

## 4. 输出端如何实现

**范围冻结。** 核验业务记录、文本、来源、身份规则及独立答案，同时固定参考配置版本和业务术语定义草案。定义修改也应视作内容变更，不能沿用旧审核。

**术语规范化。** 为候选补齐 `IRI/name/labels/definition/kind`；数据属性、对象属性再补定义域和值域。保留已有 IRI；需要扩展第三方词汇时另设受控命名空间。本例的 `example.org` 是示例命名空间，不宣称已注册或可对外解析。真正迁移到业务域名时，应使用显式 IRI 映射，重建引用、证据关联、查询与审核，不能静默改字符串。

**单一语义编译。** 临时验证图和最终 `ontology.ttl` 必须由同一个已确认的术语对象编译。类与属性声明映射到 OWL；`labels` 映射到 `rdfs:label`；自然语言定义映射到 `rdfs:comment`；域/值域使用 `rdfs:domain/range`。本体本身声明 `owl:Ontology`、`owl:versionIRI` 和 `owl:versionInfo`。不要设置暗示完整国标符合性的 `dcterms:conformsTo`。

**事实构建。** 继续按原映射、身份和文本定位机制生成对象与事实，不从参考标准添加业务实例。源记录、引文、位置、事实和映射构成的证据链不变。

**校验与审核。** 元数据程序检查只验证完整性、唯一性、类别、域/值域和范围绑定。语义是否正确仍需人工确认；程序不能据此声称完成了正式版标准符合性审核。专业 SHACL 与 OWL 验证按原流程单独执行。

**输出冻结。** 在审核时绑定术语 JSON 的内容摘要及共享编译器生成的本体图摘要。交付前重算，两者任一变化即阻断。生成术语、元数据、公理、事实、溯源和审核文件后，再生成清单摘要；报告更新也要重新计算清单，不能留下旧摘要。

## 5. 接收端如何实现

先执行本文后半部分的基础加载代码，完成文件摘要、Schema、图一致性、证据定位和 SPARQL 验收；再执行以下语义关联检查：

| 检查编号 | 至少检查的内容 |
|---|---|
| `TERM-METADATA` | 所有术语有非空定义和标签，JSON 注释与实际 RDF 相符 |
| `TERM-IDENTITY` | IRI 唯一；术语目录、类/属性读取索引与实际图对应 |
| `TERM-TYPING` | 类、数据属性、对象属性分类一致；编号类型保持字符串 |
| `TERM-DOMAIN-RANGE` | 属性域/值域、类的属性集、图与目录一致 |
| `NO-UNAPPROVED-AXIOMS` | 本例不出现未经批准的继承、等价、互斥和性质公理 |
| `REFERENCE-STATUS` | 草案保持草案标记、正式全文待核验、没有完整符合性声明 |
| `BUSINESS-RULE-PRESERVATION` | 对照业务需求检查现有硬规则，不能靠降低数量约束通过 |
| `PROVENANCE-INTEGRITY` | 事实仍指向有效证据与陈述，不因新元数据丢失原依据 |

应在 `ISOLATED_STAGING` 中分图加载。参考文献、检查报告、标准草案信息不属于业务事实图，也不能混入能力问题的查询数据集。`model/axioms.json` 是读取索引，必须与 `ontology.ttl` 核对，不能反过来悄悄重写完整本体。

异常用例中 `path` 是相对包根的路径，`pointer` 是 JSON Pointer，`line_index` 仅对 JSONL 使用且从 0 开始。对副本应用 `REPLACE` 后，运行 `expected_check_id` 对应的检查；只有实际检测到相应问题才记录通过。不要仅因摘要变化就把“错值域检测”算作成功；测试内部可跳过摘要，直接验证该语义规则。真实接收流程则仍然必须先检查摘要。

完整业务链路的 task/run/tool 字段仍由实际下游任务运行时填充，本包不预填任务成功率，不提供演进策略、变更回写或发布服务。

## 6. 验证状态与兼容迁移

`PASS` 表示指定检查器实际执行通过；`NOT_RUN` 表示未执行，`NOT_MEASURED` 表示没有测量该指标。`quality/standardization.json.local_status=PASS` 只表示本地元数据检查通过。它不等价于国标符合、正式版全文审核、专业 OWL/SHACL 通过或人工批准。

当前浏览器导出的包真实执行本地程序检查，但不冒充 RDFLib、SPARQL、pySHACL 或 HermiT。单独下载的范例包若附有 `OFFLINE_REFERENCE_RECHECK` 结果，表示对该下载快照另外做过实际复验；不意味着浏览器部署了这些服务。所有输出仍是合成范例并保持 `NOT_RELEASED`。

本版使用 **自定义协议 `ontology-delivery / 3.0.0`**，因为 Schema 增加了必需的元数据和参考边界，旧版严格校验器不能不更新就接受。升级方式是更新接收端的版本白名单、Schema 与必要检查项；原 `objects/facts/assertions/evidence` 核心字段、原 IRI、业务查询、规则和来源语义不变。

本包是新的完整快照，不是原 v2 包的差量补丁。对照 v2 实例图应保持同构；TBox 新增的是本体头和注释元数据，不新增业务逻辑。新版本的 `ontology` 含内容摘要，术语自身版本也带摘要；`constraints` 和 `mapping` 在其语义不变时保留原版本。生产迁移不得复制合成审核或使用本包的示例 IRI 代替真实身份规划。

**取得正式版全文后的处理：** 单独登记正式正文版本及摘要；复核实际适用范围与逐项差异；更新 `crosswalk` 的引用版本和正式条款；只有确定存在适用且未满足的要求时才增加规则并重新审核。不要直接把所有 `PENDING` 或 `CONSULTATION_DRAFT` 改成“已符合”。


---

# 建模输出数据包：接入与实现

**协议：`ontology-delivery / 3.0.0`。** 本包是员工—部门当前归属的合成建模结果，用于联调、结果复验和下游评测接入，不是生产发布。`ontology-delivery` 的目录、字段和交接规则是本次提出的接口约定，不是现成行业标准；图数据、约束、查询与字段校验分别采用 RDF/Turtle、SHACL、SPARQL 和 JSON Schema。

## 1. 从哪里开始

先读 `manifest.json`，再读 `integration/load_contract.json`。前者说明“这一包是什么、有哪些文件、对应哪些版本”，后者说明“如何验证和加载”。不要直接把全部 TTL 文件拼成业务图，也不要把测试预期混入业务事实。

本包只包含建模产物、证明和解释这些产物所必需的来源快照、接入契约及本说明。没有操作台、Agent 源代码、完整运行项目、自动优化程序或业务执行结果。

### 文件分类

| 路径 | 内容 | 使用方式 |
|---|---|---|
| `model/ontology.ttl` | 类、属性、关系的完整语义定义 | 载入本体图。 |
| `model/instances.ttl` | 本次采纳的对象和事实 | 载入本次快照实例图。 |
| `model/shapes.ttl` | 必填、数量、类型和目标类约束 | 作为验证图，不混入业务查询图。 |
| `model/catalog.json` | 本体类型与属性的轻量读取索引 | 供对象服务读取；不能替代完整 OWL 定义。 |
| `model/scope.json`、`model/rules.json` | 身份范围、时间范围、业务边界和带编号的规则 | 确定解释口径，定位违规规则。 |
| `data/objects.jsonl`、`data/facts.jsonl` | 对象索引和逐条事实登记 | 通过对象 IRI、`fact_id` 连接业务调用、证据和评测。 |
| `mapping/mapping.json` | 源字段到对象、属性与关系的声明式映射 | 确定身份、值转换、目标查找、去重与冲突策略。 |
| `provenance/` | 来源目录、证据、原始陈述与事实的对应关系 | 从结果逐层回查来源；一条事实可有多份证据。 |
| `evidence/snapshots/` | 实际引用的记录、文本和规则依据快照 | 用摘要和定位复验；不包含整个上游项目。 |
| `quality/` | 校验、审核、问题和有计算口径的指标 | 区分真实执行的检查、未运行的检查和未测量指标。 |
| `acceptance/` | 预先给定的查询答案、查询文件、异常用例与实测结果 | 在独立副本中回归，不以输出反写正确答案。 |
| `integration/` | 分图加载、版本上下文和只读能力描述 | 接入对象读取、任务运行和后续反馈关联。 |
| `version/` | 变更描述、依赖与转换工具版本 | 固定依赖，判断版本关系与读取兼容性。 |
| `contracts/delivery.schema.json` | JSON/JSONL 字段与类型定义 | 按 manifest 中 `schema_ref` 对每个对象校验。 |

## 2. 关键字段与关联关系

### 2.1 统一身份与时间

`package_id` 标识一份冻结交付；`model_versions` 分别记录本体、实例、约束、映射和参考答案的版本。对象以 `(identity_scope, type_iri, business_id)` 定位，不能按姓名相似度合并。

`object_id`、事实主语和 IRI 对象均为完整 IRI。普通字符串使用 `{"type":"literal","value":"E-001","datatype":"http://www.w3.org/2001/XMLSchema#string","language":null}`；关系目标使用 `{"type":"iri","value":"https://example.org/data/hr/Department/D-01"}`。不可把 IRI 目标当作普通字符串。

本包时间语义是 `CURRENT_SNAPSHOT`。`snapshot_at` 是本次快照时间；`valid_from`、`valid_to` 为 `null` 表示没有提供生效区间，不代表永久有效。不同快照不能直接并入同一个“当前归属”图，否则旧、新关系可能同时存在。接收方需按身份范围维护独立快照和明确的活动版本指针。

### 2.2 事实—证据链

`data/facts.jsonl.fact_id` → `assertion_refs` → `provenance/assertions.jsonl.assertion_id` → `evidence_ref` → `provenance/evidence.jsonl.evidence_id` → `source_id` → `provenance/sources.json` → 快照文件及其 SHA-256。

一条事实由记录和文本共同支持时，保留两条原始陈述和两份证据；去重只合并事实，不删除依据。记录定位使用 JSON Pointer，例如 `/0`，相对于其来源快照；文本定位使用 Unicode 码点、零起点、左闭右开区间 `[start,end)`，并保存逐字引文。JavaScript 原生字符串索引按 UTF-16 计数，不能直接代替此处码点位置，应先使用 `Array.from(text)`。

本示例只提供规则化快照，`original_source_locator=null` 明确表示没有真实原文件页码、框坐标或业务系统原记录位置。不得把“可追溯到规则化快照”宣传为“已经追溯到原始文件”。生产输出应补齐上游提供的原始定位，而不是推测页码。

### 2.3 规则、审核与问题

每项规则都有 `rule_id`、`shape_iri` 和 `basis_ref`。发现问题时记录对象、事实、规则、证据编号；`quality/issues.jsonl` 的单行结构见 `#/$defs/issue`。空文件表示本次没有导出的未解决建模问题，不表示全部专业验证已经通过。

`quality/review.json.reviewed_artifacts` 把审核绑定到实际文件摘要。范围、事实、映射、来源或依赖发生变化时，旧审核失效。示例审核标为 `SYNTHETIC_CONFIRMATION_ONLY`，不能替代有身份认证的业务审批。

## 3. 输出端如何实现

**第一步：冻结内容。** 固定范围、身份策略、结构、规则、映射、采纳事实及其全部证据。保留未解决项，不能为得到“通过”而悄悄丢弃数据。把独立查询答案作为只读输入固定在构建之前。

**第二步：确定性编译。** 使用同一份已确认内容，分别生成 ontology、instances 和 shapes。结构及约束包含完整定义；事实只写采纳内容。不得在导出时再次让模型自由补写。

**第三步：生成关联索引。** 导出对象、事实、原始陈述、证据和来源目录；映射须包含标识规则、转换版本、目标查找和冲突策略。所有相对路径以包根目录为起点。

**第四步：重读实际文件。** 解析三个 RDF 文件；将 facts.jsonl 重新构图并与 instances.ttl 做图同构比较；检查规则目标覆盖、引用闭包、来源摘要和引文位置；执行约定查询并与冻结答案进行无序精确多重集比较。数量相同或查询无异常都不等于答案正确。

**第五步：记录真实状态。** 已执行的检查写 `PASS` 或 `FAIL`，未运行写 `NOT_RUN`，运行失败写 `ERROR`。专业 SHACL、OWL 和真实审核各自独立，不能相互替代。没有独立金标时，语义准确率写 `NOT_MEASURED`；没有下游运行时，任务成功率写 `NOT_AVAILABLE`。

**第六步：打包。** 最后计算所有载荷、契约及说明文件的字节数和 SHA-256，生成 manifest。manifest 不计算自己的摘要，避免循环引用；接收端应另外记录 manifest 原始字节的 SHA-256，用于收件幂等。SHA-256 只能检查内容变化，不证明来源可信；生产传输还需身份认证或签名。

## 4. 接收端如何实现

按 `load_contract.json` 完成：安全解包 → 清单与文件摘要 → JSON Schema → 固定依赖 → 分图加载 → 事实与证据复验 → 查询与异常回归 → 保存验收结果。

同一 `package_id`、同一 manifest 摘要重复到达可以幂等返回；同一 ID 对应不同摘要必须拒绝。拒绝目录穿越、绝对路径、重复 ZIP 条目、符号链接和超限文件；不要执行包中字符串或动态抓取未锁定的 imports。生产审核、校验和发布由接收端自己的策略决定，包内布尔字段不是授权。

下述代码是一个可复制的**只读基础接入示例**。依赖 `rdflib`、`jsonschema`；在解压目录外保存为 `inspect_delivery.py` 后运行 `python inspect_delivery.py 解压目录`。它验证清单、字段、RDF 事实一致性、来源引用和查询答案，不代替完整业务审核、SHACL、OWL或异常回归。

```python
import hashlib, json, sys
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from rdflib import Graph, URIRef, Literal
from rdflib.compare import isomorphic

root = Path(sys.argv[1]).resolve()
def require(ok, message):
    if not ok:
        raise ValueError(message)
def file(name):
    p = root / name
    require(not p.is_symlink(), 'Symlink rejected: ' + name)
    p = p.resolve()
    require(p.is_relative_to(root) and p.is_file(), 'Unsafe/missing path: ' + name)
    return p
def read(name):
    return json.loads(file(name).read_text(encoding='utf-8'))
def lines(name):
    return [json.loads(x) for x in file(name).read_text(encoding='utf-8').splitlines() if x.strip()]
def digest(name):
    return hashlib.sha256(file(name).read_bytes()).hexdigest()
def term(x):
    if x['type'] == 'iri':
        return URIRef(x['value'])
    require(not (x.get('datatype') and x.get('language')), 'Conflicting literal fields')
    return Literal(x['value'], datatype=x.get('datatype'), lang=x.get('language'))

manifest = read('manifest.json')
schema = read('contracts/delivery.schema.json')
Draft202012Validator.check_schema(schema)
def validate(value, definition):
    v = Draft202012Validator({**schema, '$ref': definition}, format_checker=FormatChecker())
    v.validate(value)
validate(manifest, '#/$defs/manifest')
require(len({x['path'] for x in manifest['files']}) == len(manifest['files']), 'Duplicate paths')
for item in manifest['files']:
    raw = file(item['path']).read_bytes()
    require(len(raw) == item['bytes'], 'Size mismatch: ' + item['path'])
    require(hashlib.sha256(raw).hexdigest() == item['sha256'], 'Digest mismatch: ' + item['path'])
    if item['schema_ref']:
        values = lines(item['path']) if item['path'].endswith('.jsonl') else [read(item['path'])]
        for value in values:
            validate(value, '#' + item['schema_ref'].split('#', 1)[1])

graphs = {k: Graph().parse(file('model/' + k + '.ttl'), format='turtle')
          for k in ('ontology', 'instances', 'shapes')}
facts = lines('data/facts.jsonl')
require(len({f['fact_id'] for f in facts}) == len(facts), 'Duplicate fact IDs')
rebuilt = Graph()
for f in facts:
    rebuilt.add((URIRef(f['subject']), URIRef(f['predicate']), term(f['object'])))
require(len(rebuilt) == len(facts), 'Duplicate facts in one snapshot')
require(isomorphic(rebuilt, graphs['instances']), 'JSON/TTL facts differ')
sources = {s['source_id']: s for s in read('provenance/sources.json')['items']}
evidence = {e['evidence_id']: e for e in lines('provenance/evidence.jsonl')}
for e in evidence.values():
    source = sources[e['source_id']]
    require(digest(source['path']) == e['source_sha256'] == source['sha256'], 'Source digest mismatch')
    if e['kind'] == 'text':
        text = file(source['path']).read_text(encoding='utf-8')
        a, b = e['locator']['start'], e['locator']['end']
        require(0 <= a <= b <= len(text) and text[a:b] == e['quote'], 'Quote mismatch')
for f in facts:
    require(all(e in evidence for e in f['evidence_refs']), 'Dangling evidence')
for reviewed in read('quality/review.json')['reviewed_artifacts']:
    require(digest(reviewed['path']) == reviewed['sha256'], 'Review invalidated')

baseline = read('acceptance/baseline.json')
query = file(baseline['query_ref']).read_text(encoding='utf-8')
actual = (graphs['ontology'] + graphs['instances']).query(query)
variables = baseline['variables']
actual_rows = Counter(tuple(row.asdict()[v] for v in variables) for row in actual)
expected_rows = Counter(tuple(term(row[v]) for v in variables) for row in baseline['expected'])
require(actual_rows == expected_rows, 'Query answers differ')
print('基础接入检查通过；仍需完成专业语义验证、覆盖核对、异常回归与真实审核。')
print('manifest_sha256 =', digest('manifest.json'))
```

### 需另外实现的检查

对象索引必须与显式 `rdf:type` 一致；实际受检对象必须覆盖 `acceptance/baseline.json.target_inventory`，不能因遗漏类型导致零目标“通过”。对每个 assertion 核对 fact、evidence、source、mapping rule 与 transform 的引用，按映射重查记录值、关系方向和文本陈述。

专业数据验证可调用 `pyshacl.validate(data_graph=实例图, shacl_graph=约束图, ont_graph=本体图, inference='none', advanced=False, meta_shacl=True)`，保存真实报告并统计目标覆盖。OWL 检查应使用锁定版本的 ROBOT/HermiT，同时检查本体与实例组合的逻辑一致性及不可满足类；失败、未运行和不支持的构造要分别记录。不能把本包的限定 JavaScript 检查器称为 pySHACL 或 OWL 推理器。

异常回归按 `acceptance/cases.json` 在副本上施加变异；更新事实时同步该副本的实例图，避免只是因为 JSON/TTL 不一致被拦截，而没有真正验证指定规则。每个异常必须命中其 `expected_check_ids`，不能只记录“出错了”。运行结果另外保存，不修改原包、原规则或原标准答案。

## 5. 供完整链路关联的字段

读取服务依据 `integration/capabilities.json` 绑定两个只读查询函数。按员工编号查询时，将 `requestedEmployeeId` 绑定为 RDF 字符串，例如 `query(..., initBindings={'requestedEmployeeId': Literal('E-001')})`，不要用字符串拼接生成查询。

该文件是能力**声明**，`service_endpoint=null` 表示没有部署地址，`actions=[]` 表示本案例没有已定义的动作。它不是“动作成功执行”的占位结果。若业务确需写操作，必须另有真实动作定义、输入输出契约、前置规则、授权策略和实现引用，相关字段结构预留于 Schema。

`integration/context.json` 提供本次包版本、对象、事实、规则和证据的关联入口。下游真实执行时自行增加 `task_id`、`run_id`、`tool_id`、`tool_version`、时间、结果和所用对象/事实/规则编号；事件格式见 `#/$defs/runtime_event`。本包不填写虚构任务轨迹。这样才能把后续任务问题关联到“哪份数据、哪项规则、哪个工具、哪一版本”，而不是要求建模输出端实现下游运行或优化。

## 6. 当前示例的验收边界

是否真正执行 RDF 解析、SPARQL 与异常回归，以 `quality/validation.json` 和 `acceptance/results.json` 的实际状态为准。浏览器导出与离线复验后的交付使用同一个 Schema，但前者不会伪造后者的检查结果。

参考答案只验证当前归属查询。对象库存来自构建前确认的记录身份，不是独立语义识别金标；约束通过、答案一致和引用完整均不能代替本体识别准确率或真实业务效果。

`version/change_set.json` 是初始快照记录，上一版本为 `null`；没有基包不能计算真实版本差异。后续增量包须绑定基包 ID 与 manifest 摘要，列明新增、修改和删除；接收端应拒绝基包不一致的增量。

格式参考：W3C RDF 1.1/Turtle、SHACL、SPARQL 1.1；JSON Schema Draft 2020-12。协议中的目录、版本字段、审查状态和运行关联字段属于本说明约定，接收方需按自身系统实现适配。

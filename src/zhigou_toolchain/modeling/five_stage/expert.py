"""Expert draft templates and closed internal contracts; never human approval.

These eleven texts are execution sources, not reconstructed historical prompts.
Configuration versions live in the existing modeling session/CAS generation.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zhigou_toolchain.contracts.canonical import semantic_hash

DEFAULT_PROMPTS = {
    1: (
        "根据本次已授权的表格数据、文本片段、来源定位、质量结果和业务目标，完成当前方法的输入核验、数据画像或范围草拟。明确对象类型、身份字段、时间范围、查询目标、排除项及需要业务确认的规则。保留原始编号、原值、来源与证据，不把样本现象升级为必填、唯一性或全域业务规则。缺失数据进入待补充或隔离，歧义进入 unresolved；不得改写上游数据或生成独立验收答案。仅提交本方法允许的草案或报告。",
        "对照已冻结的业务目标与专家检查点，审核本方法的输入核验、画像或范围草案。检查来源引用是否闭合，身份与时间口径是否清晰，是否遗漏必需对象/查询目标，是否越界建模，是否从样本臆造硬规则。依据实际文件和程序检查逐项定位，不接受生成器自述替代证据。可在范围草案内修正的给出最小建议；需要新数据或业务裁决的交专家处理。独立验收答案不在你的读取范围。输出规定的结构化审核结果，不代替范围批准。",
    ),
    2: (
        "在已确认范围和锁定本体基线上，优先复用已有 IRI、类、属性和公理，再提出确有来源及规则依据的结构缺口。区分对象类型、对象实例、数据属性、对象关系和约束，不重复创建同义概念。检索分数只作候选线索；没有召回不等于基线不存在。新增 IRI 和约束必须符合已授权命名空间、规则与当前方法白名单；无法判断的明确保留。输出可规范化的结构候选，不自行批准或写入正式本体。",
        "对照本阶段指导、冻结基线、已确认范围和专家检查点，检查复用是否有依据，类型层级是否合理，属性方向、定义域和值域是否一致，是否重复造类，新增 IRI 是否获准，SHACL 约束是否有业务规则支持。引用具体 IRI、规则、候选及实际兼容/逻辑检查结果。术语检索不足不能直接批准新建；需要改变业务规则或未授权 IRI 时升级专家处理。只返回审核问题与受限建议，不直接覆盖候选或削弱规则。",
    ),
    3: (
        "依据已确认结构、身份策略和字段映射，将表格记录转换为实例事实，并从文本片段提取明确陈述的事实。保留字符串编码、单位和时间语义；所有事实绑定真实字段、记录或可定位引文。否定、不确定和冲突分别记录，不能转成肯定事实；未知身份不得根据名字猜测。单位或编码转换只按已确认规则执行并留痕。输出当前方法允许的映射、实例或证据候选，不回写来源文件。",
        "逐项检查映射执行与声明是否一致，实例身份是否重复或混同，属性类型/值/单位/编码是否正确，对象关系是否指向有效实例，文本事实是否有准确引文和位置，以及否定、不确定、去重与冲突处理是否正确。对每个问题给出具体事实、来源和字段定位。只建议有来源依据的局部修订；来源相互矛盾或目标身份未知时转专家处理，不能用猜测补齐。审核后仍需程序重新校验和追溯绑定。",
    ),
    4: (
        "对当前候选版本执行完整性、依赖、SHACL 与 OWL 联合验证，并依据真实检查结果组织待审核问题。使用共享编译逻辑生成临时图；把数据问题、结构问题、业务歧义和等待人工审批分开。按最早受影响阶段提出修复路线。未执行、超时或缺依赖的检查如实报告；不得删除失败项、修改期望结果或将等待审核当数据缺陷修复。仅提出检查解释与修复建议，不代替人类批准。",
        "检查每项必需验证是否针对当前候选和相同依赖真实执行，检查是否漏报问题、用旧版本报告放行或混淆程序通过与人工批准。逐个核对问题定位和修复路线，确认不通过削弱约束来消除错误。对本轮修复产物重新查看受影响检查结果，不能只审核修复计划或声称问题已解决。检查失败或结果未知不得 PASS；需要业务判断的 ESCALATE。输出结构化意见，不改写正式校验报告。",
    ),
    5: (
        "只对已确认并满足前置检查的候选进行确定性编译与打包。按对象语义、关系语义、约束规则、可调用服务、交付与验证配套检查输出完整性，复用真实本体、实例、映射、证据与服务契约，不编造部署能力。模型可以辅助审查可编辑的计划和契约草案，但正式语义图、清单摘要及验证结果由原程序生成。对象读取、查询和动作按真实权限执行；动作示例仅预演，未部署不称可在线调用。批次清单必须提供，验收私有答案不得进入模型输入。",
        "对照冻结候选、专家交付要求和已授权的验收摘要，审核实际编译文件、五类输出的对应关系、版本依赖、证据引用、查询与服务契约、文件哈希及必须提供的批次清单。明确区分包格式有效、语义检查通过、人工批准、服务已部署和下游已接收。检查审计/Prompt 是否关联真实运行、Token 是否来自实际调用；未知用量不能按零统计。只报告遗漏、矛盾和修复路线，不直接编辑 TTL、原生包或校验回执。",
    ),
}
REVISION_PROMPT = "依据本轮固定的专家指导和审核规则，处理当前产物的已验证问题及有权限的人类反馈。只对允许修改范围提出最小补丁，逐项说明对应问题和来源依据；保持无关内容不变。不能通过修改审核标准、删除失败证据、放宽硬规则或改验收答案取得通过。无法安全修复、来源不足或需要前阶段变更时，返回未解决问题与建议目标阶段。不要自行宣称修复已通过；程序应用补丁、运行验证并重新审核后才能确定。仅输出约定的补丁 Schema。"

CRITERIA = {
    1: ["来源与证据闭合", "身份、时间和目标清晰，无遗漏及越界", "不从样本臆造硬规则，歧义保留"],
    2: ["复用与新 IRI 授权有据", "类型、方向、定义域和值域一致，无重复概念", "约束有规则依据且未削弱"],
    3: ["事实与来源、引文和位置一致", "身份与关联有效，值、单位和编码正确", "否定、未知、去重和冲突准确保留"],
    4: ["必需检查针对当前版本真实执行", "问题完整且修复路由正确，不削弱约束", "程序通过与人类审批分开"],
    5: ["五类成果、依赖、来源和契约一致", "确定性编译、文件哈希与必需批次清单", "真实审计及Token与批准、部署、接收状态分开"],
}


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Criterion(ClosedModel):
    criterion_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    description: str = Field(min_length=1, max_length=4000)
    required: bool = True
    source: str = Field(min_length=1, max_length=1000)


class LoopBudget(ClosedModel):
    max_revision_rounds: int = Field(default=3, ge=0, le=3)
    max_model_calls: int = Field(default=64, ge=1, le=128)
    max_seconds: int = Field(default=300, ge=1, le=600)
    max_tokens: int = Field(default=200000, ge=1, le=1000000)
    max_output_tokens: int = Field(default=2000, ge=128, le=8192)
    max_network_retries: int = Field(default=1, ge=0, le=2)


class MethodOverride(ClosedModel):
    pre_guidance_prompt: str | None = Field(default=None, min_length=1, max_length=12000)
    post_review_prompt: str | None = Field(default=None, min_length=1, max_length=12000)


class ExpertConfiguration(ClosedModel):
    stage: int = Field(ge=1, le=5)
    pre_guidance_prompt: str = Field(min_length=1, max_length=12000)
    post_review_prompt: str = Field(min_length=1, max_length=12000)
    criteria: list[Criterion] = Field(min_length=1, max_length=50)
    method_overrides: dict[str, MethodOverride] = Field(default_factory=dict)
    budget: LoopBudget = Field(default_factory=LoopBudget)
    coverage_confirmed: bool = False

    @model_validator(mode="after")
    def validate_criteria(self):
        from .registry import registry
        allowed = {m["method_id"] for m in registry()["methods"] if m["stage"] == self.stage}
        if not set(self.method_overrides).issubset(allowed):
            raise ValueError("EXPERT_METHOD_STAGE_MISMATCH")
        if len({c.criterion_id for c in self.criteria}) != len(self.criteria) or not any(c.required for c in self.criteria):
            raise ValueError("EXPERT_REQUIRED_CRITERIA_INVALID")
        return self


class ReviewCheck(ClosedModel):
    criterion_id: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    reason: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(max_length=100)


class ReviewIssue(ClosedModel):
    issue_id: str = Field(min_length=1, max_length=100)
    criterion_id: str
    severity: Literal["BLOCKING", "WARNING"]
    location: str = Field(min_length=1, max_length=1000)
    description: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(min_length=1, max_length=100)
    target_stage: int = Field(ge=1, le=5)


class ReviewResult(ClosedModel):
    decision: Literal["PASS", "REVISE", "ESCALATE"]
    checks: list[ReviewCheck] = Field(max_length=50)
    issues: list[ReviewIssue] = Field(max_length=100)
    summary: str = Field(min_length=1, max_length=2000)


class PatchItem(ClosedModel):
    target: str = Field(min_length=1, max_length=250)
    field: Literal["description", "in_scope", "out_of_scope", "objects", "targets", "exclusions", "label", "object_iri", "literal", "package_name"]
    value: str | list[str]
    issue_id: str
    evidence_ref: str
    quote: str = Field(min_length=1, max_length=4000)
    quote_start: int = Field(ge=0)


class RevisionPatch(ClosedModel):
    base_digest: str
    changes: list[PatchItem] = Field(max_length=100)
    unresolved: list[str] = Field(max_length=100)


def default_configuration(stage):
    guidance, review = DEFAULT_PROMPTS[stage]
    value = ExpertConfiguration(stage=stage, pre_guidance_prompt=guidance, post_review_prompt=review,
        criteria=[Criterion(criterion_id=f"S{stage}.{i + 1}", description=c, source="DEFAULT_TEMPLATE_20260928")
                  for i, c in enumerate(CRITERIA[stage])]).model_dump()
    return {"version": 0, "digest": semantic_hash(value), "configuration": value,
            "status": "DRAFT", "confirmed_by": None, "confirmed_at": None, "author": None,
            "origin": "DEFAULT_TEMPLATE_NOT_EXPERT_CONFIRMED"}


def resolve_configuration(version, method):
    if version.get("status") != "CONFIRMED" or not version.get("confirmed_by"):
        raise ValueError("EXPERT_CONFIGURATION_UNCONFIRMED")
    config = deepcopy(version["configuration"])
    if int(method.split(".")[0]) != config["stage"]:
        raise ValueError("EXPERT_METHOD_STAGE_MISMATCH")
    override = {k: v for k, v in config.pop("method_overrides", {}).get(method, {}).items() if v is not None}
    return {**config, **override, "version": version["version"], "digest": version["digest"],
            "configuration_source": "METHOD_OVERRIDE" if override else "STAGE_DEFAULT", "method_id": method}


def technical_decision(review, config, evidence, *, program_passed):
    checks = review.get("checks", [])
    by_id = {c["criterion_id"]: c for c in checks}
    allowed = {c["criterion_id"] for c in config["criteria"]}
    required = {c["criterion_id"] for c in config["criteria"] if c["required"]}
    if (len(by_id) != len(checks) or not set(by_id).issubset(allowed) or not required.issubset(by_id)
            or any(not c.get("evidence_refs") or not set(c["evidence_refs"]).issubset(evidence) for c in checks)
            or any(c["status"] == "UNKNOWN" for c in checks)
            or any(i.get("criterion_id") not in allowed or not set(i.get("evidence_refs", [])).issubset(evidence)
                   for i in review.get("issues", []))):
        return "ESCALATE"
    if review["decision"] != "PASS":
        return review["decision"]
    if (not program_passed or any(by_id[c]["status"] != "PASS" for c in required)
            or any(i["severity"] == "BLOCKING" for i in review.get("issues", []))):
        return "ESCALATE"
    return "PASS"

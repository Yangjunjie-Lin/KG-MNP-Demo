#!/usr/bin/env python3
"""Build Stage 03 ontology modules, catalog, inventory, and change logs.

Deterministic: sorted output; no random UUIDs. Re-runnable.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from stage03_constants import (  # noqa: E402
    LICENSE_IRI,
    MODULE_FILES,
    ONTOLOGY_VERSION,
    OPTIONAL_MODULES,
    RUNTIME_MODULES,
    TERM_NS,
    ontology_iri,
    old_term_iri,
    term_iri,
    version_iri,
)
from stage03_term import T, Term  # noqa: E402

LICENSE = LICENSE_IRI


# fmt: off
TERMS: list[Term] = [
    # ---- CORE annotations only ----
    T(local="alignmentStatus", term_type="AnnotationProperty", module="CORE",
      label_en="Alignment Status", label_zh="对齐状态",
      definition_en="Human-reviewed alignment status: VERIFIED, PARTIAL, or LOCAL_ONLY.",
      definition_zh="人工审定的外部对齐状态：VERIFIED、PARTIAL 或 LOCAL_ONLY。",
      source_status="PROJECT_GOVERNANCE", audit_decision="ACCEPT",
      audit_notes="Retained in core as cross-module annotation."),
    T(local="moduleCode", term_type="DatatypeProperty", module="CORE",
      label_en="Module Code", label_zh="模块代码",
      definition_en="Catalog module code identifying the defining ontology module for a term.",
      definition_zh="标识术语所属正式本体模块的目录代码。",
      range="xsd:string", source_status="PROJECT_GOVERNANCE", audit_decision="ACCEPT"),
    T(local="sourceStatus", term_type="AnnotationProperty", module="CORE",
      label_en="Source Status", label_zh="来源状态",
      definition_en="Provenance status of a local term: LOCAL_EXTENSION, INDUSTRY_ALIGNED, STANDARD_REUSED, or PROJECT_GOVERNANCE.",
      definition_zh="本地术语来源状态：LOCAL_EXTENSION、INDUSTRY_ALIGNED、STANDARD_REUSED 或 PROJECT_GOVERNANCE。",
      source_status="PROJECT_GOVERNANCE", audit_decision="ACCEPT"),
    T(local="definingModule", term_type="AnnotationProperty", module="CORE",
      label_en="Defining Module", label_zh="定义模块",
      definition_en="Annotation naming the single defining ontology module for a term.",
      definition_zh="标注术语唯一正式定义模块的注解属性。",
      source_status="PROJECT_GOVERNANCE", audit_decision="ACCEPT"),
    T(local="replacementTerm", term_type="AnnotationProperty", module="CORE",
      label_en="Replacement Term", label_zh="替代术语",
      definition_en="Points from a deprecated term to its recommended replacement.",
      definition_zh="从已弃用术语指向推荐替代术语。",
      source_status="PROJECT_GOVERNANCE", audit_decision="ACCEPT"),

    # ---- IDENTITY ----
    T(local="Subscriber", term_type="Class", module="IDENTITY",
      label_en="Subscriber", label_zh="用户",
      definition_en="A person or organisation that holds telecom subscriptions and may request number portability.",
      definition_zh="持有电信订阅并可申请携号转网的自然人或组织。",
      source_status="INDUSTRY_ALIGNED", audit_decision="MOVE_MODULE",
      audit_notes="Moved from core to identity."),
    T(local="PhoneNumber", term_type="Class", module="IDENTITY",
      label_en="Phone Number", label_zh="电话号码",
      definition_en="A telephone number that may be the subject of an MNP case.",
      definition_zh="可作为携号转网案件标的的电话号码。",
      source_status="LOCAL_EXTENSION", audit_decision="MOVE_MODULE"),
    T(local="NaturalPerson", term_type="Class", module="IDENTITY",
      label_en="Natural Person", label_zh="自然人用户",
      definition_en="A natural person subscriber requesting number portability.",
      definition_zh="申请携号转网的自然人用户。",
      superclass="Subscriber", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="OrganisationSubscriber", term_type="Class", module="IDENTITY",
      label_en="Organisation Subscriber", label_zh="组织用户",
      definition_en="An organisation acting as a telecom subscriber.",
      definition_zh="作为电信用户的组织主体。",
      superclass="Subscriber", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="IdentityDocument", term_type="Class", module="IDENTITY",
      label_en="Identity Document", label_zh="身份证件",
      definition_en="An identity document used for real-name registration.",
      definition_zh="用于实名登记的身份证件。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="RealNameRegistration", term_type="Class", module="IDENTITY",
      label_en="Real Name Registration", label_zh="实名登记",
      definition_en="A real-name registration record linking a subscriber to identity evidence.",
      definition_zh="将用户与身份证据关联的实名登记记录。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="IdentityVerification", term_type="Class", module="IDENTITY",
      label_en="Identity Verification", label_zh="实名核验",
      definition_en="A system observation recording identity match outcome.",
      definition_zh="记录身份比对结果的系统观测。",
      superclass="SystemObservation", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="PhoneNumberOwnership", term_type="Class", module="IDENTITY",
      label_en="Phone Number Ownership Assertion", label_zh="号码归属主张",
      definition_en="An asserted ownership or assignment relationship between a holder and a phone number, distinct from subscription assignment.",
      definition_zh="持有人与号码之间的归属主张，区别于订阅分配关系。",
      source_status="LOCAL_EXTENSION", audit_decision="MODIFY",
      audit_notes="Clarified as assertion class; operational assignment uses assignedToSubscription."),
    T(local="holdsSubscription", term_type="ObjectProperty", module="IDENTITY",
      label_en="holds subscription", label_zh="持有订阅",
      definition_en="Links a subscriber to a service subscription they hold.",
      definition_zh="将用户关联到其持有的服务订阅。",
      domain="Subscriber", range="ServiceSubscription",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT",
      audit_notes="ODR-001 replacement for hasSubscription."),
    T(local="assignedToSubscription", term_type="ObjectProperty", module="IDENTITY",
      label_en="assigned to subscription", label_zh="分配至订阅",
      definition_en="Links a phone number to the service subscription to which it is assigned.",
      definition_zh="将电话号码关联到其被分配的服务订阅。",
      domain="PhoneNumber", range="ServiceSubscription",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT",
      audit_notes="ODR-001; replaces ownsPhoneNumber ownership semantics."),
    T(local="ownsPhoneNumber", term_type="ObjectProperty", module="IDENTITY",
      label_en="owns phone number (deprecated)", label_zh="拥有号码（已弃用）",
      definition_en="Deprecated. Previously linked Subscriber to PhoneNumber with ambiguous ownership semantics.",
      definition_zh="已弃用。原用于连接用户与号码，但“拥有”语义含糊。",
      domain="Subscriber", range="PhoneNumber", deprecated=True,
      replacement="assignedToSubscription",
      source_status="LOCAL_EXTENSION", audit_decision="DEPRECATE",
      audit_notes="ODR-001: use holdsSubscription + assignedToSubscription chain."),
    T(local="hasSubscription", term_type="ObjectProperty", module="IDENTITY",
      label_en="has subscription (deprecated)", label_zh="有订阅（已弃用）",
      definition_en="Deprecated synonym of holdsSubscription.",
      definition_zh="已弃用，请使用 holdsSubscription。",
      domain="Subscriber", range="ServiceSubscription", deprecated=True,
      replacement="holdsSubscription",
      source_status="LOCAL_EXTENSION", audit_decision="DEPRECATE",
      audit_notes="ODR-001."),
    T(local="hasIdentityDocument", term_type="ObjectProperty", module="IDENTITY",
      label_en="has identity document", label_zh="有身份证件",
      definition_en="Links a subscriber to an identity document.",
      definition_zh="将用户关联到身份证件。",
      domain="Subscriber", range="IdentityDocument",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="hasRealNameRegistration", term_type="ObjectProperty", module="IDENTITY",
      label_en="has real-name registration", label_zh="有实名登记",
      definition_en="Links a subscriber to a real-name registration record.",
      definition_zh="将用户关联到实名登记记录。",
      domain="Subscriber", range="RealNameRegistration",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="verifiedBy", term_type="ObjectProperty", module="IDENTITY",
      label_en="verified by", label_zh="由...核验",
      definition_en="Links a real-name registration to an identity verification observation.",
      definition_zh="将实名登记关联到身份核验观测。",
      domain="RealNameRegistration", range="IdentityVerification",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="assertsOwnership", term_type="ObjectProperty", module="IDENTITY",
      label_en="asserts ownership", label_zh="主张归属",
      definition_en="Links an ownership assertion record to a phone number.",
      definition_zh="将归属主张记录关联到电话号码。",
      domain="PhoneNumberOwnership", range="PhoneNumber",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="ownershipHolder", term_type="ObjectProperty", module="IDENTITY",
      label_en="ownership holder", label_zh="归属持有人",
      definition_en="Links an ownership assertion to the asserting subscriber.",
      definition_zh="将归属主张关联到主张方用户。",
      domain="PhoneNumberOwnership", range="Subscriber",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="maskedPhoneNumber", term_type="DatatypeProperty", module="IDENTITY",
      label_en="masked phone number", label_zh="掩码电话号码",
      definition_en="A privacy-preserving masked representation of a phone number.",
      definition_zh="电话号码的隐私掩码表示。",
      domain="PhoneNumber", range="xsd:string",
      source_status="LOCAL_EXTENSION", audit_decision="MOVE_MODULE"),
    T(local="documentTypeCode", term_type="DatatypeProperty", module="IDENTITY",
      label_en="document type code", label_zh="证件类型代码",
      definition_en="Controlled code for identity document type.",
      definition_zh="身份证件类型受控代码。",
      domain="IdentityDocument", range="xsd:string",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="documentNumberMasked", term_type="DatatypeProperty", module="IDENTITY",
      label_en="masked document number", label_zh="掩码证件号",
      definition_en="Masked identity document number.",
      definition_zh="经过掩码处理的证件号码。",
      domain="IdentityDocument", range="xsd:string",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="verificationOutcome", term_type="DatatypeProperty", module="IDENTITY",
      label_en="verification outcome", label_zh="核验结果",
      definition_en="Outcome code of an identity verification.",
      definition_zh="身份核验结果代码。",
      domain="IdentityVerification", range="xsd:string",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),

    # ---- ACCOUNT_BILLING ----
    T(local="TelecomAccount", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Telecom Account", label_zh="电信账户",
      definition_en="A billing or customer account through which services are charged.",
      definition_zh="用于计费或客户管理的电信账户。",
      source_status="INDUSTRY_ALIGNED", audit_decision="MOVE_MODULE"),
    T(local="BillingAccount", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Billing Account", label_zh="计费账户",
      definition_en="A billing account that aggregates charges and payments.",
      definition_zh="汇总费用与缴费的计费账户。",
      superclass="TelecomAccount", source_status="INDUSTRY_ALIGNED", audit_decision="ACCEPT"),
    T(local="Bill", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Bill", label_zh="账单",
      definition_en="A periodic bill issued against a billing account.",
      definition_zh="针对计费账户出具的周期账单。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="Charge", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Charge", label_zh="费用项",
      definition_en="An individual charge line on a bill.",
      definition_zh="账单上的单项费用。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="Payment", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Payment", label_zh="缴费",
      definition_en="A payment applied to a billing account.",
      definition_zh="应用于计费账户的缴费。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="OutstandingBalanceObservation", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Outstanding Balance Observation", label_zh="欠费余额观测",
      definition_en="Observed outstanding balance used as billing evidence.",
      definition_zh="用作计费证据的欠费余额观测。",
      superclass="SystemObservation", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="PaymentArrangement", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Payment Arrangement", label_zh="缴费安排",
      definition_en="An agreed payment plan that may clear portability restrictions.",
      definition_zh="可能解除携转限制的约定缴费安排。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="BillingSettlement", term_type="Class", module="ACCOUNT_BILLING",
      label_en="Billing Settlement", label_zh="计费结清",
      definition_en="A settlement event clearing outstanding balances.",
      definition_zh="结清欠费余额的结算事件。",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="hasBill", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="has bill", label_zh="有账单",
      definition_en="Links a billing account to a bill.",
      definition_zh="将计费账户关联到账单。",
      domain="BillingAccount", range="Bill", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="hasCharge", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="has charge", label_zh="有费用项",
      definition_en="Links a bill to a charge line.",
      definition_zh="将账单关联到费用项。",
      domain="Bill", range="Charge", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="hasPayment", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="has payment", label_zh="有缴费",
      definition_en="Links a billing account to a payment.",
      definition_zh="将计费账户关联到缴费。",
      domain="BillingAccount", range="Payment", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="observesAccount", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="observes account", label_zh="观测账户",
      definition_en="Links an outstanding balance observation to the observed billing account.",
      definition_zh="将欠费观测关联到被观测的计费账户。",
      domain="OutstandingBalanceObservation", range="BillingAccount",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="hasPaymentArrangementRecord", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="has payment arrangement", label_zh="有缴费安排",
      definition_en="Links a billing account to a payment arrangement.",
      definition_zh="将计费账户关联到缴费安排。",
      domain="BillingAccount", range="PaymentArrangement",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="settlesAccount", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="settles account", label_zh="结清账户",
      definition_en="Links a billing settlement to the settled account.",
      definition_zh="将结清事件关联到被结清账户。",
      domain="BillingSettlement", range="BillingAccount",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="relatedAccount", term_type="ObjectProperty", module="ACCOUNT_BILLING",
      label_en="related account (deprecated)", label_zh="相关账户（已弃用）",
      definition_en="Deprecated redundant link from Subscriber to TelecomAccount; use billedThrough on ServiceSubscription.",
      definition_zh="已弃用的用户到账户冗余关系；请使用订阅上的 billedThrough。",
      domain="Subscriber", range="TelecomAccount", deprecated=True,
      replacement="billedThrough",
      source_status="LOCAL_EXTENSION", audit_decision="DEPRECATE",
      audit_notes="ODR-001."),
    T(local="billPeriodStart", term_type="DatatypeProperty", module="ACCOUNT_BILLING",
      label_en="bill period start", label_zh="账期开始",
      definition_en="Start datetime of a bill period.",
      definition_zh="账单账期开始时间。",
      domain="Bill", range="xsd:dateTime", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="billPeriodEnd", term_type="DatatypeProperty", module="ACCOUNT_BILLING",
      label_en="bill period end", label_zh="账期结束",
      definition_en="End datetime of a bill period.",
      definition_zh="账单账期结束时间。",
      domain="Bill", range="xsd:dateTime", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="chargeAmount", term_type="DatatypeProperty", module="ACCOUNT_BILLING",
      label_en="charge amount", label_zh="费用金额",
      definition_en="Monetary amount of a charge.",
      definition_zh="费用项金额。",
      domain="Charge", range="xsd:decimal", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="paymentAmount", term_type="DatatypeProperty", module="ACCOUNT_BILLING",
      label_en="payment amount", label_zh="缴费金额",
      definition_en="Monetary amount of a payment.",
      definition_zh="缴费金额。",
      domain="Payment", range="xsd:decimal", source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
    T(local="arrangementStatusCode", term_type="DatatypeProperty", module="ACCOUNT_BILLING",
      label_en="arrangement status code", label_zh="缴费安排状态码",
      definition_en="Status code of a payment arrangement.",
      definition_zh="缴费安排状态代码。",
      domain="PaymentArrangement", range="xsd:string",
      source_status="LOCAL_EXTENSION", audit_decision="ACCEPT"),
]
# fmt: on


def all_terms() -> list[Term]:
    from stage03_term_catalog_part2 import TERMS_PART2
    from stage03_term_catalog_part3 import TERMS_PART3
    from stage03_term_catalog_part4 import TERMS_PART4

    return TERMS + TERMS_PART2 + TERMS_PART3 + TERMS_PART4


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def emit_term(t: Term) -> str:
    lines: list[str] = []
    iri = f"mnp:{t.local}"
    type_map = {
        "Class": "owl:Class",
        "ObjectProperty": "owl:ObjectProperty",
        "DatatypeProperty": "owl:DatatypeProperty",
        "AnnotationProperty": "owl:AnnotationProperty",
    }
    if t.term_type == "Individual":
        lines.append(f"{iri} a mnp:CodeListEntry ;")
    else:
        types = [type_map[t.term_type]]
        if t.characteristics:
            types.extend(f"owl:{ch}" for ch in t.characteristics.split("|") if ch)
        lines.append(f"{iri} a {', '.join(types)} ;")
    lines.append(f'    rdfs:label "{esc(t.label_en)}"@en ;')
    lines.append(f'    rdfs:label "{esc(t.label_zh)}"@zh-CN ;')
    lines.append(f'    skos:definition "{esc(t.definition_en)}"@en ;')
    lines.append(f'    skos:definition "{esc(t.definition_zh)}"@zh-CN ;')
    code = t.module if t.module in MODULE_FILES else t.module
    mod_file = MODULE_FILES.get(t.module, t.module)
    lines.append(f'    mnp:moduleCode "{code}" ;')
    lines.append(f'    mnp:sourceStatus "{t.source_status}" ;')
    lines.append(f'    mnp:definingModule "{mod_file}" ;')
    if t.superclass:
        lines.append(f"    rdfs:subClassOf mnp:{t.superclass} ;")
    if t.domain:
        lines.append(f"    rdfs:domain mnp:{t.domain} ;")
    if t.range:
        if t.range.startswith("xsd:"):
            lines.append(f"    rdfs:range {t.range} ;")
        else:
            lines.append(f"    rdfs:range mnp:{t.range} ;")
    if t.inverse:
        lines.append(f"    owl:inverseOf mnp:{t.inverse} ;")
    if t.deprecated:
        lines.append("    owl:deprecated true ;")
        if t.replacement:
            lines.append(f"    mnp:replacementTerm mnp:{t.replacement} ;")
            lines.append(
                f'    skos:changeNote "Deprecated in ontology 1.0.0; use mnp:{t.replacement}."@en ;'
            )
    for d in t.disjoint_with:
        lines.append(f"    owl:disjointWith mnp:{d} ;")
    if t.term_type == "Individual":
        lines.append(f'    mnp:codeListName "{esc(t.code_list_name)}" ;')
        lines.append(f'    mnp:codeValue "{esc(t.code_value)}" ;')
        lines.append(f'    mnp:codeLabelEn "{esc(t.code_label_en)}" ;')
        lines.append(f'    mnp:codeLabelZh "{esc(t.code_label_zh)}" ;')
    # Fix trailing semicolon on last line
    lines[-1] = lines[-1].rstrip(" ;") + " ."
    return "\n".join(lines)


def module_header(module_key: str, title_en: str, title_zh: str, desc_en: str, desc_zh: str, imports: list[str]) -> str:
    mod = MODULE_FILES[module_key]
    lines = [
        f"@prefix mnp: <{TERM_NS}> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        f"<{ontology_iri(mod)}> a owl:Ontology ;",
        f"    owl:versionIRI <{version_iri(mod)}> ;",
        f'    owl:versionInfo "{ONTOLOGY_VERSION}" ;',
        f'    dcterms:title "{esc(title_en)}"@en ;',
        f'    dcterms:title "{esc(title_zh)}"@zh-CN ;',
        f'    dcterms:description "{esc(desc_en)}"@en ;',
        f'    dcterms:description "{esc(desc_zh)}"@zh-CN ;',
        f"    dcterms:license <{LICENSE}> ;",
    ]
    for imp in imports:
        lines.append(f"    owl:imports <{ontology_iri(imp)}> ;")
    lines[-1] = lines[-1].rstrip(" ;") + " ."
    lines.append("")
    return "\n".join(lines)


MODULE_META = {
    "CORE": ("KG-MNP Core Annotations", "KG-MNP 核心注解",
             "Cross-module annotation properties and governance metadata for KG-MNP.",
             "KG-MNP 跨模块注解属性与治理元数据。", []),
    "IDENTITY": ("KG-MNP Identity Module", "KG-MNP 身份模块",
                 "Subscribers, phone numbers, identity documents and assignment relations.",
                 "用户、号码、身份证件与分配关系。", ["mnp-core"]),
    "ACCOUNT_BILLING": ("KG-MNP Account and Billing Module", "KG-MNP 账户与计费模块",
                        "Telecom accounts, bills, charges, payments and settlements.",
                        "电信账户、账单、费用、缴费与结清。", ["mnp-core"]),
    "SERVICE_CONTRACT": ("KG-MNP Service and Contract Module", "KG-MNP 业务与合约模块",
                         "Services, subscriptions, contracts and billing linkage.",
                         "服务、订阅、合约与计费关联。", ["mnp-core"]),
    "PROCESS": ("KG-MNP Process Module", "KG-MNP 流程模块",
                "MNP cases, process steps, authorization codes and events.",
                "携转案件、流程步骤、授权码与事件。", ["mnp-core"]),
    "COMPLIANCE": ("KG-MNP Compliance Module", "KG-MNP 合规模块",
                   "Eligibility assessment, decisions, rules, clauses and blocking reasons.",
                   "资格评估、决定、规则、条款与阻塞原因。", ["mnp-core"]),
    "EVIDENCE_TIME": ("KG-MNP Evidence and Time Module", "KG-MNP 证据与时间模块",
                      "Business evidence records, source systems and temporal annotations.",
                      "业务证据、来源系统与时间注解。", ["mnp-core"]),
    "MODELING_PROVENANCE": ("KG-MNP Modeling Provenance Module", "KG-MNP 建模来源模块",
                            "Ontology modeling and mapping provenance concepts (not business case evidence).",
                            "本体建模与映射来源概念（非业务案件证据）。", ["mnp-core"]),
    "CODE_LIST": ("KG-MNP Code List Module", "KG-MNP 码表模块",
                  "Controlled status code individuals for evidence, auth codes and process steps.",
                  "证据、授权码与流程步骤等受控状态码个体。", ["mnp-core"]),
    "ALIGNMENTS": ("KG-MNP Alignments Module", "KG-MNP 对齐模块",
                   "Optional external alignment annotations; not a default runtime import.",
                   "可选外部对齐注解；不作为默认运行时导入。", ["mnp-core"]),
}


def write_modules(terms: list[Term]) -> dict[str, str]:
    by_mod: dict[str, list[Term]] = {}
    for t in terms:
        by_mod.setdefault(t.module, []).append(t)
    written: dict[str, str] = {}
    out_dir = ROOT / "ontology"
    for mod_key, meta in MODULE_META.items():
        header = module_header(mod_key, *meta)
        body_terms = sorted(by_mod.get(mod_key, []), key=lambda x: (x.term_type, x.local))
        # Special: compliance decision disjointness already on classes
        chunks = [emit_term(t) for t in body_terms]
        # Compliance: add producesDecision functional note via characteristics already
        content = header + "\n\n".join(chunks) + "\n"
        path = out_dir / f"{MODULE_FILES[mod_key]}.ttl"
        path.write_text(content, encoding="utf-8")
        written[mod_key] = str(path)
    return written


def write_root() -> Path:
    imports = RUNTIME_MODULES  # not alignments
    lines = [
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "",
        f"<{ontology_iri('kg-mnp')}> a owl:Ontology ;",
        f"    owl:versionIRI <{version_iri('kg-mnp')}> ;",
        f'    owl:versionInfo "{ONTOLOGY_VERSION}" ;',
        '    dcterms:title "KG-MNP Root Ontology"@en ;',
        '    dcterms:title "KG-MNP 根本体"@zh-CN ;',
        '    dcterms:description "Aggregate entry point importing all runtime KG-MNP ontology modules for Protégé offline use."@en ;',
        '    dcterms:description "导入全部运行时本体模块的聚合入口，供 Protégé 离线打开。"@zh-CN ;',
        f"    dcterms:license <{LICENSE}> ;",
    ]
    for m in imports:
        lines.append(f"    owl:imports <{ontology_iri(m)}> ;")
    lines[-1] = lines[-1].rstrip(" ;") + " ."
    lines.append("")
    path = ROOT / "ontology" / "kg-mnp.ttl"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_catalog() -> Path:
    entries: list[tuple[str, str]] = []
    modules = ["kg-mnp"] + RUNTIME_MODULES + OPTIONAL_MODULES
    for m in modules:
        entries.append((ontology_iri(m), f"{m}.ttl"))
        entries.append((version_iri(m), f"{m}.ttl"))
    entries = sorted(set(entries), key=lambda x: x[0])
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        '<catalog xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog" prefer="public">',
    ]
    for uri, filename in entries:
        lines.append(f'    <uri name="{uri}" uri="{filename}"/>')
    lines.append("</catalog>")
    lines.append("")
    path = ROOT / "ontology" / "catalog-v001.xml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_inventory(terms: list[Term]) -> Path:
    path = ROOT / "docs" / "ontology" / "term-inventory.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "term_iri", "local_name", "term_type", "defining_module",
        "label_en", "label_zh_cn", "definition_en", "definition_zh_cn",
        "superclass", "domain", "range", "inverse_property", "characteristics",
        "deprecated", "replacement_term", "source", "source_status",
        "audit_decision", "audit_notes",
    ]
    rows = []
    for t in sorted(terms, key=lambda x: (x.module, x.term_type, x.local)):
        mod = MODULE_FILES.get(t.module, t.module)
        rows.append({
            "term_iri": term_iri(t.local),
            "local_name": t.local,
            "term_type": t.term_type,
            "defining_module": mod,
            "label_en": t.label_en,
            "label_zh_cn": t.label_zh,
            "definition_en": t.definition_en,
            "definition_zh_cn": t.definition_zh,
            "superclass": t.superclass,
            "domain": t.domain,
            "range": t.range,
            "inverse_property": t.inverse,
            "characteristics": t.characteristics,
            "deprecated": "true" if t.deprecated else "false",
            "replacement_term": term_iri(t.replacement) if t.replacement else "",
            "source": t.source,
            "source_status": t.source_status,
            "audit_decision": t.audit_decision,
            "audit_notes": t.audit_notes,
        })
    # Also ontology resources
    for m in ["kg-mnp"] + RUNTIME_MODULES + OPTIONAL_MODULES:
        rows.append({
            "term_iri": ontology_iri(m),
            "local_name": m,
            "term_type": "Ontology",
            "defining_module": m,
            "label_en": m,
            "label_zh_cn": m,
            "definition_en": f"Ontology module resource {m}",
            "definition_zh_cn": f"本体模块资源 {m}",
            "superclass": "", "domain": "", "range": "", "inverse_property": "",
            "characteristics": "", "deprecated": "false", "replacement_term": "",
            "source": "PROJECT_GOVERNANCE", "source_status": "PROJECT_GOVERNANCE",
            "audit_decision": "ACCEPT", "audit_notes": "Ontology document IRI",
        })
    rows = sorted(rows, key=lambda r: (r["term_type"], r["defining_module"], r["local_name"]))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return path


def write_change_log(terms: list[Term]) -> Path:
    path = ROOT / "docs" / "ontology" / "term-change-log.csv"
    fieldnames = [
        "change_id", "term_iri", "change_type", "old_value", "new_value",
        "ontology_version", "rationale", "odr_ref",
    ]
    rows = []
    cid = 1
    for t in sorted(terms, key=lambda x: x.local):
        if t.audit_decision in ("DEPRECATE", "MODIFY", "MOVE_MODULE", "ACCEPT") and (
            t.deprecated or t.audit_decision != "ACCEPT" or t.module != "CORE"
        ):
            if t.deprecated or t.audit_decision in ("DEPRECATE", "MODIFY", "MOVE_MODULE"):
                rows.append({
                    "change_id": f"CL-{cid:04d}",
                    "term_iri": term_iri(t.local),
                    "change_type": t.audit_decision,
                    "old_value": old_term_iri(t.local),
                    "new_value": term_iri(t.replacement) if t.replacement else term_iri(t.local),
                    "ontology_version": ONTOLOGY_VERSION,
                    "rationale": t.audit_notes or t.definition_en,
                    "odr_ref": "",
                })
                cid += 1
    # Explicit priority changes
    priority = [
        ("ownsPhoneNumber", "DEPRECATE", "assignedToSubscription", "ODR-001"),
        ("hasSubscription", "DEPRECATE", "holdsSubscription", "ODR-001"),
        ("billedThrough", "MODIFY", "billedThrough", "ODR-001"),
        ("relatedAccount", "DEPRECATE", "billedThrough", "ODR-001"),
        ("producesBlockingReason", "DEPRECATE", "hasBlockingReason", "ODR-002"),
        ("AssessmentDependency", "DEPRECATE", "usesEvidence", "ODR-004"),
        ("dependsOn", "DEPRECATE", "usesEvidence", "ODR-004"),
        ("dependsOnEvidence", "DEPRECATE", "usesEvidence", "ODR-004"),
        ("dependsOnRuleVersion", "DEPRECATE", "usesRuleVersion", "ODR-004"),
        ("MappingRecord", "MOVE_MODULE", "MappingRecord", "ODR-005"),
    ]
    seen = {r["term_iri"] for r in rows}
    for local, ctype, repl, odr in priority:
        iri = term_iri(local)
        if iri not in seen:
            rows.append({
                "change_id": f"CL-{cid:04d}",
                "term_iri": iri,
                "change_type": ctype,
                "old_value": old_term_iri(local),
                "new_value": term_iri(repl),
                "ontology_version": ONTOLOGY_VERSION,
                "rationale": f"Stage 03 formal decision {odr}",
                "odr_ref": odr,
            })
            cid += 1
    rows = sorted(rows, key=lambda r: r["change_id"])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return path


def write_iri_migration(terms: list[Term]) -> Path:
    path = ROOT / "docs" / "ontology" / "iri-migration.csv"
    fieldnames = [
        "old_iri", "new_iri", "resource_type", "module",
        "migration_action", "compatibility_notes",
    ]
    rows = []
    for t in sorted(terms, key=lambda x: x.local):
        mod = MODULE_FILES.get(t.module, t.module)
        action = "REWRITE"
        notes = ""
        if t.deprecated and t.replacement:
            action = "DEPRECATE_AND_REWRITE_USAGE"
            notes = f"Prefer {term_iri(t.replacement)}"
        rows.append({
            "old_iri": old_term_iri(t.local),
            "new_iri": term_iri(t.local),
            "resource_type": t.term_type,
            "module": mod,
            "migration_action": action,
            "compatibility_notes": notes,
        })
    # Module ontology IRIs
    old_mods = {
        "mnp-core": "core", "mnp-identity": "identity",
        "mnp-account-billing": "account-billing",
        "mnp-service-contract": "service-contract",
        "mnp-process": "process", "mnp-compliance": "compliance",
        "mnp-evidence-time": "evidence-time", "mnp-code-list": "code-list",
        "mnp-alignments": "alignments",
    }
    for new, old in sorted(old_mods.items()):
        rows.append({
            "old_iri": f"http://example.org/kg-mnp/{old}",
            "new_iri": ontology_iri(new),
            "resource_type": "Ontology",
            "module": new,
            "migration_action": "REWRITE",
            "compatibility_notes": f"Also version IRI {version_iri(new)}",
        })
    rows.append({
        "old_iri": "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#",
        "new_iri": TERM_NS,
        "resource_type": "Namespace",
        "module": "kg-mnp",
        "migration_action": "REWRITE",
        "compatibility_notes": "Formal term namespace; instances use data/ base",
    })
    rows = sorted(rows, key=lambda r: (r["resource_type"], r["old_iri"]))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return path


def ontology_hash() -> str:
    h = hashlib.sha256()
    for path in sorted((ROOT / "ontology").glob("*.ttl")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    terms = all_terms()
    # Validate unique defining locals
    seen: dict[str, str] = {}
    for t in terms:
        if t.local in seen and not t.deprecated:
            # allow only one defining declaration
            raise SystemExit(f"Duplicate term local name: {t.local} in {t.module} and {seen[t.local]}")
        seen[t.local] = t.module
    write_modules(terms)
    write_root()
    write_catalog()
    write_inventory(terms)
    write_change_log(terms)
    write_iri_migration(terms)
    print(f"Wrote {len(terms)} terms; ontology hash={ontology_hash()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

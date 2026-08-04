import type { OntologyEdge, OntologyNode } from "../../types/ontology";
import { ontologyClassLabels } from "../../i18n/zh-CN";

/** Snapshot of current runtime ontology classes with catalog modules. */
export const CURRENT_ONTOLOGY_CLASS_SNAPSHOT: Array<{
  localName: string;
  module: string;
  label: string;
}> = [
  { localName: "BillingAccount", module: "ACCOUNT_BILLING", label: "计费账户" },
  { localName: "Bill", module: "ACCOUNT_BILLING", label: "账单" },
  { localName: "Charge", module: "ACCOUNT_BILLING", label: "费用项" },
  { localName: "Payment", module: "ACCOUNT_BILLING", label: "缴费记录" },
  { localName: "OutstandingBalanceObservation", module: "ACCOUNT_BILLING", label: "欠费观测" },
  { localName: "PaymentArrangement", module: "ACCOUNT_BILLING", label: "缴费安排" },
  { localName: "BillingSettlement", module: "ACCOUNT_BILLING", label: "账单结清" },
  { localName: "CodeListEntry", module: "CODE_LIST", label: "码表项" },
  { localName: "ReassessmentMarker", module: "COMPLIANCE", label: "重评标记" },
  { localName: "Subscriber", module: "IDENTITY", label: "订户" },
  { localName: "PhoneNumber", module: "IDENTITY", label: "电话号码" },
  { localName: "TelecomAccount", module: "ACCOUNT_BILLING", label: "电信账户" },
  { localName: "TelecomService", module: "SERVICE_CONTRACT", label: "电信业务" },
  { localName: "ServiceSubscription", module: "SERVICE_CONTRACT", label: "业务订阅" },
  { localName: "ServiceContract", module: "SERVICE_CONTRACT", label: "服务合约" },
  { localName: "MNPCase", module: "PROCESS", label: "携转案件" },
  { localName: "EligibilityAssessment", module: "COMPLIANCE", label: "资格评估" },
  { localName: "EligibilityDecision", module: "COMPLIANCE", label: "资格结论" },
  { localName: "EligibleDecision", module: "COMPLIANCE", label: "可携转结论" },
  { localName: "BlockingDecision", module: "COMPLIANCE", label: "不可携转结论" },
  { localName: "ConditionalDecision", module: "COMPLIANCE", label: "有条件结论" },
  { localName: "ManualReviewDecision", module: "COMPLIANCE", label: "人工复核结论" },
  { localName: "EvidenceRecord", module: "EVIDENCE_TIME", label: "证据记录" },
  { localName: "SystemObservation", module: "EVIDENCE_TIME", label: "系统观测" },
  { localName: "EligibilityRule", module: "COMPLIANCE", label: "资格规则" },
  { localName: "BlockingReason", module: "COMPLIANCE", label: "阻塞原因" },
  { localName: "RemediationAction", module: "COMPLIANCE", label: "处理动作" },
  { localName: "RegulatoryClause", module: "COMPLIANCE", label: "监管条款" },
  { localName: "RegulatoryDocument", module: "COMPLIANCE", label: "监管文件" },
  { localName: "InformationSystem", module: "EVIDENCE_TIME", label: "信息系统" },
  { localName: "RuleVersion", module: "COMPLIANCE", label: "规则版本" },
  { localName: "AssessmentDependency", module: "COMPLIANCE", label: "评估依赖关系" },
  { localName: "MappingRecord", module: "CORE", label: "映射记录" },
  { localName: "APIResponse", module: "EVIDENCE_TIME", label: "接口响应证据" },
  { localName: "EvidenceValidity", module: "EVIDENCE_TIME", label: "证据有效性" },
  { localName: "ObservationTime", module: "EVIDENCE_TIME", label: "观测时间" },
  { localName: "EvaluationTime", module: "EVIDENCE_TIME", label: "评估时间点" },
  { localName: "RecordedTime", module: "EVIDENCE_TIME", label: "记录时间点" },
  { localName: "NaturalPerson", module: "IDENTITY", label: "自然人订户" },
  { localName: "OrganisationSubscriber", module: "IDENTITY", label: "组织订户" },
  { localName: "IdentityDocument", module: "IDENTITY", label: "身份证件" },
  { localName: "RealNameRegistration", module: "IDENTITY", label: "实名登记" },
  { localName: "IdentityVerification", module: "IDENTITY", label: "身份核验" },
  { localName: "PhoneNumberOwnership", module: "IDENTITY", label: "号码归属" },
  { localName: "MNPRequest", module: "PROCESS", label: "携转申请" },
  { localName: "EligibilityCheck", module: "PROCESS", label: "资格检查步骤" },
  { localName: "AuthorizationCodeRequest", module: "PROCESS", label: "授权码申请" },
  { localName: "AuthorizationCode", module: "PROCESS", label: "授权码" },
  { localName: "PortInSubmission", module: "PROCESS", label: "携入提交" },
  { localName: "PortingExecution", module: "PROCESS", label: "携转执行" },
  { localName: "PortingConfirmation", module: "PROCESS", label: "携转确认" },
  { localName: "ProcessStep", module: "PROCESS", label: "流程步骤" },
  { localName: "ProcessEvent", module: "PROCESS", label: "流程事件" },
  { localName: "MNPCaseStatus", module: "PROCESS", label: "案件状态" },
  { localName: "MobilePlan", module: "SERVICE_CONTRACT", label: "移动套餐" },
  { localName: "BroadbandService", module: "SERVICE_CONTRACT", label: "宽带业务" },
  { localName: "ValueAddedService", module: "SERVICE_CONTRACT", label: "增值业务" },
  { localName: "SupplementaryCardService", module: "SERVICE_CONTRACT", label: "副卡业务" },
  { localName: "ConvergedService", module: "SERVICE_CONTRACT", label: "融合业务" },
  { localName: "CommitmentPeriod", module: "SERVICE_CONTRACT", label: "承诺期" },
  { localName: "TerminationAgreement", module: "SERVICE_CONTRACT", label: "解除协议" },
];

export function buildCurrentOntologyNodes(): OntologyNode[] {
  return CURRENT_ONTOLOGY_CLASS_SNAPSHOT.map((item) => ({
    id: `http://example.org/kg-mnp#${item.localName}`,
    localName: item.localName,
    label: item.label || ontologyClassLabels[item.localName] || item.localName,
    module: item.module,
    type: "Class",
    definition: "",
  }));
}

/** Representative whitelist edges for overview routing tests. */
export function buildSampleOverviewEdges(nodes: OntologyNode[]): OntologyEdge[] {
  const byName = new Map(nodes.map((node) => [node.localName, node.id]));
  const link = (from: string, to: string, relation: string, label: string): OntologyEdge | null => {
    const source = byName.get(from);
    const target = byName.get(to);
    if (!source || !target) return null;
    return { from: source, to: target, relation, label };
  };

  return [
    link("Subscriber", "PhoneNumber", "ownsPhoneNumber", "持有号码"),
    link("Subscriber", "IdentityDocument", "hasIdentityDocument", "持有身份证件"),
    link("Subscriber", "RealNameRegistration", "hasRealNameRegistration", "具有实名登记"),
    link("PhoneNumberOwnership", "Subscriber", "ownershipHolder", "归属主体"),
    link("PhoneNumberOwnership", "PhoneNumber", "assertsOwnership", "主张号码归属"),
    link("RealNameRegistration", "IdentityVerification", "verifiedBy", "由核验记录验证"),
    link("TelecomAccount", "BillingAccount", "relatedAccount", "关联账户"),
    link("BillingAccount", "Bill", "hasBill", "包含账单"),
    link("Bill", "Charge", "hasCharge", "包含费用项"),
    link("Bill", "Payment", "hasPayment", "包含缴费"),
    link("OutstandingBalanceObservation", "TelecomAccount", "observesAccount", "观测账户"),
    link("BillingSettlement", "TelecomAccount", "settlesAccount", "结清账户"),
    link("BillingAccount", "PaymentArrangement", "hasPaymentArrangementRecord", "具有缴费安排"),
    link("Subscriber", "TelecomAccount", "billedThrough", "通过账户计费"),
    link("ServiceSubscription", "TelecomService", "subscribesToService", "订阅业务"),
    link("Subscriber", "ServiceSubscription", "hasSubscription", "具有业务订阅"),
    link("ServiceSubscription", "ServiceContract", "governedByContract", "受合约约束"),
    link("ServiceContract", "CommitmentPeriod", "hasCommitmentPeriod", "具有承诺期"),
    link("ServiceContract", "TerminationAgreement", "hasTerminationAgreement", "具有解除协议"),
    link("ServiceContract", "TelecomService", "coversService", "涵盖业务"),
    link("MNPRequest", "Subscriber", "requestedBy", "由订户申请"),
    link("MNPRequest", "PhoneNumber", "concernsNumber", "涉及号码"),
    link("MNPCase", "EligibilityCheck", "hasProcessStep", "具有流程步骤"),
    link("MNPCase", "EligibilityCheck", "currentProcessStep", "当前流程步骤"),
    link("EligibilityCheck", "AuthorizationCodeRequest", "nextProcessStep", "下一流程步骤"),
    link("AuthorizationCodeRequest", "AuthorizationCode", "hasAuthorizationCode", "具有授权码"),
    link("MNPCase", "ProcessEvent", "hasProcessEvent", "具有流程事件"),
    link("MNPCase", "MNPCaseStatus", "hasCaseStatus", "具有案件状态"),
    link("MNPCase", "EligibilityAssessment", "hasEligibilityAssessment", "包含资格评估"),
    link("EligibilityAssessment", "EvidenceRecord", "usesEvidence", "使用证据"),
    link("EligibilityAssessment", "EligibilityRule", "evaluatedByRule", "依据规则评估"),
    link("EligibilityRule", "RuleVersion", "usesRuleVersion", "使用规则版本"),
    link("EligibilityAssessment", "EligibilityDecision", "producesDecision", "产生资格结论"),
    link("EligibilityAssessment", "BlockingReason", "producesBlockingReason", "产生阻塞原因"),
    link("BlockingReason", "RemediationAction", "recommendsAction", "建议处理动作"),
    link("EligibilityRule", "RegulatoryClause", "operationalizesClause", "落实监管条款"),
    link("RegulatoryClause", "RegulatoryDocument", "partOfDocument", "属于监管文件"),
    link("EvidenceRecord", "InformationSystem", "hasSourceSystem", "来自信息系统"),
    link("BlockingReason", "EvidenceRecord", "supportedByEvidence", "由证据支持"),
    link("BlockingReason", "EligibilityRule", "triggeredByRule", "由规则触发"),
    link("BlockingReason", "RuleVersion", "triggeredByRuleVersion", "由规则版本触发"),
    link("RuleVersion", "RegulatoryClause", "citesClause", "引用监管条款"),
    link("AssessmentDependency", "EligibilityRule", "dependsOn", "依赖"),
    link("AssessmentDependency", "RuleVersion", "dependsOnRuleVersion", "依赖规则版本"),
    link("AssessmentDependency", "EvidenceRecord", "dependsOnEvidence", "依赖证据"),
    // secondary (not in whitelist)
    link("EligibilityCheck", "ProcessStep", "subClassOf", "属于上位类"),
    link("MobilePlan", "TelecomService", "subClassOf", "属于上位类"),
  ].filter((edge): edge is OntologyEdge => edge !== null);
}

import type { OntologyEdge, OntologyModule, OntologyNode } from "../types/ontology";
import {
  moduleLabels,
  ontologyClassLabels,
  ontologyRelationLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";

export const mockOntologyModules: OntologyModule[] = [
  { id: "Core", label: moduleLabels.Core, description: "携转资格评估的核心类与属性" },
  { id: "Identity", label: moduleLabels.Identity, description: "订户、号码与身份证件" },
  { id: "AccountBilling", label: moduleLabels.AccountBilling, description: "账户、账单与欠费观测" },
  { id: "Contract", label: moduleLabels.Contract, description: "服务合约与解除协议" },
  { id: "MNPProcess", label: moduleLabels.MNPProcess, description: "携转流程、授权码与步骤" },
  { id: "Eligibility", label: moduleLabels.Eligibility, description: "资格结论、阻塞原因与处理动作" },
  { id: "Evidence", label: moduleLabels.Evidence, description: "证据记录与有效性" },
  { id: "Rules", label: moduleLabels.Rules, description: "资格规则与版本" },
  { id: "Regulatory", label: moduleLabels.Regulatory, description: "监管条款依据" },
];

function node(
  id: string,
  module: string,
  x: number,
  y: number,
  definition: string,
  localName = id,
): OntologyNode {
  return {
    id,
    localName,
    label: translateOrUnknown(ontologyClassLabels, localName, ui.unknownOntologyClass),
    module,
    type: "Class",
    x,
    y,
    definition,
  };
}

export const mockOntologyNodes: OntologyNode[] = [
  node("Case", "Core", 130, 230, "一个携号转网申请案件的完整表示。", "MNPCase"),
  node("Assessment", "Core", 310, 230, "对某个案件执行的一次完整资格评估。", "EligibilityAssessment"),
  node("Decision", "Core", 490, 150, "评估的最终资格结论。", "EligibilityDecision"),
  node("EligibilityStatus", "Core", 490, 310, "针对每条规则输出的资格状态。"),
  node("Subscriber", "Identity", 130, 100, "移动通信服务订户。"),
  node("PhoneNumber", "Identity", 310, 80, "携转操作的主体号码。"),
  node("IdentityDocument", "Identity", 130, 380, "用户身份证明文件。"),
  node("Account", "AccountBilling", 490, 60, "计费账户。", "Account"),
  node("Invoice", "AccountBilling", 650, 60, "单张账单。"),
  node("ServiceContract", "Contract", 650, 230, "服务合约。"),
  node("PortingRequest", "MNPProcess", 650, 150, "一次具体的携号转网申请。"),
  node("AuthorizationCode", "MNPProcess", 780, 80, "携转授权码。"),
  node("BlockingReason", "Eligibility", 490, 410, "导致不可携转的具体原因。"),
  node("RemediationAction", "Eligibility", 650, 410, "针对阻塞原因的建议处理动作。"),
  node("Evidence", "Evidence", 310, 380, "支持评估决策的证据记录。", "EvidenceRecord"),
  node("Rule", "Rules", 130, 480, "资格判断规则。", "EligibilityRule"),
  node("RuleVersion", "Rules", 310, 480, "规则的版本化实例。"),
  node("RegulatoryClause", "Regulatory", 490, 480, "规则的监管条款依据。"),
];

function edge(from: string, to: string, relation: string): OntologyEdge {
  return {
    from,
    to,
    relation,
    label: translateOrUnknown(
      ontologyRelationLabels,
      relation,
      ui.unknownOntologyRelation,
    ),
  };
}

export const mockOntologyEdges: OntologyEdge[] = [
  edge("Case", "Assessment", "hasAssessment"),
  edge("Case", "Subscriber", "hasSubscriber"),
  edge("Case", "PhoneNumber", "hasPhoneNumber"),
  edge("Assessment", "Decision", "hasDecision"),
  edge("Assessment", "Evidence", "usesEvidence"),
  edge("Assessment", "BlockingReason", "hasBlockingReason"),
  edge("Assessment", "EligibilityStatus", "hasEligibilityStatus"),
  edge("BlockingReason", "RemediationAction", "hasRemediation"),
  edge("BlockingReason", "Rule", "triggeredBy"),
  edge("Rule", "RuleVersion", "hasVersion"),
  edge("RuleVersion", "RegulatoryClause", "citesClause"),
  edge("Evidence", "IdentityDocument", "references"),
  edge("Subscriber", "Account", "hasAccount"),
  edge("Account", "Invoice", "hasInvoice"),
  edge("Case", "ServiceContract", "hasContract"),
  edge("Case", "PortingRequest", "initiates"),
  edge("PortingRequest", "AuthorizationCode", "requiresAuthCode"),
];

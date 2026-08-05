import {
  ontologyClassLabels,
  ontologyRelationLabels,
  translateOrUnknown,
  ui,
} from "../i18n/zh-CN";

const EXTRA_CLASS_LABELS: Record<string, string> = {
  APIResponse: "接口响应证据",
  "API响应证据": "接口响应证据",
  RuleVersion: "规则版本",
  "Rule版本": "规则版本",
  MNPCase: "携转案件",
  "MNP案件": "携转案件",
  Operator: "运营商",
  "Operator记录": "运营商记录",
  DonorOperator: "携出方运营商",
  RecipientOperator: "携入方运营商",
  TelecomOperator: "运营商",
  UserRight: "用户权益",
};

const EXTRA_RELATION_LABELS: Record<string, string> = {
  hasRealNameRegistration: "具有实名记录",
  verifiedBy: "验证",
  ownsPhoneNumber: "持有／使用",
  assertsOwnership: "持有／使用",
  ownershipHolder: "持有／使用",
  billedThrough: "拥有",
  relatedAccount: "拥有",
  hasBill: "生成",
  hasCharge: "生成",
  hasPayment: "结清",
  hasPaymentArrangementRecord: "结清",
  settlesAccount: "结清",
  hasSubscription: "订购",
  subscribesToService: "订购",
  governedByContract: "受约束于",
  coversService: "关联",
  requestedBy: "提交",
  concernsNumber: "申请携转号码",
  hasProcessStep: "包含",
  hasAuthorizationCode: "获得",
  hasProcessEvent: "可能触发",
  hasCaseStatus: "产生",
  hasEligibilityAssessment: "触发",
  dependsOn: "检查",
  evaluatedByRule: "依据",
  producesBlockingReason: "识别",
  recommendsAction: "建议",
  supportedByEvidence: "由证据支持",
  usesEvidence: "引用",
  hasSourceSystem: "来源于",
};

function containsLatin(value: string): boolean {
  return /[A-Za-z]/.test(value);
}

function containsChinese(value: string): boolean {
  return /[\u3400-\u9fff]/u.test(value);
}

function localNameOf(value: string): string {
  if (!value) return "";
  const hash = value.lastIndexOf("#");
  if (hash >= 0) return value.slice(hash + 1);
  const slash = value.lastIndexOf("/");
  if (slash >= 0) return value.slice(slash + 1);
  return value;
}

/**
 * Resolve Chinese display label for graph nodes/edges.
 * Priority: API zh → project mapping → rdfs zh → pure Chinese backend → unknown.
 * Mixed CN/EN technical strings must go through mapping; never "has Chinese ⇒ show as-is".
 */
export function resolveGraphChineseLabel(input: {
  apiLabelZh?: string | null;
  localName?: string | null;
  fallbackLabel?: string | null;
  kind: "class" | "relation";
}): string {
  const api = (input.apiLabelZh ?? "").trim();
  if (api && containsChinese(api) && !containsLatin(api)) {
    return api;
  }
  if (api && EXTRA_CLASS_LABELS[api]) return EXTRA_CLASS_LABELS[api];
  if (api && EXTRA_RELATION_LABELS[api]) return EXTRA_RELATION_LABELS[api];

  const key = localNameOf(input.localName ?? "") || localNameOf(api);
  if (key) {
    if (input.kind === "class") {
      if (EXTRA_CLASS_LABELS[key]) return EXTRA_CLASS_LABELS[key];
      if (ontologyClassLabels[key]) return ontologyClassLabels[key];
    } else {
      if (EXTRA_RELATION_LABELS[key]) return EXTRA_RELATION_LABELS[key];
      if (ontologyRelationLabels[key]) return ontologyRelationLabels[key];
    }
  }

  const fallback = (input.fallbackLabel ?? "").trim();
  if (fallback && containsChinese(fallback) && !containsLatin(fallback)) {
    return fallback;
  }
  if (fallback && EXTRA_CLASS_LABELS[fallback]) return EXTRA_CLASS_LABELS[fallback];
  if (fallback && EXTRA_RELATION_LABELS[fallback]) {
    return EXTRA_RELATION_LABELS[fallback];
  }

  if (key) {
    return translateOrUnknown(
      input.kind === "class" ? ontologyClassLabels : ontologyRelationLabels,
      key,
      input.kind === "class" ? ui.unknownOntologyClass : ui.unknownOntologyRelation,
    );
  }

  return input.kind === "class"
    ? "未识别业务概念"
    : "未识别业务关系";
}

export function wrapNodeLabel(label: string, maxCharsPerLine = 8): string[] {
  const chars = [...label];
  if (chars.length <= maxCharsPerLine) return [label];
  const first = chars.slice(0, maxCharsPerLine).join("");
  const rest = chars.slice(maxCharsPerLine);
  if (rest.length <= maxCharsPerLine) return [first, rest.join("")];
  return [first, `${rest.slice(0, maxCharsPerLine - 1).join("")}…`];
}

export function collapsedRelationLabel(labels: string[]): string {
  if (labels.length <= 1) return labels[0] ?? "未识别业务关系";
  return `${labels.length} 项关系`;
}

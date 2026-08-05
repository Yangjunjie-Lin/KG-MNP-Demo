import type { BusinessLayerId, BusinessRoleId } from "./graphTypes";
import { BUSINESS_WORLD } from "./businessLayerConfig";

export const CORE_NODE_SIZE = { width: 150, height: 54 } as const;
export const LONG_NODE_SIZE = { width: 180, height: 58 } as const;
export const SAFETY_CHECK_SIZE = { width: 190, height: 88 } as const;
export const EXTENSION_NODE_SIZE = { width: 142, height: 46 } as const;

export const MAX_ANCHOR_DEVIATION_X = 40;
export const MAX_ANCHOR_DEVIATION_Y = 24;

export interface CoreRoleDefinition {
  id: BusinessRoleId;
  layerId: BusinessLayerId;
  labelZh: string;
  anchor: { x: number; y: number };
  size: { width: number; height: number };
}

export const CORE_ROLE_ANCHORS: Record<BusinessRoleId, { x: number; y: number }> =
  {
    USER: { x: 0.2, y: 0.07 },
    VERIFICATION: { x: 0.4, y: 0.07 },
    MOBILE_NUMBER_IDENTITY: { x: 0.63, y: 0.07 },
    OPERATOR_CURRENT: { x: 0.87, y: 0.07 },

    ACCOUNT: { x: 0.28, y: 0.25 },
    BILL: { x: 0.52, y: 0.25 },
    PAYMENT: { x: 0.8, y: 0.25 },

    TARIFF_PLAN: { x: 0.22, y: 0.4 },
    CONTRACT: { x: 0.38, y: 0.4 },
    BROADBAND: { x: 0.55, y: 0.4 },
    VALUE_ADDED_SERVICE: { x: 0.72, y: 0.4 },
    USER_RIGHT: { x: 0.88, y: 0.4 },

    PORT_REQUEST: { x: 0.23, y: 0.58 },
    MOBILE_NUMBER_PORT: { x: 0.4, y: 0.545 },
    OPERATOR_DONOR: { x: 0.4, y: 0.58 },
    OPERATOR_RECIPIENT: { x: 0.4, y: 0.65 },
    PORT_STEP: { x: 0.57, y: 0.58 },
    AUTH_CODE: { x: 0.68, y: 0.58 },
    EXCEPTION_EVENT: { x: 0.79, y: 0.58 },
    IMPACT: { x: 0.91, y: 0.58 },

    ELIGIBILITY_CONDITION: { x: 0.24, y: 0.76 },
    REGULATION_RULE: { x: 0.24, y: 0.89 },
    SAFETY_CHECK: { x: 0.49, y: 0.76 },
    BLOCK_REASON: { x: 0.69, y: 0.76 },
    REMEDIATION_ACTION: { x: 0.87, y: 0.76 },
    EVIDENCE: { x: 0.69, y: 0.89 },
    OPERATOR_EVIDENCE: { x: 0.87, y: 0.89 },
  };

export const CORE_ROLE_LABELS: Record<BusinessRoleId, string> = {
  USER: "用户",
  VERIFICATION: "实名认证记录",
  MOBILE_NUMBER_IDENTITY: "手机号码",
  OPERATOR_CURRENT: "运营商",
  ACCOUNT: "账户",
  BILL: "账单",
  PAYMENT: "缴费记录",
  TARIFF_PLAN: "套餐",
  CONTRACT: "合同",
  BROADBAND: "宽带",
  VALUE_ADDED_SERVICE: "增值业务",
  USER_RIGHT: "用户权益",
  PORT_REQUEST: "携转申请",
  MOBILE_NUMBER_PORT: "手机号码",
  OPERATOR_DONOR: "运营商（携出方）",
  OPERATOR_RECIPIENT: "运营商（携入方）",
  PORT_STEP: "办理步骤",
  AUTH_CODE: "授权码",
  EXCEPTION_EVENT: "异常事件",
  IMPACT: "影响结果",
  ELIGIBILITY_CONDITION: "资格条件",
  REGULATION_RULE: "监管规则",
  SAFETY_CHECK: "安全检查",
  BLOCK_REASON: "阻塞原因",
  REMEDIATION_ACTION: "处理措施",
  EVIDENCE: "证据",
  OPERATOR_EVIDENCE: "运营商",
};

export const ROLE_LAYER: Record<BusinessRoleId, BusinessLayerId> = {
  USER: "USER_IDENTITY",
  VERIFICATION: "USER_IDENTITY",
  MOBILE_NUMBER_IDENTITY: "USER_IDENTITY",
  OPERATOR_CURRENT: "USER_IDENTITY",
  ACCOUNT: "ACCOUNT_BILLING",
  BILL: "ACCOUNT_BILLING",
  PAYMENT: "ACCOUNT_BILLING",
  TARIFF_PLAN: "SERVICE_OFFERING",
  CONTRACT: "SERVICE_OFFERING",
  BROADBAND: "SERVICE_OFFERING",
  VALUE_ADDED_SERVICE: "SERVICE_OFFERING",
  USER_RIGHT: "SERVICE_OFFERING",
  PORT_REQUEST: "PORTABILITY_PROCESS",
  MOBILE_NUMBER_PORT: "PORTABILITY_PROCESS",
  OPERATOR_DONOR: "PORTABILITY_PROCESS",
  OPERATOR_RECIPIENT: "PORTABILITY_PROCESS",
  PORT_STEP: "PORTABILITY_PROCESS",
  AUTH_CODE: "PORTABILITY_PROCESS",
  EXCEPTION_EVENT: "PORTABILITY_PROCESS",
  IMPACT: "PORTABILITY_PROCESS",
  ELIGIBILITY_CONDITION: "QUALIFICATION_COMPLIANCE",
  REGULATION_RULE: "QUALIFICATION_COMPLIANCE",
  SAFETY_CHECK: "QUALIFICATION_COMPLIANCE",
  BLOCK_REASON: "QUALIFICATION_COMPLIANCE",
  REMEDIATION_ACTION: "QUALIFICATION_COMPLIANCE",
  EVIDENCE: "QUALIFICATION_COMPLIANCE",
  OPERATOR_EVIDENCE: "QUALIFICATION_COMPLIANCE",
};

export const CORE_ROLES_BY_LAYER: Record<BusinessLayerId, BusinessRoleId[]> = {
  USER_IDENTITY: [
    "USER",
    "VERIFICATION",
    "MOBILE_NUMBER_IDENTITY",
    "OPERATOR_CURRENT",
  ],
  ACCOUNT_BILLING: ["ACCOUNT", "BILL", "PAYMENT"],
  SERVICE_OFFERING: [
    "TARIFF_PLAN",
    "CONTRACT",
    "BROADBAND",
    "VALUE_ADDED_SERVICE",
    "USER_RIGHT",
  ],
  PORTABILITY_PROCESS: [
    "PORT_REQUEST",
    "MOBILE_NUMBER_PORT",
    "OPERATOR_DONOR",
    "OPERATOR_RECIPIENT",
    "PORT_STEP",
    "AUTH_CODE",
    "EXCEPTION_EVENT",
    "IMPACT",
  ],
  QUALIFICATION_COMPLIANCE: [
    "ELIGIBILITY_CONDITION",
    "REGULATION_RULE",
    "SAFETY_CHECK",
    "BLOCK_REASON",
    "REMEDIATION_ACTION",
    "EVIDENCE",
    "OPERATOR_EVIDENCE",
  ],
};

export const ALL_CORE_ROLES: BusinessRoleId[] = Object.keys(
  CORE_ROLE_ANCHORS,
) as BusinessRoleId[];

export function roleNodeSize(roleId: BusinessRoleId): {
  width: number;
  height: number;
} {
  if (roleId === "SAFETY_CHECK") return { ...SAFETY_CHECK_SIZE };
  if (
    roleId === "OPERATOR_DONOR" ||
    roleId === "OPERATOR_RECIPIENT" ||
    roleId === "MOBILE_NUMBER_IDENTITY" ||
    roleId === "MOBILE_NUMBER_PORT" ||
    roleId === "ELIGIBILITY_CONDITION" ||
    roleId === "VALUE_ADDED_SERVICE"
  ) {
    return { ...LONG_NODE_SIZE };
  }
  return { ...CORE_NODE_SIZE };
}

export function getCoreRoleDefinitions(): CoreRoleDefinition[] {
  return ALL_CORE_ROLES.map((id) => ({
    id,
    layerId: ROLE_LAYER[id],
    labelZh: CORE_ROLE_LABELS[id],
    anchor: CORE_ROLE_ANCHORS[id],
    size: roleNodeSize(id),
  }));
}

export function anchorToCenter(
  anchor: { x: number; y: number },
  worldWidth = BUSINESS_WORLD.width,
  worldHeight = BUSINESS_WORLD.height,
): { cx: number; cy: number } {
  return {
    cx: anchor.x * worldWidth,
    cy: anchor.y * worldHeight,
  };
}

/** Structural overview relations (presentation only, not RDF facts). */
export interface StructuralRelation {
  id: string;
  fromRole: BusinessRoleId;
  toRole: BusinessRoleId;
  labelZh: string;
  group?: string;
}

export const STRUCTURAL_RELATIONS: StructuralRelation[] = [
  {
    id: "struct-user-verification",
    fromRole: "USER",
    toRole: "VERIFICATION",
    labelZh: "具有实名记录",
  },
  {
    id: "struct-verification-number",
    fromRole: "VERIFICATION",
    toRole: "MOBILE_NUMBER_IDENTITY",
    labelZh: "验证",
  },
  {
    id: "struct-user-number",
    fromRole: "USER",
    toRole: "MOBILE_NUMBER_IDENTITY",
    labelZh: "持有／使用",
  },
  {
    id: "struct-number-operator-service",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "OPERATOR_CURRENT",
    labelZh: "当前服务",
  },
  {
    id: "struct-number-operator-alloc",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "OPERATOR_CURRENT",
    labelZh: "初始分配",
  },
  {
    id: "struct-user-account",
    fromRole: "USER",
    toRole: "ACCOUNT",
    labelZh: "拥有",
  },
  {
    id: "struct-account-bill",
    fromRole: "ACCOUNT",
    toRole: "BILL",
    labelZh: "生成",
  },
  {
    id: "struct-bill-payment",
    fromRole: "BILL",
    toRole: "PAYMENT",
    labelZh: "结清",
  },
  {
    id: "struct-number-plan",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "TARIFF_PLAN",
    labelZh: "订购",
    group: "service-bus",
  },
  {
    id: "struct-number-contract",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "CONTRACT",
    labelZh: "受约束于",
    group: "service-bus",
  },
  {
    id: "struct-number-broadband",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "BROADBAND",
    labelZh: "关联",
    group: "service-bus",
  },
  {
    id: "struct-number-vas",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "VALUE_ADDED_SERVICE",
    labelZh: "使用",
    group: "service-bus",
  },
  {
    id: "struct-number-right",
    fromRole: "MOBILE_NUMBER_IDENTITY",
    toRole: "USER_RIGHT",
    labelZh: "享有",
    group: "service-bus",
  },
  {
    id: "struct-user-port",
    fromRole: "USER",
    toRole: "PORT_REQUEST",
    labelZh: "提交",
  },
  {
    id: "struct-port-number",
    fromRole: "PORT_REQUEST",
    toRole: "MOBILE_NUMBER_PORT",
    labelZh: "申请携转号码",
  },
  {
    id: "struct-port-donor",
    fromRole: "PORT_REQUEST",
    toRole: "OPERATOR_DONOR",
    labelZh: "携出自",
  },
  {
    id: "struct-port-recipient",
    fromRole: "PORT_REQUEST",
    toRole: "OPERATOR_RECIPIENT",
    labelZh: "携入至",
  },
  {
    id: "struct-donor-step",
    fromRole: "OPERATOR_DONOR",
    toRole: "PORT_STEP",
    labelZh: "包含",
  },
  {
    id: "struct-step-auth",
    fromRole: "PORT_STEP",
    toRole: "AUTH_CODE",
    labelZh: "获得",
  },
  {
    id: "struct-auth-exception",
    fromRole: "AUTH_CODE",
    toRole: "EXCEPTION_EVENT",
    labelZh: "可能触发",
  },
  {
    id: "struct-exception-impact",
    fromRole: "EXCEPTION_EVENT",
    toRole: "IMPACT",
    labelZh: "产生",
  },
  {
    id: "struct-port-eligibility",
    fromRole: "PORT_REQUEST",
    toRole: "ELIGIBILITY_CONDITION",
    labelZh: "触发",
  },
  {
    id: "struct-safety-condition",
    fromRole: "SAFETY_CHECK",
    toRole: "ELIGIBILITY_CONDITION",
    labelZh: "检查",
  },
  {
    id: "struct-condition-rule",
    fromRole: "ELIGIBILITY_CONDITION",
    toRole: "REGULATION_RULE",
    labelZh: "依据",
  },
  {
    id: "struct-safety-block",
    fromRole: "SAFETY_CHECK",
    toRole: "BLOCK_REASON",
    labelZh: "识别",
  },
  {
    id: "struct-block-remediation",
    fromRole: "BLOCK_REASON",
    toRole: "REMEDIATION_ACTION",
    labelZh: "建议",
  },
  {
    id: "struct-block-evidence",
    fromRole: "BLOCK_REASON",
    toRole: "EVIDENCE",
    labelZh: "由证据支持",
  },
  {
    id: "struct-safety-evidence",
    fromRole: "SAFETY_CHECK",
    toRole: "EVIDENCE",
    labelZh: "引用",
  },
  {
    id: "struct-evidence-operator",
    fromRole: "EVIDENCE",
    toRole: "OPERATOR_EVIDENCE",
    labelZh: "来源于",
  },
];

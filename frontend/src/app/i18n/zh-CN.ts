export function t(map: Record<string, string>, key: string, fallback?: string): string {
  return map[key] ?? fallback ?? key;
}

/**
 * 安全中文映射：找不到映射时返回中文未知提示，绝不回退渲染原始英文值。
 * 原始值仅写入 console.warn，便于开发排查。
 */
export function translateOrUnknown(
  map: Record<string, string>,
  key: string | null | undefined,
  unknownLabel = "未识别信息",
): string {
  if (key == null || String(key).trim() === "") {
    return "暂无信息";
  }
  const resolved = map[key];
  if (resolved != null && resolved !== "") {
    return resolved;
  }
  if (typeof console !== "undefined" && typeof console.warn === "function") {
    console.warn(`[i18n] 未登记映射值: ${key}`);
  }
  return unknownLabel;
}

export const decisionLabels: Record<string, string> = {
  ELIGIBLE: "可携转",
  BLOCKED: "不可携转",
  MANUAL_REVIEW: "需要人工复核",
  CONDITIONAL: "有条件通过",
  UNKNOWN: "结论未识别",
};

export const stepStatusLabels: Record<string, string> = {
  PASS: "通过",
  PASSED: "通过",
  FAIL: "未通过",
  FAILED: "未通过",
  DONE: "已完成",
  SKIPPED: "已跳过",
  SKIP: "已跳过",
  PENDING: "待处理",
  NOT_EVALUATED: "尚未评估",
};

export const evidenceStatusLabels: Record<string, string> = {
  VALID: "有效",
  EXPIRED: "已过期",
  REVOKED: "已撤销",
  UNKNOWN: "未知",
  MISSING: "缺失",
  CONFLICT: "存在冲突",
};

export const publicationStatusLabels: Record<string, string> = {
  PUBLISHABLE: "可发布",
  NOT_PUBLISHABLE: "不可发布",
};

export const pipelineStepLabels: Record<string, string> = {
  "JSON Schema": "结构化输入校验",
  json_schema: "结构化输入校验",
  "json-schema": "结构化输入校验",
  "RDF Builder": "知识图谱构建",
  rdf_builder: "知识图谱构建",
  "rdf-builder": "知识图谱构建",
  "Input SHACL": "输入图约束校验",
  input_graph: "输入图约束校验",
  input_shacl: "输入图约束校验",
  "input-shacl": "输入图约束校验",
  "OWL-RL": "语义关系推导",
  owlrl: "语义关系推导",
  "owl-rl": "语义关系推导",
  "Rule Engine": "资格规则执行",
  rule_engine: "资格规则执行",
  "rule-engine": "资格规则执行",
  Assessment: "评估结果生成",
  assessment: "评估结果生成",
  assessment_materialization: "评估结果生成",
  "Assessment SHACL": "评估图约束校验",
  assessment_graph: "评估图约束校验",
  assessment_shacl: "评估图约束校验",
  "assessment-shacl": "评估图约束校验",
  "SPARQL Trace": "可追溯关系查询",
  sparql_trace: "可追溯关系查询",
  "sparql-trace": "可追溯关系查询",
};

export const evidenceTypeLabels: Record<string, string> = {
  IDENTITY_MATCH: "实名一致性证据",
  IdentityEvidence: "实名一致性证据",
  NUMBER_STATUS: "号码状态证据",
  NumberStatusEvidence: "号码状态证据",
  BILLING_BALANCE: "计费余额证据",
  BillingEvidence: "计费余额证据",
  CONTRACT_STATUS: "合约状态证据",
  ContractEvidence: "合约状态证据",
  PORTING_HISTORY: "携转历史证据",
  PortingHistoryEvidence: "携转历史证据",
};

export const blockingReasonLabels: Record<string, string> = {
  REAL_NAME_MISMATCH: "实名信息不一致",
  NUMBER_STATUS_INVALID: "号码状态异常",
  OUTSTANDING_BALANCE: "存在未结费用",
  ACTIVE_CONTRACT_RESTRICTION: "存在有效合约限制",
  PORTING_INTERVAL_TOO_SHORT: "携转间隔不足",
  PORTING_INTERVAL_NOT_MET: "携转间隔不足",
  MISSING_OR_EXPIRED_EVIDENCE: "关键证据缺失或过期",
  AUTHORIZATION_CODE_EXPIRED: "授权码已过期",
  AUTHORIZATION_CODE_MISSING: "授权码不存在",
  TERMINATION_NOT_EFFECTIVE: "解除协议尚未生效",
  ELIGIBILITY_NOT_PASSED: "资格评估未通过",
  ELIGIBILITY_NOT_EVALUATED: "资格评估尚未完成",
};

export const remediationActionLabels: Record<string, string> = {
  VERIFY_IDENTITY: "核验并更新身份信息",
  RESTORE_NUMBER_STATUS: "恢复号码正常状态",
  SETTLE_OUTSTANDING_FEES: "结清未付费用",
  WAIT_OR_TERMINATE_CONTRACT: "等待合约到期或办理解约",
  WAIT_PORTING_INTERVAL: "等待满足携转间隔",
  WAIT_UNTIL_INTERVAL_MET: "等待满足携转间隔",
};

export const regulatoryClauseLabels: Record<string, string> = {
  "REG-MNP-CLAUSE-01": "监管条款一：实名信息一致性",
  "REG-MNP-CLAUSE-02": "监管条款二：号码状态要求",
  "REG-MNP-CLAUSE-03": "监管条款三：费用结清要求",
  "REG-MNP-CLAUSE-04": "监管条款四：合约限制要求",
  "REG-MNP-CLAUSE-05": "监管条款五：携转间隔要求",
};

export const processStepLabels: Record<string, string> = {
  ELIGIBILITY_CHECK: "资格检查",
  AUTHORIZATION: "授权码申请",
  AUTHORIZATION_CODE_REQUEST: "授权码申请",
  PORT_IN_SUBMISSION: "转入申请提交",
  PORTING_EXECUTION: "携转执行",
  PORTING_CONFIRMATION: "携转确认",
};

export const dataSourceLabels: Record<string, string> = {
  CRM: "客户关系系统",
  HLR: "号码状态系统",
  BILLING: "计费系统",
  CONTRACT: "合约管理系统",
  MNP_HISTORY: "携转历史系统",
};

export const caseLabels: Record<string, string> = {
  "CASE-01": "案例一",
  "CASE-02": "案例二",
  "CASE-03": "案例三",
  "CASE-04": "案例四",
  "CASE-05": "案例五",
  "CASE-06": "案例六",
  "CASE-07": "案例七",
  "CASE-08": "案例八",
  "CASE-09": "案例九",
};

export const assessmentLabels: Record<string, string> = {
  "CASE-06-HIST": "案例六历史评估",
  "CASE-06-CURRENT": "案例六当前评估",
  "EXEC-CASE-06-HIST": "案例六历史评估",
  "ASSESS-CASE-06-HIST": "案例六历史评估",
  "EXEC-CASE-06": "案例六当前评估",
};

export const ruleLabels: Record<string, string> = {
  "MNP-ELIG-001": "规则一：实名信息一致性",
  "MNP-ELIG-002": "规则二：号码状态正常",
  "MNP-ELIG-003": "规则三：费用结清",
  "MNP-ELIG-004": "规则四：合约限制检查",
  "MNP-ELIG-005": "规则五：携转间隔检查",
  "MNP-ELIG-001@1.0": "规则一：实名信息一致性（版本 1.0）",
  "MNP-ELIG-002@1.0": "规则二：号码状态正常（版本 1.0）",
  "MNP-ELIG-003@1.0": "规则三：费用结清（版本 1.0）",
  "MNP-ELIG-004@1.0": "规则四：合约限制检查（版本 1.0）",
  "MNP-ELIG-005@1.0": "规则五：携转间隔检查（版本 1.0）",
  "MNP-ELIG-005@1.1": "规则五：携转间隔检查（版本 1.1）",
};

export const ontologyClassLabels: Record<string, string> = {
  EligibilityAssessment: "资格评估",
  Assessment: "资格评估",
  EvidenceRecord: "证据记录",
  Evidence: "证据记录",
  BlockingReason: "阻塞原因",
  EligibilityRule: "资格规则",
  Rule: "资格规则",
  RuleVersion: "规则版本",
  RegulatoryClause: "监管条款",
  RemediationAction: "处理动作",
  MNPCase: "携转案件",
  Case: "携转案件",
  Subscriber: "订户",
  PhoneNumber: "电话号码",
  Account: "账户",
  TelecomAccount: "账户",
  ServiceContract: "服务合约",
  AuthorizationCode: "授权码",
  PortingRequest: "携转申请",
  Decision: "资格结论",
  EligibilityDecision: "资格结论",
  EligibilityStatus: "资格状态",
  IdentityDocument: "身份证件",
  Invoice: "账单",
  ProcessStep: "流程步骤",
  BlockingDecision: "不可携转结论",
  ConditionalDecision: "有条件结论",
  EligibleDecision: "可携转结论",
  ManualReviewDecision: "人工复核结论",
  AssessmentDependency: "评估依赖关系",
  InformationSystem: "信息系统",
  MappingRecord: "映射记录",
  RegulatoryDocument: "监管文件",
  ServiceSubscription: "业务订阅",
  SystemObservation: "系统观测",
  TelecomService: "电信业务",
};

export const traceEvidenceLabels: Record<string, string> = {
  CONTRACT_STATUS: "合约状态证据",
  BILLING_BALANCE: "计费余额证据",
  IDENTITY_MATCH: "实名一致性证据",
  NUMBER_STATUS: "号码状态证据",
  PORTING_HISTORY: "携转历史证据",
};

export const traceNodeTypeLabels: Record<string, string> = {
  EligibilityAssessment: "资格评估",
  EvidenceRecord: "证据",
  BlockingReason: "阻塞原因",
  EligibilityRule: "资格规则",
  RuleVersion: "规则版本",
  RegulatoryClause: "监管条款",
  RemediationAction: "处理动作",
  MNPCase: "案例",
  BlockingDecision: "资格结论",
  AssessmentDependency: "评估依赖",
  RegulatoryDocument: "监管文件",
};

export const ontologyTypeLabels: Record<string, string> = {
  Class: "类",
  ObjectProperty: "对象属性",
  DatatypeProperty: "数据属性",
  Individual: "实例",
  NodeShape: "节点约束",
  PropertyShape: "属性约束",
};

export const ontologyRelationLabels: Record<string, string> = {
  subClassOf: "属于上位类",
  hasEligibilityAssessment: "包含资格评估",
  hasAssessment: "包含资格评估",
  usesEvidence: "使用证据",
  evaluatedByRule: "依据规则评估",
  evaluatedBy: "依据规则评估",
  triggeredBy: "依据规则评估",
  producesDecision: "产生资格结论",
  hasDecision: "产生资格结论",
  producesBlockingReason: "产生阻塞原因",
  hasBlockingReason: "产生阻塞原因",
  recommendsAction: "建议处理动作",
  hasRemediation: "建议处理动作",
  operationalizesClause: "落实监管条款",
  citesClause: "引用监管条款",
  hasVersion: "具有版本",
  hasSubscriber: "关联订户",
  hasPhoneNumber: "关联号码",
  hasAccount: "关联账户",
  hasContract: "关联合约",
  initiates: "发起携转申请",
  requiresAuthCode: "需要授权码",
  references: "引用",
  hasInvoice: "包含账单",
  hasEligibilityStatus: "包含资格状态",
  partOfDocument: "属于监管文件",
  dependsOnEvidence: "依赖证据",
  dependsOnRuleVersion: "依赖规则版本",
  supportedByEvidence: "由证据支持",
  triggeredByRule: "由规则触发",
  triggeredByRuleVersion: "由规则版本触发",
  aboutCase: "关于案件",
  affectsAssessment: "影响评估",
  billedThrough: "通过账户计费",
  concernsNumber: "涉及号码",
  coversService: "涵盖业务",
  currentProcessStep: "当前流程步骤",
  dependsOn: "依赖",
  evaluatedAtTime: "在指定时间评估",
  evidenceForCase: "作为案件证据",
  governedByContract: "受合约约束",
  hasAuthorizationCode: "具有授权码",
  hasBill: "包含账单",
  hasCaseEvidence: "包含案件证据",
  hasCaseStatus: "具有案件状态",
  hasCharge: "包含费用项",
  hasCommitmentPeriod: "具有承诺期",
  hasEvidenceValidity: "具有证据有效性",
  hasPayment: "包含缴费",
  hasPaymentArrangementRecord: "具有缴费安排",
  hasProcessEvent: "具有流程事件",
  hasProcessStep: "具有流程步骤",
  hasRuleVersion: "具有规则版本",
  hasSourceSystem: "来自信息系统",
  hasSubscription: "具有业务订阅",
  hasTerminationAgreement: "具有解除协议",
  markedForReassessment: "标记为需要重评",
  nextProcessStep: "下一流程步骤",
  observedAtTime: "在指定时间观测",
  observesAccount: "观测账户",
  ownsPhoneNumber: "持有号码",
  recordedAtTime: "在指定时间记录",
  relatedAccount: "关联账户",
  requestedBy: "由订户申请",
  settlesAccount: "结清账户",
  subscribesToService: "订阅业务",
  supersedesRuleVersion: "取代规则版本",
  usesRuleVersion: "使用规则版本",
  assertsOwnership: "主张号码归属",
  hasIdentityDocument: "持有身份证件",
  hasRealNameRegistration: "具有实名登记",
  ownershipHolder: "归属主体",
  verifiedBy: "由核验记录验证",
};

export const moduleLabels: Record<string, string> = {
  Core: "核心",
  CORE: "核心",
  Identity: "身份",
  IDENTITY: "身份",
  AccountBilling: "账户计费",
  ACCOUNT_BILLING: "账户计费",
  Contract: "合约",
  SERVICE_CONTRACT: "合约",
  MNPProcess: "携转流程",
  PROCESS: "携转流程",
  Eligibility: "资格",
  COMPLIANCE: "资格",
  Evidence: "证据",
  EVIDENCE_TIME: "证据",
  CODE_LIST: "受控码表",
  ALIGNMENTS: "外部对齐",
  Rules: "规则",
  Regulatory: "监管",
};

export const contractStatusLabels: Record<string, string> = {
  ACTIVE: "有效",
  EXPIRED: "已到期",
  TERMINATED: "已解除",
  PENDING: "待生效",
  CLOSED: "已关闭",
  SIGNED_PENDING_EFFECTIVE: "已签署但尚未生效",
};

export const numberStatusLabels: Record<string, string> = {
  ACTIVE: "正常",
  NORMAL: "正常",
  SUSPENDED: "已停用",
  CANCELLED: "已注销",
  CLOSED: "已关闭",
};

export const authCodeStatusLabels: Record<string, string> = {
  EXPIRED: "已过期",
  VALID: "已签发",
  MISSING: "缺失",
  ISSUED: "已签发",
  USED: "已使用",
  REVOKED: "已撤销",
};

export const terminationStatusLabels: Record<string, string> = {
  SIGNED_PENDING_EFFECTIVE: "已签署但尚未生效",
};

export const serviceStatusLabels: Record<string, string> = {
  ONLINE: "运行正常",
  DEGRADED: "性能降级",
  OFFLINE: "已离线",
};

export const ruleLifecycleLabels: Record<string, string> = {
  ACTIVE: "当前有效",
  EXPIRED: "历史版本",
  CURRENT: "当前有效",
  HISTORICAL: "历史版本",
};

export const requestTypeLabels: Record<string, string> = {
  PORT_OUT: "携出",
  PORT_IN: "携入",
};

export const priorityLabels: Record<string, string> = {
  NORMAL: "普通",
  URGENT: "紧急",
  BATCH: "批量",
};

export const currencyLabels: Record<string, string> = {
  CNY: "人民币",
};

export const identityTypeLabels: Record<string, string> = {
  ID_CARD: "居民身份证",
  PASSPORT: "护照",
  RESIDENCE: "居住证",
};

export const ui = {
  systemName: "携号转网资格判断本体系统",
  backendOnline: "运行正常",
  envDemo: "演示环境",
  apiVersion: "第一版",
  schemaVersion: "第一版",
  prototypeFooter: "阶段性研究原型",
  runDemo: "运行示例",
  navOverview: "系统总览",
  navNewAssessment: "新建评估",
  navCaseHistory: "案件与历史",
  navOntology: "本体浏览器",
  navCompetency: "能力问题",
  navRules: "规则与版本",
  navWhatIf: "情景推演实验",
  navSystemStatus: "系统状态",
  decision: "资格结论",
  processStatus: "流程状态",
  blockingReason: "阻塞原因",
  supportingEvidence: "支持证据",
  triggeredRule: "触发规则 / 版本",
  remediationAction: "处理动作",
  regulatoryClause: "监管条款",
  assessmentTime: "评估时间",
  executionCount: "执行次数",
  publicationStatus: "发布状态",
  caseName: "案例名称",
  latestDecision: "最新结论",
  actions: "操作",
  viewDetail: "查看详情",
  loadExample: "加载示例",
  submitAssessment: "提交评估",
  canAdvance: "可进入下一步",
  cannotAdvance: "不能继续",
  empty: "暂无数据",
  loading: "加载中…",
  searchOntology: "搜索本体类…",
  baseline: "基准方案",
  scenario: "推演方案",
  historicalVersion: "历史规则版本",
  currentVersion: "当前规则版本",
  eligibilityVsProcessNote: "资格结论与流程状态是分开的。",
  formEntry: "表单录入",
  technicalDebug: "技术调试",
  technicalDebugHint: "此功能仅供开发调试，不属于正式演示界面。",
  unknownStatus: "状态未识别",
  unknownRule: "规则名称未识别",
  unknownEvidence: "证据类型未识别",
  unknownOntologyClass: "本体概念未识别",
  unknownOntologyRelation: "本体关系未识别",
  unknownDataSource: "数据来源未识别",
  unknownClause: "监管条款未识别",
  unknownAction: "处理动作未识别",
  unknownReason: "阻塞原因未识别",
  unknownCase: "案例名称未识别",
  unknownModule: "模块未识别",
  case06HistoricalAssessment: "案例六历史评估",
  case06CurrentAssessment: "案例六当前评估",
};

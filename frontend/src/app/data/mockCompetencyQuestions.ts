import { caseLabels, t } from "../i18n/zh-CN";

export interface CompetencyQuestion {
  id: string;
  titleZh: string;
  questionZh: string;
  usage: string;
  expected: string;
  requiredInputs: string[];
  exampleCase: string;
  exampleCaseLabel: string;
}

const titles: Record<string, string> = {
  "CQ-01": "当前是否可携转",
  "CQ-02": "阻塞原因",
  "CQ-03": "阻塞证据",
  "CQ-04": "证据来源和时间",
  "CQ-05": "使用的规则版本",
  "CQ-06": "监管条款",
  "CQ-07": "解除动作",
  "CQ-08": "当前流程步骤",
  "CQ-09": "不能进入下一步的原因",
  "CQ-10": "授权码是否有效",
  "CQ-11": "关联业务",
  "CQ-12": "影响携转的合约",
  "CQ-13": "欠费证据是否过期",
  "CQ-14": "多阻塞如何分别处理",
  "CQ-15": "规则更新影响哪些评估",
};

const usageMap: Record<string, string> = {
  "CQ-01": "返回案件当前资格结论",
  "CQ-02": "列出独立阻塞原因代码",
  "CQ-03": "查询支持各阻塞原因的证据",
  "CQ-04": "查询证据来源与生成、有效时间",
  "CQ-05": "查询评估时点选用的规则版本",
  "CQ-06": "查询阻塞原因引用的监管条款",
  "CQ-07": "查询建议的解除或处理动作",
  "CQ-08": "查询当前携转流程步骤",
  "CQ-09": "查询流程无法前进的原因",
  "CQ-10": "查询授权码状态与有效期",
  "CQ-11": "查询案件关联的电信业务",
  "CQ-12": "查询影响携转的合约状态",
  "CQ-13": "检查计费证据是否过期",
  "CQ-14": "分别给出各阻塞原因的处理动作",
  "CQ-15": "查询规则更新影响的历史评估",
};

const expectedMap: Record<string, string> = {
  "CQ-01": "资格结论（可携转 / 不可携转 / 需要人工复核）",
  "CQ-02": "阻塞原因列表",
  "CQ-03": "证据标识、证据状态",
  "CQ-04": "数据来源、生成时间、有效期",
  "CQ-05": "规则标识与版本号",
  "CQ-06": "监管条款标识",
  "CQ-07": "处理动作代码",
  "CQ-08": "流程步骤代码",
  "CQ-09": "流程阻塞事件类型",
  "CQ-10": "授权码状态与有效截止时间",
  "CQ-11": "关联业务列表",
  "CQ-12": "合约状态与到期时间",
  "CQ-13": "计费证据有效截止时间",
  "CQ-14": "各阻塞原因及其处理动作",
  "CQ-15": "需重评的评估标识列表",
};

const examples: Record<string, string> = {
  "CQ-01": "CASE-01",
  "CQ-02": "CASE-04",
  "CQ-03": "CASE-04",
  "CQ-04": "CASE-03",
  "CQ-05": "CASE-03",
  "CQ-06": "CASE-03",
  "CQ-07": "CASE-03",
  "CQ-08": "CASE-07",
  "CQ-09": "CASE-07",
  "CQ-10": "CASE-07",
  "CQ-11": "CASE-01",
  "CQ-12": "CASE-03",
  "CQ-13": "CASE-02",
  "CQ-14": "CASE-04",
  "CQ-15": "CASE-06",
};

const inputs: Record<string, string[]> = {
  "CQ-01": ["case_id"],
  "CQ-02": ["case_id"],
  "CQ-03": ["case_id"],
  "CQ-04": ["case_id"],
  "CQ-05": ["case_id"],
  "CQ-06": ["case_id"],
  "CQ-07": ["case_id"],
  "CQ-08": ["case_id"],
  "CQ-09": ["case_id"],
  "CQ-10": ["case_id"],
  "CQ-11": ["case_id"],
  "CQ-12": ["case_id"],
  "CQ-13": ["case_id"],
  "CQ-14": ["case_id"],
  "CQ-15": ["case_id"],
};

export const mockCompetencyQuestions: CompetencyQuestion[] = Object.keys(titles).map(
  (id) => {
    const exampleCase = examples[id];
    return {
      id,
      titleZh: titles[id],
      questionZh: titles[id],
      usage: usageMap[id],
      expected: expectedMap[id],
      requiredInputs: inputs[id],
      exampleCase,
      exampleCaseLabel: t(caseLabels, exampleCase, exampleCase),
    };
  },
);

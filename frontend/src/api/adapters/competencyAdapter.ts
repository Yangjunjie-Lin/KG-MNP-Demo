import { array, record, text } from "./guards";

export interface CompetencyQuestionView {
  id: string;
  titleZh: string;
  requiredInputs: string[];
  returnFields: string[];
  exampleCase: string;
}

export interface CompetencyResultView {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  status: string;
}

export function adaptCompetencyQuestions(dto: unknown): CompetencyQuestionView[] {
  return array(record(dto).items).map((raw) => {
    const item = record(raw);
    return {
      id: text(item.id),
      titleZh: text(item.title_zh, "能力问题"),
      requiredInputs: array(item.required_inputs).map((value) => text(value)),
      returnFields: array(item.return_fields).map((value) => text(value)),
      exampleCase: text(item.example_case, "CASE-01"),
    };
  });
}

export function adaptCompetencyResult(dto: unknown): CompetencyResultView {
  const result = record(dto);
  return {
    columns: array(result.columns).map((value) => text(value)),
    rows: array(result.rows).map(record),
    status: text(result.status),
  };
}

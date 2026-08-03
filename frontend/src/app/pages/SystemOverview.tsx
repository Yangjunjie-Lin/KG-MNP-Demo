import { useEffect, useState } from "react";
import {
  ArrowRight,
  ChevronRight,
  Clock,
  FileText,
  Database,
  Shield,
  Cpu,
  Zap,
  BarChart3,
  FileCheck,
  GitBranch,
} from "lucide-react";
import { SectionHeader } from "../components/SectionHeader";
import { MetricCard } from "../components/MetricCard";
import { DecisionBadge } from "../components/StatusBadges";
import { cn } from "../utils/cn";
import {
  blockingReasonLabels,
  caseLabels,
  t,
} from "../i18n/zh-CN";
import { listCases } from "../services/caseService";
import { getPipelineSteps } from "../services/assessmentService";
import { getModules, getNodes, getEdges } from "../services/ontologyService";
import { listRules } from "../services/ruleService";
import { getCompetencyQuestions } from "../services/assessmentService";
import type { CaseSummary, PipelineStep } from "../types/assessment";

const PIPELINE_ICONS: Record<string, typeof FileText> = {
  "json-schema": FileText,
  "rdf-builder": Database,
  "input-shacl": Shield,
  "owl-rl": Cpu,
  "rule-engine": Zap,
  assessment: BarChart3,
  "assessment-shacl": FileCheck,
  "sparql-trace": GitBranch,
};

function formatTime(iso: string): string {
  return iso.replace("T", " ").replace("Z", "").slice(0, 16);
}

export function SystemOverview({
  onCaseClick,
}: {
  onCaseClick: (caseId: string) => void;
}) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [pipeline, setPipeline] = useState<PipelineStep[]>([]);
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [metrics, setMetrics] = useState({
    modules: 0,
    classes: 0,
    props: 0,
    shapes: 31,
    rules: 0,
    cqs: 0,
  });

  useEffect(() => {
    void (async () => {
      const [caseList, steps, modules, nodes, edges, rules, cqs] =
        await Promise.all([
          listCases(),
          getPipelineSteps(),
          getModules(),
          getNodes(),
          getEdges(),
          listRules(),
          getCompetencyQuestions(),
        ]);
      setCases(caseList);
      setPipeline(steps);
      setMetrics({
        modules: modules.length,
        classes: nodes.length,
        props: edges.length,
        shapes: 31,
        rules: rules.length,
        cqs: cqs.length,
      });
    })();
  }, []);

  return (
    <div className="p-6 space-y-6 max-w-full min-w-0 overflow-x-hidden">
      <div>
        <SectionHeader title="本体统计" />
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
          <MetricCard label="本体模块" value={metrics.modules} color="text-blue-700" />
          <MetricCard label="本体类" value={metrics.classes} color="text-violet-700" />
          <MetricCard label="对象属性" value={metrics.props} color="text-indigo-700" />
          <MetricCard label="约束形状" value={metrics.shapes} color="text-cyan-700" />
          <MetricCard label="规则数量" value={metrics.rules} color="text-emerald-700" />
          <MetricCard label="能力问题" value={metrics.cqs} color="text-amber-700" />
        </div>
      </div>

      <div>
        <SectionHeader title="系统处理流程" sub="点击步骤查看详情" />
        <div className="bg-white border border-slate-200 rounded-lg p-5 min-w-0">
          <div className="flex items-start gap-1 overflow-x-auto pb-2">
            {pipeline.map((step, i) => {
              const Icon = PIPELINE_ICONS[step.id] ?? FileText;
              const isActive = activeStep === step.id;
              return (
                <div key={step.id} className="flex items-center gap-1 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => setActiveStep(isActive ? null : step.id)}
                    className={cn(
                      "flex flex-col items-center gap-2 px-3 py-3 rounded-lg border transition-all min-w-[90px]",
                      isActive
                        ? "border-blue-400 bg-blue-50 shadow-sm"
                        : "border-slate-200 hover:border-blue-300 hover:bg-slate-50",
                    )}
                  >
                    <div
                      className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center",
                        isActive ? "bg-blue-600" : "bg-slate-100",
                      )}
                    >
                      <Icon
                        size={16}
                        className={isActive ? "text-white" : "text-slate-600"}
                      />
                    </div>
                    <span
                      className={cn(
                        "text-[11px] font-medium text-center leading-tight",
                        isActive ? "text-blue-700" : "text-slate-600",
                      )}
                    >
                      {step.label}
                    </span>
                  </button>
                  {i < pipeline.length - 1 && (
                    <ArrowRight size={14} className="text-slate-300 flex-shrink-0" />
                  )}
                </div>
              );
            })}
          </div>
          {activeStep &&
            (() => {
              const step = pipeline.find((s) => s.id === activeStep);
              if (!step) return null;
              return (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                    <div>
                      <div className="text-xs text-slate-400 font-medium mb-1">功能</div>
                      <div className="text-slate-700">{step.description}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400 font-medium mb-1">输入</div>
                      <div className="text-slate-700">{step.input}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-400 font-medium mb-1">输出</div>
                      <div className="text-slate-700">{step.output}</div>
                    </div>
                    <div>
                      <div className="text-xs text-red-400 font-medium mb-1">失败时</div>
                      <div className="text-slate-700">{step.failure}</div>
                    </div>
                  </div>
                </div>
              );
            })()}
        </div>
      </div>

      <div>
        <SectionHeader title="示例案件" sub="九个预置案例，点击查看评估详情" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {cases.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onCaseClick(c.id)}
              className="bg-white border border-slate-200 rounded-lg p-4 text-left hover:border-blue-300 hover:shadow-sm transition-all group min-w-0"
            >
              <div className="flex items-start justify-between mb-2 gap-2">
                <span className="text-xs text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded">
                  {t(caseLabels, c.id, c.id)}
                </span>
                <DecisionBadge decision={c.decision} />
              </div>
              <div className="font-medium text-slate-800 text-sm mb-1.5">{c.title}</div>
              <div className="text-xs text-slate-500 mb-3 leading-relaxed">{c.scenario}</div>
              {c.blockingReasons.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {c.blockingReasons.map((r) => (
                    <span
                      key={r}
                      className="text-[10px] bg-red-50 text-red-600 px-1.5 py-0.5 rounded border border-red-100"
                    >
                      {t(blockingReasonLabels, r, r)}
                    </span>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-auto">
                <Clock size={10} />
                <span>{formatTime(c.assessmentTime)}</span>
                <span className="ml-auto flex items-center gap-1 text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">
                  查看详情 <ChevronRight size={10} />
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

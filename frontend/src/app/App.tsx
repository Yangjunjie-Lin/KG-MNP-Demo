import { Navigate, Route, Routes } from "react-router";
import { AppLayout } from "./layout/AppLayout";
import { AssessmentResult } from "./pages/AssessmentResult";
import { CaseHistory } from "./pages/CaseHistory";
import { CompetencyQuestions } from "./pages/CompetencyQuestions";
import { NewAssessment } from "./pages/NewAssessment";
import { OntologyBrowser } from "./pages/OntologyBrowser";
import { RulesAndVersions } from "./pages/RulesAndVersions";
import { SystemOverview } from "./pages/SystemOverview";
import { SystemStatus } from "./pages/SystemStatus";
import { WhatIfExperiment } from "./pages/WhatIfExperiment";

function NotFound() { return <div className="m-6 rounded border border-slate-200 bg-white p-10 text-center"><h1 className="mb-2 text-lg font-semibold text-slate-800">未找到相关页面</h1><p className="text-sm text-slate-500">请检查地址或返回系统总览。</p></div>; }

export default function App() {
  return <AppLayout><Routes>
    <Route path="/" element={<Navigate to="/overview" replace />} />
    <Route path="/overview" element={<SystemOverview />} />
    <Route path="/assessments/new" element={<NewAssessment />} />
    <Route path="/cases" element={<CaseHistory />} />
    <Route path="/assessments/:executionId" element={<AssessmentResult />} />
    <Route path="/ontology" element={<OntologyBrowser />} />
    <Route path="/competency-questions" element={<CompetencyQuestions />} />
    <Route path="/rules" element={<RulesAndVersions />} />
    <Route path="/what-if" element={<WhatIfExperiment />} />
    <Route path="/system" element={<SystemStatus />} />
    <Route path="*" element={<NotFound />} />
  </Routes></AppLayout>;
}

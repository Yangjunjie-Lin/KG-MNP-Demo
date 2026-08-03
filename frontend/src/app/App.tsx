import { useState } from "react";
import { AppLayout } from "./layout/AppLayout";
import { SystemOverview } from "./pages/SystemOverview";
import { NewAssessment } from "./pages/NewAssessment";
import { CaseHistory } from "./pages/CaseHistory";
import { AssessmentResult } from "./pages/AssessmentResult";
import { OntologyBrowser } from "./pages/OntologyBrowser";
import { CompetencyQuestions } from "./pages/CompetencyQuestions";
import { RulesAndVersions } from "./pages/RulesAndVersions";
import { WhatIfExperiment } from "./pages/WhatIfExperiment";
import { SystemStatus } from "./pages/SystemStatus";
import type { PageId } from "./types/common";

export default function App() {
  const [page, setPage] = useState<PageId>("overview");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const openCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setPage("result");
  };

  const handleBack = () => {
    setPage("case-history");
    setSelectedCaseId(null);
  };

  const handleRunDemo = () => {
    openCase("CASE-03");
  };

  const handleNavigate = (p: PageId) => {
    setPage(p);
    if (p !== "result") setSelectedCaseId(null);
  };

  return (
    <AppLayout current={page} onNavigate={handleNavigate} onRunDemo={handleRunDemo}>
      {page === "overview" && (
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
          <SystemOverview onCaseClick={openCase} />
        </div>
      )}
      {page === "result" && selectedCaseId && (
        <div className="flex-1 overflow-hidden flex flex-col min-w-0">
          <AssessmentResult caseId={selectedCaseId} onBack={handleBack} />
        </div>
      )}
      {page === "new-assessment" && (
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
          <NewAssessment />
        </div>
      )}
      {page === "case-history" && (
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
          <CaseHistory onCaseClick={openCase} />
        </div>
      )}
      {page === "ontology" && (
        <div className="flex-1 overflow-hidden flex min-w-0">
          <OntologyBrowser />
        </div>
      )}
      {page === "competency" && (
        <div className="flex-1 overflow-hidden flex min-w-0">
          <CompetencyQuestions />
        </div>
      )}
      {page === "rules" && (
        <div className="flex-1 overflow-hidden flex min-w-0">
          <RulesAndVersions />
        </div>
      )}
      {page === "whatif" && (
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
          <WhatIfExperiment />
        </div>
      )}
      {page === "system-status" && (
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
          <SystemStatus />
        </div>
      )}
    </AppLayout>
  );
}

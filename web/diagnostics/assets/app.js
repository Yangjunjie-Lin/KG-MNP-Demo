(function () {
  "use strict";
  var statusNode = document.getElementById("status");
  var identity = document.getElementById("identity");
  var summaryGrid = document.getElementById("summary-grid");
  var issueList = document.getElementById("issue-list");
  var detailCard = document.getElementById("detail-card");
  var detailEmpty = document.getElementById("detail-empty");

  function text(value) { return value === null || value === undefined ? "" : String(value); }
  function add(parent, tag, value, className) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text(value);
    parent.appendChild(node);
    return node;
  }
  function get(path) { return fetch(path, { credentials: "same-origin" }).then(function (r) { if (!r.ok) throw new Error("diagnostics unavailable"); return r.json(); }); }
  function showDetail(issue) {
    detailEmpty.hidden = true; detailCard.hidden = false; detailCard.replaceChildren();
    add(detailCard, "h3", issue.classification + " — " + issue.severity);
    add(detailCard, "p", issue.scope === "HISTORICAL_REVIEW_CONTEXT" ? "HISTORICAL REVIEW CONTEXT" : "CURRENT DIAGNOSTIC", "badge");
    add(detailCard, "p", issue.explanation);
    var trace = { focus_node: issue.focus_node, path: issue.path, observed_values: issue.observed_values, authority_basis: issue.authority_basis, source_assertions: issue.source_assertions, candidate_refs: issue.candidate_refs, review_decision_refs: issue.review_decision_refs, evidence_refs: issue.evidence_refs, source_refs: issue.source_refs, publication_id: issue.publication_id, diagnostic_id: issue.diagnostic_id };
    add(detailCard, "pre", JSON.stringify(trace, null, 2), "trace");
  }
  Promise.all([get("/diagnostics/api/status"), get("/diagnostics/api/summary"), get("/diagnostics/api/issues?limit=1000")]).then(function (values) {
    var state = values[0], report = values[1], issues = values[2].issues;
    statusNode.textContent = state.status + " · read-only · derived observation layer";
    [["Publication", state.publication_id], ["Package", state.package_id], ["Repository semantic hash", state.repository_semantic_hash]].forEach(function (pair) { add(identity, "dt", pair[0]); add(identity, "dd", pair[1]); });
    Object.keys(report.summary).forEach(function (key) { if (typeof report.summary[key] === "number") { var card = add(summaryGrid, "div", null, "card"); add(card, "strong", report.summary[key]); add(card, "span", key.replace(/_/g, " ")); } });
    issues.forEach(function (issue) { var row = add(issueList, "button", null, "issue" + (issue.scope === "HISTORICAL_REVIEW_CONTEXT" ? " history" : "")); row.type = "button"; add(row, "h3", issue.classification); add(row, "span", issue.scope === "HISTORICAL_REVIEW_CONTEXT" ? "HISTORICAL REVIEW CONTEXT" : "CURRENT DIAGNOSTIC", "badge"); add(row, "p", issue.focus_node + (issue.path ? " · " + issue.path : "")); row.addEventListener("click", function () { showDetail(issue); }); });
  }).catch(function (error) { statusNode.textContent = text(error.message); });
}());

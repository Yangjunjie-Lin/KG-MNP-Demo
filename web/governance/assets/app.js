"use strict";

const state = { csrf: "", revision: 0, head: "GENESIS", issues: [], workspace: null };
const byId = (id) => document.getElementById(id);
const text = (tag, value, className) => {
  const node = document.createElement(tag);
  node.textContent = String(value);
  if (className) node.className = className;
  return node;
};
const show = (name) => {
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === name));
};
document.querySelectorAll("nav button").forEach((button) => button.addEventListener("click", () => show(button.dataset.view)));

async function json(url, options = {}) {
  const response = await fetch(url, { credentials: "omit", cache: "no-store", ...options });
  const value = await response.json();
  if (!response.ok) throw new Error(`${value.code || "REQUEST_FAILED"}: ${value.detail || response.status}`);
  return value;
}

function payload(type, proposedValue) {
  const empty = { rdf_term: null, evidence_refs: [], source_refs: [], candidate_refs: [], constraint_refs: [], review_reopen_reason: null };
  if (type === "PROPOSE_VALUE_CANDIDATE") empty.rdf_term = { term_type: "LITERAL", iri: null, lexical_form: proposedValue, datatype_iri: "http://www.w3.org/2001/XMLSchema#string", language: null };
  if (type === "PROPOSE_EVIDENCE_ATTACHMENT") empty.evidence_refs = [proposedValue];
  if (type === "PROPOSE_SOURCE_ATTACHMENT") empty.source_refs = [proposedValue];
  if (type === "REQUEST_REVIEW_REOPEN") empty.review_reopen_reason = proposedValue;
  if (type === "PROPOSE_CONSTRAINT_REVIEW") empty.constraint_refs = [proposedValue];
  return empty;
}

function render() {
  const dl = byId("verification-data"); dl.replaceChildren();
  [["Status", "GOVERNANCE_READY"], ["Workspace revision", state.revision], ["Head event hash", state.head], ["Authority", "Non-authoritative future amendment governance only"]].forEach(([key, value]) => { dl.append(text("dt", key), text("dd", value)); });
  const diagnosticList = byId("diagnostic-list"); diagnosticList.replaceChildren();
  const diagnosticSelect = byId("proposal-diagnostic"); diagnosticSelect.replaceChildren();
  state.issues.forEach((issue) => {
    const card = text("button", `${issue.classification} · ${issue.diagnostic_id}`, "card");
    card.type = "button";
    card.addEventListener("click", () => { byId("diagnostic-detail").textContent = JSON.stringify(issue, null, 2); show("detail"); });
    diagnosticList.append(card);
    const option = text("option", `${issue.classification} · ${issue.diagnostic_id.slice(-12)}`); option.value = issue.diagnostic_id; diagnosticSelect.append(option);
  });
  const proposals = state.workspace ? state.workspace.proposals : [];
  const proposalList = byId("proposal-list"); proposalList.replaceChildren();
  const reviewSelect = byId("review-proposal"); reviewSelect.replaceChildren();
  proposals.forEach((proposal) => {
    proposalList.append(text("article", `${proposal.status} · ${proposal.proposal_type} · ${proposal.proposal_id}`, "card"));
    if (proposal.status === "SUBMITTED") { const option = text("option", proposal.proposal_id); option.value = proposal.proposal_id; reviewSelect.append(option); }
  });
  const amendments = state.workspace ? state.workspace.approved_amendment_requests : [];
  const amendmentList = byId("amendment-list"); amendmentList.replaceChildren();
  amendments.forEach((item) => amendmentList.append(text("article", `Approved for Future Amendment · ${item.amendment_request_id}`, "card")));
  const events = byId("event-list"); events.replaceChildren();
  if (state.workspace) state.workspace.events.forEach((event) => events.append(text("li", `${event.sequence} · ${event.event_type} · ${event.event_id}`)));
}

async function refresh() {
  const bootstrap = await json("/governance/api/bootstrap");
  state.csrf = bootstrap.csrf_token; state.revision = bootstrap.workspace_revision; state.head = bootstrap.head_event_hash;
  state.issues = (await json("/governance/api/diagnostics")).issues;
  state.workspace = await json("/governance/api/workspace");
  render();
}

function post(url, body) { return json(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrf }, body: JSON.stringify(body) }); }

byId("proposal-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const target = state.issues.find((item) => item.diagnostic_id === byId("proposal-diagnostic").value);
    const type = byId("proposal-type").value;
    const proposal = await post("/governance/api/proposals", { expected_workspace_revision: state.revision, expected_head_hash: state.head, target_diagnostic_id: target.diagnostic_id, target_diagnostic_basis_hash: target.diagnostic_basis_hash, proposal_type: type, proposed_payload: payload(type, byId("proposed-value").value), rationale: byId("rationale").value, created_by_label: byId("creator-label").value, proposal_revision: 1 });
    await refresh();
    const digest = proposal.proposal_id.split(":").pop();
    await post(`/governance/api/proposals/${encodeURIComponent(digest)}/submit`, { expected_workspace_revision: state.revision, expected_head_hash: state.head });
    byId("message").textContent = "Proposal submitted. Awaiting Human Review."; await refresh(); show("review");
  } catch (error) { byId("message").textContent = error.message; }
});

byId("review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const digest = byId("review-proposal").value.split(":").pop();
    await post(`/governance/api/proposals/${encodeURIComponent(digest)}/review`, { expected_workspace_revision: state.revision, expected_head_hash: state.head, decision: byId("review-decision").value, review_note: byId("review-note").value, reviewed_by_label: byId("reviewer-label").value, explicit_human_action: byId("explicit-action").checked });
    byId("message").textContent = "Explicit human review recorded."; await refresh();
  } catch (error) { byId("message").textContent = error.message; }
});

refresh().catch((error) => { byId("message").textContent = error.message; });

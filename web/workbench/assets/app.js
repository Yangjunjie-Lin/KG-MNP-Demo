const DEFAULTS = Object.freeze({
  entity: "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/2993a1403cabddd34da97cacad8c5aa55103903ab9d3a0d831bd9f989f2fc029",
  predicate: "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#subscriptionStatusCode",
  candidate: "urn:kg-mnp:candidate:63de7ebf8435aedbba092b5cb7d83450eacb351ffbc96e9833bdcacc6c14a6e2",
  source: "urn:kg-mnp:source-record:703f296ce26afb5543514b90584f50bc062ca9e64436e3e5e49f9921148eab0d"
});

const root = document.querySelector("#view-root");
const chip = document.querySelector("#verification-chip");
const blocking = document.querySelector("#blocking-error");
const blockingMessage = document.querySelector("#blocking-error-message");

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined && text !== null) item.textContent = String(text);
  return item;
}

function append(parent, ...children) {
  for (const child of children) {
    if (child) parent.append(child);
  }
  return parent;
}

async function jsonRequest(path) {
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin) throw new Error("WORKBENCH_NOT_READY");
  const response = await fetch(url, {
    method: "GET",
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    headers: { Accept: "application/json" }
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error?.code || "WORKBENCH_NOT_READY");
  }
  return payload;
}

function setCurrentNavigation() {
  for (const link of document.querySelectorAll(".primary-nav a")) {
    const path = new URL(link.href).pathname;
    if (path === window.location.pathname) link.setAttribute("aria-current", "page");
  }
}

function heading(kicker, title, description) {
  const wrapper = node("header", "view-heading");
  const text = node("div");
  append(text, node("p", "eyebrow", kicker), node("h2", "", title), node("p", "", description));
  wrapper.append(text);
  return wrapper;
}

function panel(title, description) {
  const wrapper = node("section", "panel");
  const head = node("header", "panel-heading");
  append(head, node("h3", "", title), node("p", "", description));
  const body = node("div", "panel-body");
  append(wrapper, head, body);
  return { wrapper, body };
}

function statusCard(title, value) {
  const card = node("article", "card");
  append(card, node("h3", "", title), node("div", "value", value));
  return card;
}

function termElement(term) {
  const wrapper = node("div", "term");
  if (!term || !term.term_type) {
    wrapper.append(node("span", "term-detail", "Not present"));
    return wrapper;
  }
  const kind = node("span", `term-kind${term.term_type === "LITERAL" ? " literal" : ""}`, term.term_type);
  const value = term.term_type === "IRI" ? term.iri : term.lexical_form;
  append(wrapper, kind, node("span", "term-value", value));
  if (term.term_type === "LITERAL") {
    append(
      wrapper,
      node("span", "term-detail", `Datatype: ${term.datatype_iri ?? "none"}`),
      node("span", "term-detail", `Language: ${term.language ?? "none"}`)
    );
  }
  return wrapper;
}

function resultMetadata(model) {
  const meta = node("div", "result-meta");
  append(
    meta,
    node("span", "", `Rows: ${model.result_count}`),
    node("span", "", `Query: ${model.query_id}`),
    node("span", "", `Source result hash: ${model.source_result_hash}`),
    node("span", "", model.truncated ? "Result truncated" : "Complete bounded result")
  );
  return meta;
}

function rowsTable(model, captionText = "RDF-faithful result rows") {
  if (!model.rows.length) return node("p", "empty-state", "No asserted result rows.");
  const table = node("table");
  table.append(node("caption", "", captionText));
  const head = node("thead");
  const headRow = node("tr");
  for (const variable of model.variables) headRow.append(node("th", "", variable));
  head.append(headRow);
  const body = node("tbody");
  for (const row of model.rows) {
    const byVariable = new Map(row.bindings.map((binding) => [binding.variable, binding.term]));
    const line = node("tr");
    for (const variable of model.variables) {
      const cell = node("td");
      cell.append(termElement(byVariable.get(variable)));
      line.append(cell);
    }
    body.append(line);
  }
  append(table, head, body);
  return table;
}

function field(form, labelText, name, value, options = {}) {
  const wrapper = node("div", `field ${options.size || ""}`.trim());
  const label = node("label", "", labelText);
  label.htmlFor = `field-${name}`;
  let control;
  if (options.choices) {
    control = node("select");
    for (const choice of options.choices) {
      const item = node("option", "", choice);
      item.value = choice;
      control.append(item);
    }
    control.value = value;
  } else {
    control = node("input");
    control.type = options.type || "text";
    control.value = value;
  }
  control.id = `field-${name}`;
  control.name = name;
  control.required = options.required !== false;
  wrapper.append(label, control);
  form.append(wrapper);
  return control;
}

function formButton(form, text = "Inspect") {
  const actions = node("div", "form-actions");
  const button = node("button", "", text);
  button.type = "submit";
  actions.append(button);
  form.append(actions);
  return button;
}

function loading(container) {
  container.replaceChildren(node("p", "loading", "Loading verified Phase 01 results…"));
}

function renderError(container, error) {
  const message = error instanceof Error ? error.message : "WORKBENCH_NOT_READY";
  container.replaceChildren(node("p", "blocking-error", message));
}

function traceItem(label, value) {
  const item = node("li");
  append(item, node("span", "trace-label", label), node("span", "term-value", value ?? "Not present"));
  return item;
}

function bindingValue(row, variable) {
  const binding = row.bindings.find((item) => item.variable === variable);
  if (!binding) return null;
  return binding.term.term_type === "IRI" ? binding.term.iri : binding.term.lexical_form;
}

function renderTraceRows(model, container) {
  container.replaceChildren(resultMetadata(model));
  if (!model.rows.length) {
    container.append(node("p", "empty-state", "No fact-level trace rows."));
    return;
  }
  for (const row of model.rows) {
    const chain = node("ol", "trace-chain");
    const objectTerm = row.bindings.find((item) => item.variable === "object")?.term;
    const objectValue = objectTerm?.term_type === "IRI" ? objectTerm.iri : objectTerm?.lexical_form;
    append(
      chain,
      traceItem("Fact subject", bindingValue(row, "subject")),
      traceItem("Fact predicate", bindingValue(row, "predicate")),
      traceItem(`Fact object (${objectTerm?.term_type ?? "unknown"})`, objectValue),
      traceItem("Named graph", bindingValue(row, "businessGraph")),
      traceItem("Modeling candidate", bindingValue(row, "candidateId")),
      traceItem("Review decision", `${bindingValue(row, "decisionId") ?? "Not present"} · ${bindingValue(row, "outcome") ?? "No outcome"}`),
      traceItem("Evidence", bindingValue(row, "evidenceRef")),
      traceItem("Source", bindingValue(row, "sourceRef")),
      traceItem("Publication", model.publication_id)
    );
    container.append(chain);
  }
}

function dashboard(status) {
  document.title = "Verification · KG-MNP Evidence Workbench";
  root.replaceChildren(
    heading(
      "Verification / publication status",
      "A verified view, never a new authority",
      "Every view is bound to one Application Phase 01 attestation and one immutable publication identity."
    )
  );
  const cards = node("section", "grid");
  cards.setAttribute("aria-label", "Verification identities");
  append(
    cards,
    statusCard("Foundation", status.foundation_verified ? "Verified · Stage 01–08" : "Not verified"),
    statusCard("Application Phase 01", status.phase01_attestation_status),
    statusCard("Publication ID", status.publication_id),
    statusCard("Publication semantic hash", status.publication_semantic_hash),
    statusCard("Ontology version", status.ontology_version),
    statusCard("Repository semantic hash", status.repository_semantic_hash),
    statusCard("Query registry identity", status.query_registry_hash),
    statusCard("Phase 01 attestation digest", status.phase01_attestation_hash)
  );
  root.append(cards);
}

async function ontologyPage() {
  document.title = "Ontology explorer · KG-MNP Evidence Workbench";
  root.replaceChildren(heading("Ontology explorer", "Classes and properties", "Terms come only from registered Phase 01 ontology queries. Module graphs, labels, definitions, domains, ranges and hierarchy remain RDF-faithful."));
  const classPanel = panel("Classes", "Labels, definitions, superclass and source TBox graph");
  const propertyPanel = panel("Object and datatype properties", "Property kind, domain, range, hierarchy and source TBox graph");
  root.append(classPanel.wrapper, propertyPanel.wrapper);
  loading(classPanel.body);
  loading(propertyPanel.body);
  try {
    const [classes, properties] = await Promise.all([
      jsonRequest("/workbench/api/view/ontology/classes?limit=100&offset=0"),
      jsonRequest("/workbench/api/view/ontology/properties?limit=100&offset=0")
    ]);
    classPanel.body.replaceChildren(resultMetadata(classes), rowsTable(classes, "Ontology classes"));
    propertyPanel.body.replaceChildren(resultMetadata(properties), rowsTable(properties, "Ontology properties"));
  } catch (error) {
    renderError(classPanel.body, error);
    renderError(propertyPanel.body, error);
  }
}

function entityPage() {
  document.title = "Entity explorer · KG-MNP Evidence Workbench";
  root.replaceChildren(heading("Entity explorer", "Inspect asserted entity facts", "Outgoing and incoming relations retain term kind, literal metadata and named graph. Review-only records never enter this facts table."));
  const form = node("form", "query-form");
  const iri = field(form, "Entity IRI", "iri", DEFAULTS.entity);
  formButton(form, "Inspect entity");
  const results = panel("Asserted facts", "Current business graph rows only");
  results.body.append(node("p", "empty-state", "Submit an entity IRI to inspect it."));
  root.append(form, results.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    loading(results.body);
    try {
      const query = new URLSearchParams({ iri: iri.value, limit: "100", offset: "0" });
      const model = await jsonRequest(`/workbench/api/view/entity?${query.toString()}`);
      results.body.replaceChildren(resultMetadata(model), rowsTable(model, "Asserted entity facts"));
    } catch (error) {
      renderError(results.body, error);
    }
  });
}

function factParameters(controls) {
  const values = {
    subject: controls.subject.value,
    predicate: controls.predicate.value,
    object_type: controls.objectType.value,
    object_value: controls.objectValue.value
  };
  if (controls.objectType.value === "LITERAL") {
    if (controls.datatype.value) values.datatype_iri = controls.datatype.value;
    if (controls.language.value) values.language = controls.language.value;
  }
  return new URLSearchParams(values);
}

function factPage() {
  document.title = "Fact inspector · KG-MNP Evidence Workbench";
  root.replaceChildren(heading("Fact inspector", "Exact RDF fact and lineage", "Inspect subject, predicate, object and named graph, then follow the exact fact-level candidate, decision, evidence, source and publication chain."));
  const form = node("form", "query-form");
  const controls = {
    subject: field(form, "Subject IRI", "subject", DEFAULTS.entity),
    predicate: field(form, "Predicate IRI", "predicate", DEFAULTS.predicate),
    objectType: field(form, "Object kind", "object_type", "LITERAL", { choices: ["IRI", "LITERAL"], size: "third" }),
    objectValue: field(form, "Object lexical form or IRI", "object_value", "ACTIVE", { size: "third" }),
    datatype: field(form, "Datatype IRI", "datatype_iri", "http://www.w3.org/2001/XMLSchema#string", { size: "third", required: false }),
    language: field(form, "Language tag", "language", "", { size: "third", required: false })
  };
  formButton(form, "Inspect fact and provenance");
  const fact = panel("Asserted fact", "Exact business fact match and named graph");
  const trace = panel("Fact-level traceability", "Fact → graph → candidate → review → evidence → source → publication");
  fact.body.append(node("p", "empty-state", "Submit an exact RDF fact."));
  trace.body.append(node("p", "empty-state", "Traceability will appear here."));
  root.append(form, fact.wrapper, trace.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    loading(fact.body);
    loading(trace.body);
    const parameters = factParameters(controls);
    try {
      const [factModel, traceModel] = await Promise.all([
        jsonRequest(`/workbench/api/view/fact?${parameters.toString()}`),
        jsonRequest(`/workbench/api/view/fact/provenance?${parameters.toString()}&limit=100&offset=0`)
      ]);
      fact.body.replaceChildren(resultMetadata(factModel), rowsTable(factModel, "Exact asserted fact"));
      renderTraceRows(traceModel, trace.body);
    } catch (error) {
      renderError(fact.body, error);
      renderError(trace.body, error);
    }
  });
}

function tracePage() {
  document.title = "Evidence trace · KG-MNP Evidence Workbench";
  root.replaceChildren(heading("Evidence trace", "Cross-layer registered trace", "Follow a resource through the Phase 01 cross-trace query. The workbench does not infer missing links."));
  const form = node("form", "query-form");
  const resource = field(form, "Resource identifier", "resource_id", DEFAULTS.entity);
  formButton(form, "Load trace");
  const results = panel("Structured trace", "Raw registered query bindings and publication identity");
  results.body.append(node("p", "empty-state", "Submit a resource identifier."));
  root.append(form, results.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    loading(results.body);
    try {
      const query = new URLSearchParams({ resource_id: resource.value, limit: "100", offset: "0" });
      const model = await jsonRequest(`/workbench/api/view/trace?${query.toString()}`);
      results.body.replaceChildren(resultMetadata(model), rowsTable(model, "Cross-trace rows"));
    } catch (error) {
      renderError(results.body, error);
    }
  });
}

function reviewPage() {
  document.title = "Review history · KG-MNP Evidence Workbench";
  root.replaceChildren(heading("Review trace", "Review history is not an asserted business fact", "Confirmed, modified, rejected and deferred decisions remain review records. Rejected or deferred candidates never appear as current business facts."));
  root.append(node("p", "review-boundary", "Semantic boundary: review outcome ≠ asserted business state."));
  const form = node("form", "query-form");
  const resource = field(form, "Candidate or reviewed resource identifier", "resource_id", DEFAULTS.candidate);
  formButton(form, "Inspect review history");
  const results = panel("Review history", "Decision ID, candidate ID, outcome and review lineage");
  results.body.append(node("p", "empty-state", "Submit a review resource identifier."));
  root.append(form, results.wrapper);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    loading(results.body);
    try {
      const query = new URLSearchParams({ resource_id: resource.value, limit: "100", offset: "0" });
      const model = await jsonRequest(`/workbench/api/view/review?${query.toString()}`);
      results.body.replaceChildren(resultMetadata(model), rowsTable(model, "Review records — not asserted business facts"));
    } catch (error) {
      renderError(results.body, error);
    }
  });
}

function disableBrowsing(error) {
  const message = error instanceof Error ? error.message : "WORKBENCH_NOT_READY";
  chip.textContent = "Workbench not ready";
  chip.classList.add("failed");
  blockingMessage.textContent = message;
  blocking.hidden = false;
  root.replaceChildren();
  for (const link of document.querySelectorAll(".primary-nav a")) {
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
  }
}

async function start() {
  setCurrentNavigation();
  let status;
  try {
    status = await jsonRequest("/workbench/api/status");
    if (status.status !== "WORKBENCH_READY") throw new Error("WORKBENCH_NOT_READY");
  } catch (error) {
    disableBrowsing(error);
    return;
  }
  chip.textContent = "Foundation verified · Phase 01 verified";
  chip.classList.add("ready");
  const path = window.location.pathname;
  if (path === "/") dashboard(status);
  else if (path === "/ontology") await ontologyPage();
  else if (path === "/entity") entityPage();
  else if (path === "/fact") factPage();
  else if (path === "/trace") tracePage();
  else if (path === "/review") reviewPage();
  else disableBrowsing(new Error("WORKBENCH_NOT_READY"));
}

start();

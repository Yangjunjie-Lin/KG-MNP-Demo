#!/usr/bin/env bash
# Generate ontology HTML docs with a pinned WIDOCO version.
# Failure here must NOT fail core pytest - this is optional documentation.

set -euo pipefail

WIDOCO_VERSION="1.4.25"
# Release assets are JDK-specific (see https://github.com/dgarijo/Widoco/releases/tag/v1.4.25)
WIDOCO_JAR="widoco-${WIDOCO_VERSION}-jar-with-dependencies_JDK-17.jar"
WIDOCO_URL="https://github.com/dgarijo/Widoco/releases/download/v${WIDOCO_VERSION}/${WIDOCO_JAR}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/docs/ontology-site"
MERGED="${ROOT}/docs/ontology-site/_merged-ontology.ttl"
TOOLS="${ROOT}/third_party/widoco"

mkdir -p "${TOOLS}" "${OUT}"

if ! command -v java >/dev/null 2>&1; then
  echo "ERROR: Java not found. Install JRE 11+ to run WIDOCO." >&2
  echo "Core tests do not require WIDOCO." >&2
  exit 2
fi

if [[ ! -f "${TOOLS}/${WIDOCO_JAR}" ]]; then
  echo "Downloading WIDOCO ${WIDOCO_VERSION} (${WIDOCO_JAR})..."
  if ! curl -fsSL -L -o "${TOOLS}/${WIDOCO_JAR}" "${WIDOCO_URL}"; then
    echo "ERROR: Failed to download WIDOCO from ${WIDOCO_URL}" >&2
    echo "Core tests do not require WIDOCO." >&2
    exit 3
  fi
fi

# Merge ontology files with RDFLib for a single WIDOCO input
python - <<PY
from pathlib import Path
from rdflib import Graph
root = Path(r"${ROOT}")
g = Graph()
for name in ["mnp-core.ttl", "mnp-compliance.ttl", "mnp-alignments.ttl"]:
    g.parse(root / "ontology" / name, format="turtle")
out = root / "docs" / "ontology-site" / "_merged-ontology.ttl"
out.parent.mkdir(parents=True, exist_ok=True)
g.serialize(out, format="turtle")
print(f"Merged ontology -> {out} ({len(g)} triples)")
PY

java -jar "${TOOLS}/${WIDOCO_JAR}" \
  -ontFile "${MERGED}" \
  -outFolder "${OUT}" \
  -rewriteAll \
  -getOntologyMetadata \
  -uniteSections || {
    echo "ERROR: WIDOCO execution failed." >&2
    echo "Core tests do not require WIDOCO." >&2
    exit 4
  }

test -f "${OUT}/index-en.html" || test -f "${OUT}/index.html" || { echo "ERROR: index.html missing"; exit 5; }
if [[ -f "${OUT}/index-en.html" && ! -f "${OUT}/index.html" ]]; then
  cp "${OUT}/index-en.html" "${OUT}/index.html"
fi
echo "WIDOCO documentation generated at ${OUT}"
ls "${OUT}/index.html" "${OUT}/provenance" >/dev/null 2>&1 || true

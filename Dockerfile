FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY ontology ./ontology
COPY shapes ./shapes
COPY data ./data
COPY rules ./rules
COPY schemas ./schemas
COPY queries ./queries
COPY mappings ./mappings
COPY references ./references
COPY inputs ./inputs
COPY competency_questions ./competency_questions
COPY config ./config
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[api]"

ENV KG_MNP_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ENV KG_MNP_API_HOST=0.0.0.0
ENV KG_MNP_API_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "kg_mnp_demo.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

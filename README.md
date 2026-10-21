# Health AI Ethics & Compliance Evaluator

A rule-based **RAG + LLM** system that evaluates AI systems in healthcare against ethical and legal requirements — EU AI Act, KVKK (Turkish data protection law), GDPR, ISO/IEC 42001:2023 and the WHO guidance on large multimodal models.

> Built as the final project for *YZM714 – Ethical and Legal Dimensions of AI* (AI Engineering MSc, İzmir Bakırçay University, 2026).

## What it does
You describe a healthcare AI use case (e.g. a pharmacy stock forecasting model or a radiology decision-support tool). The system:

1. **Retrieves** the relevant regulation passages with hybrid search (semantic 60% + BM25 40%)
2. **Scores** the use case on **7 ethical dimensions** (0–100) with a transparent, JSON-defined rule engine
3. **Generates** an evidence-based risk assessment with Claude, citing its sources
4. **Exports** the full analysis as a PDF report

### 7 dimensions
Fairness & Bias · Transparency & Explainability · Accountability · Privacy & Data Protection · Human Oversight · Legal Compliance · Safety

### Built-in use cases
| Use case | EU AI Act category |
|---|---|
| Pharmacy stock management AI | High-risk (Annex III) |
| Clinical decision support / radiology | High-risk (Annex III) + MDR |
| Multi-center model training on health data | High-risk (Annex III) |

## Architecture
```
User query ─► Hybrid retriever (ChromaDB + sentence-transformers + BM25)
                     │
                     ▼
            Rule engine (rules/ethics_rules.json) ─► dimension scores
                     │
                     ▼
            LLM (Claude API or local Ollama) ─► cited assessment ─► PDF
```

**Stack:** Python · Streamlit · ChromaDB · sentence-transformers · rank-bm25 · Anthropic Claude API · Ollama (optional) · fpdf2

## Run locally
```bash
pip install -r requirements.txt

# Set your key (or use Ollama, see below)
export LLM_BACKEND=anthropic
export ANTHROPIC_API_KEY=your-key

python ingest.py          # builds the vector index once
streamlit run app.py      # http://localhost:8501
```

**No API key?** Run fully local with Ollama:
```bash
export LLM_BACKEND=ollama
export OLLAMA_MODEL=llama3.2:latest
streamlit run app.py
```

## Project structure
```
app.py              Streamlit UI
rag_pipeline.py     Hybrid retrieval + rule engine + LLM call
ingest.py           Loads knowledge base into ChromaDB
pdf_rapor.py        PDF report generator
rules/              7 dimensions, weights, checklists, legal references
knowledge_base/     Curated regulation summaries (7 sources, 29 chunks)
```

## Notes
- The UI and reports are in Turkish.
- This is an academic prototype, not legal advice.

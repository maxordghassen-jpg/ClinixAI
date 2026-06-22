---
name: project-clinixai-eval
description: ClinixAI evaluation service v2 — architecture, metrics, endpoints, and frontend dashboard
metadata:
  type: project
---

Evaluation service (port 8006) was fully rebuilt in session 3 (2026-05-28).

**Backend changes:**
- New metrics: `em_score.py` (Exact Match), `esm_score.py` (Jaccard ESM), `answer_correctness.py` (0.6×sem + 0.4×token_f1), `answer_relevancy.py` (question–answer cosine), `context_precision.py` (fraction of memories reflected)
- `rouge_score.py` updated to return `RougeScores` dataclass with rouge1/rouge2/rougeL in one pass
- `eval_schemas.py` — complete EvalResult with all 15+ metric fields + EvalSummary + TrendResponse + CompareResult
- `llm_judge.py` — now evaluates 4 always-on dimensions (conv_quality, hallucination, safety, answer_relevancy) + conditional answer_correctness, workflow, memory_relevance, context_precision, personalization
- `orchestrator.py` — all metrics run in parallel via asyncio.gather; updated WEIGHTS include answer_correctness (0.10) and answer_relevancy (0.08)
- MongoDB persistence via motor: `app/db/mongo_client.py` + `app/services/result_store.py`, collection `evaluation_results`
- `settings.py` — added MONGODB_URI, MONGODB_DB, ENABLE_MONGO
- `requirements.txt` — added motor, pymongo
- New endpoints: GET /results, GET /results/history, GET /results/trends, GET /results/{id}, DELETE /results/{id}, POST /results/compare, GET /results/export/csv, GET /results/export/json

**Frontend changes:**
- recharts installed as dependency
- `frontend/types/eval.ts` — full TypeScript types for EvalResult, EvalSummary, TrendResponse, CompareResult, EvalScenario + helper functions scoreColor/scoreLabel
- `frontend/lib/evalApi.ts` — typed API layer for all eval endpoints
- New API proxy routes: /api/eval/results, /api/eval/results/history, /api/eval/results/trends, /api/eval/results/compare, /api/eval/results/[id], /api/eval/results/export/csv, /api/eval/results/export/json
- 8 reusable components in `frontend/components/eval/`: ScoreRing, MetricCard, JudgePanel, TrendChart, RadarEvaluation, LatencyChart, EvaluationHistory, ScenarioRunner
- `frontend/app/eval/page.tsx` — full 5-tab dashboard (Scenarios, Manual, Last Result, Analytics, Compare)

**Why:** User requested production-grade evaluation pipeline with all standard NLP metrics, MongoDB history, trend charts, and run comparison.
**How to apply:** When working on eval features, all metric files are independent and unit-testable. MongoDB is optional (ENABLE_MONGO=False for stateless mode). Frontend charts use recharts (not a shadcn chart library).

# ClinixAI — Technology Choices & Justifications

## 1. LangGraph (vs. Raw LangChain, Custom FSM, RASA)

**What it is**: A Python library for building stateful, multi-step AI agents using a directed graph execution model built on top of LangChain.

**Why chosen**:
- Healthcare appointment booking is inherently multi-turn: specialty → doctor selection → date → time → confirmation. A naive single-prompt approach cannot maintain this context.
- LangGraph's `StateGraph` provides a formal data flow model where state is explicit and first-class — every node receives a typed `AgentState` and returns an updated copy.
- Cross-workflow transitions (user pivoting from booking to viewing appointments mid-flow) require controlled state invalidation. LangGraph's node model allows `WorkflowNode` to surgically reset specific state fields and sync deletions to Redis without complex callback logic.
- Conditional routing (step-based flow control) is natural in LangGraph without custom dispatcher code.

**Alternatives rejected**:
- **Raw LangChain chains**: No formal state model; difficult to maintain multi-turn context across 5+ steps.
- **Custom FSM**: Would require building state machine infrastructure from scratch, including async execution, error handling, and state persistence.
- **RASA**: Designed for intent-and-entity chatbots, not for deep API-integrated workflow automation with LLM reasoning at each step.
- **Haystack**: Document retrieval focus; lacks workflow orchestration primitives.

---

## 2. FastAPI (vs. Flask, Django, Express)

**What it is**: A modern Python web framework for building async APIs with built-in Pydantic integration and OpenAPI documentation.

**Why chosen**:
- **Async first**: All LLM API calls, Redis operations, and MongoDB queries are async. FastAPI's native async support means 5 concurrent LLM evaluation calls (in the evaluation orchestrator) run truly in parallel without blocking.
- **Pydantic integration**: The request/response schemas are Pydantic models. FastAPI automatically validates incoming JSON against `EvalRequest`, `ChatRequest`, etc. and returns typed `EvalResult` objects.
- **Performance**: FastAPI benchmarks 2–4× faster than Flask for high-concurrency workloads.
- **Auto-generated docs**: `/docs` endpoint provides interactive Swagger UI for all microservices.

**Alternatives rejected**:
- **Flask**: Synchronous by default; async support in Flask 2.0 is limited and requires extra configuration. No native Pydantic integration.
- **Django**: Too heavyweight for focused microservices; ORM and admin not needed.
- **Express (Node.js)**: Would require Python-to-Node communication bridges for the LangGraph/LangChain Python ecosystem.

---

## 3. Redis (vs. In-Memory Dict, PostgreSQL Session Store, Memcached)

**What it is**: An in-memory data structure store supporting strings, hashes, lists, sets, and sorted sets with native TTL.

**Why chosen**:
- **Sub-millisecond latency**: Session state must be retrieved at the start of every turn. Redis HGETALL on a session namespace takes <1ms vs. 10–50ms for a PostgreSQL query.
- **Native TTL**: Session keys automatically expire after 30 minutes of inactivity. No background cleanup job needed.
- **Hash data structure**: Redis hashes map perfectly to `state.memory` dict — each field is a separate key, enabling surgical deletion (`DEL session:abc:step`) during cross-workflow resets without reading and rewriting the entire document.
- **Atomic operations**: Redis HSET is atomic; no race conditions when multiple requests arrive concurrently for the same session.
- **Pub/sub (future)**: Redis pub/sub would enable real-time push notifications to patients when appointments are confirmed.

**Alternatives rejected**:
- **In-memory dict (Python)**: Does not survive process restart; cannot be shared across multiple agent_service instances (horizontal scaling).
- **PostgreSQL**: Relational database latency (10–100ms per query) is unacceptable for per-turn state retrieval.
- **Memcached**: Lacks native hash structure (would require JSON serialize/deserialize entire dict) and lacks surgical key deletion.

---

## 4. MongoDB (vs. PostgreSQL, SQLite, Firestore)

**What it is**: A document-oriented NoSQL database storing BSON documents.

**Why chosen for different use cases**:

- **`user_memories`**: The document schema for memories includes a 384-dimensional float array. MongoDB natively stores arrays without schema changes. PostgreSQL would require a `vector` extension (pgvector) or a separate embedding store.
- **`evaluation_results`**: The `EvalResult` schema has 30+ fields, many nullable, plus a nested `dimensions` dict. MongoDB's schema-less model accommodates this without complex migrations.
- **`medical_data_tunisia`**: Google Places data has variable fields per facility type. MongoDB's flexibility avoids nullable-column proliferation.
- **Geospatial**: MongoDB supports `$geoNear` and `2dsphere` indexes natively for the geo service.
- **Atlas cloud**: MongoDB Atlas provides managed cloud hosting with automatic backups, replication, and monitoring.

**Alternatives considered**:
- **PostgreSQL**: Better for relational data (appointments, users). In practice, the appointment service could use PostgreSQL, but MongoDB was chosen for consistency across services.
- **SQLite**: Not suitable for production multi-service use; no network protocol.
- **Firestore**: Would create Google Cloud vendor lock-in.

---

## 5. Next.js 16 App Router (vs. Create React App, Vue, Angular)

**What it is**: A React framework with server-side rendering, file-based routing, and an App Router for React Server Components.

**Why chosen**:
- **API routes**: The `/app/api/**` directory enables server-side proxy routes that forward requests to backend microservices. This avoids CORS issues without a dedicated API gateway.
- **TypeScript first-class**: Next.js TypeScript support is seamless — the type definitions in `types/eval.ts` are shared across API routes and components.
- **Performance**: React Server Components reduce JavaScript bundle size; image optimization is built-in.
- **Deployment flexibility**: Next.js can be deployed on Vercel, Docker, or as a standalone Node.js server.

**Alternatives rejected**:
- **Create React App**: SPA only; no API route capability; no SSR.
- **Vue/Nuxt**: Different ecosystem; React/Next was chosen for its larger component ecosystem (Recharts, Framer Motion, MapLibre bindings).
- **Angular**: Too heavy for a startup/thesis project; steeper learning curve.

---

## 6. Recharts (vs. Chart.js, D3.js, Victory, Nivo)

**What it is**: A React chart library built on D3.js with a declarative component API.

**Why chosen**:
- **React-native**: Charts are React components — `<LineChart>`, `<RadarChart>`, `<BarChart>`. This integrates naturally with React state and Tailwind.
- **TypeScript support**: Full TypeScript definitions for all chart props.
- **Recharts `ReferenceLine`**: The thesis-style average reference line (dashed red) used in `ThesisCurveChart` is a first-class Recharts primitive.
- **`connectNulls`**: The `connectNulls` prop on `<Line>` is critical for the NLP curve charts — it connects line segments across runs where a metric was not computed (e.g., BLEU disabled).

**Alternatives rejected**:
- **D3.js direct**: Too low-level; requires imperative DOM manipulation incompatible with React's declarative model.
- **Chart.js**: Canvas-based (not SVG); harder to customize with React; no `connectNulls` equivalent.
- **Victory**: Less maintained; fewer chart types.

---

## 7. Groq API / LLM Provider (vs. OpenAI, Mistral, Local Ollama)

**What it is**: A cloud AI inference provider offering LLM APIs optimized for low latency.

**Why chosen**:
- **Speed**: Groq's hardware (custom ASIC) delivers ~500 tokens/second output — 5–10× faster than OpenAI GPT-4.
- **`llama-3.3-70b-versatile`**: A strong open-weight model with excellent multilingual capabilities (Arabic, French, English).
- **Temperature=0.0**: Deterministic outputs for intent classification and judge scoring — critical for reproducible evaluation results.
- **JSON output**: The model reliably follows JSON schema instructions for structured extraction.

**Alternatives considered**:
- **OpenAI GPT-4**: Higher cost; slower inference; API rate limits more restrictive.
- **Local Ollama**: Would require local GPU; deployment complexity; lower quality for small GPU configurations.
- **Mistral**: Good alternative; Groq was preferred for the combination of speed + multilingual + 70B parameter scale.

---

## 8. Microservices Architecture (vs. Monolith)

**Why microservices for ClinixAI**:

1. **Technology heterogeneity**: The geo_service uses Flask + synchronous MongoDB queries (natural for batch data processing). The agent_service uses FastAPI + async operations. A monolith would force one framework choice.

2. **Independent deployment**: The evaluation service can be deployed on a GPU-equipped server for BERTScore computation while the patient-facing agent service runs on a standard CPU server.

3. **Fault isolation**: A failure in the evaluation service does not affect patient booking workflows.

4. **Database separation**: Each service owns its MongoDB collections. The geo_service connects to `medical_data_tunisia`; the evaluation service to `eval_db`. Cross-service queries go through HTTP APIs, not direct database access.

**The cost**: Inter-service HTTP calls add ~1–5ms per call compared to in-process function calls. For ClinixAI, where LLM API calls dominate at 400–2000ms, this overhead is negligible.

---

## 9. LLM-as-a-Judge (vs. Pure NLP Metrics, Human Evaluation)

**Why LLM-as-a-Judge**:
- **Scale**: Human evaluation is expensive and slow — cannot run after every code change.
- **Healthcare specificity**: ROUGE/BLEU cannot evaluate whether the agent correctly identified a life-threatening urgency, or whether it safely avoided recommending specific medications.
- **Proactivity measurement**: No classical metric can reward "agent offered to book the appointment before being asked."
- **Calibration**: By using a powerful LLM (llama-3.3-70b) to evaluate a smaller workflow LLM, the judge has genuine understanding of quality dimensions.

**Limitations acknowledged**:
- LLM judges can have biases (verbosity bias, reference bias) — addressed by explicit anti-bias rules in the prompts.
- LLM judge scores are not perfectly reproducible (temperature=0.0 mitigates but doesn't eliminate variance).
- Judge itself can hallucinate explanations.

---

## 10. BERTScore (vs. TF-IDF Cosine Similarity)

**Why BERTScore for semantic similarity**:
- BERTScore uses contextual embeddings from a transformer model: "appointment" in "book an appointment" and "consultation" in "schedule a consultation" map to nearby embedding vectors — TF-IDF would give these zero similarity.
- `bert-base-multilingual-cased` handles Arabic and French without requiring separate models.
- BERTScore correlates more strongly with human quality judgments than ROUGE or BLEU (demonstrated on WMT translation benchmarks).

---

## 11. Tailwind CSS (vs. Styled-Components, CSS Modules, Bootstrap)

**Why Tailwind**:
- **Utility-first**: All styling is done in JSX with utility classes — no context switching to CSS files.
- **Design constraints**: Tailwind's scale system (spacing, colors, rounded corners) enforces visual consistency across the 5-tab evaluation dashboard.
- **No runtime overhead**: Tailwind generates static CSS at build time; no JavaScript CSS-in-JS overhead.
- **Dark mode (future)**: Tailwind's `dark:` prefix makes dark mode straightforward.

---

## 12. paraphrase-multilingual-MiniLM-L12-v2 (vs. OpenAI text-embedding-ada)

**Why this embedding model**:
- **Free, local inference**: No API cost per embedding. With potentially thousands of memory lookups per day, API-based embeddings would incur significant costs.
- **Multilingual**: Supports 50+ languages including Arabic and French — critical for ClinixAI's trilingual use case.
- **Lightweight**: 384 dimensions (vs. 1536 for ada-002) means faster cosine similarity computation and smaller storage per embedding.
- **Paraphrase-trained**: Optimized specifically for semantic similarity between paraphrases — "book an appointment" and "schedule a meeting" should be near-identical in embedding space, which is exactly the property needed for memory retrieval.

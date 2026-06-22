# ClinixAI — Frontend Architecture (Next.js)

## 1. Technology Stack

The ClinixAI frontend is built with:

- **Next.js 16** with the App Router (React Server Components + Client Components)
- **React 19** with hooks (useState, useEffect, useCallback, useMemo)
- **TypeScript** for full static typing across all components and API contracts
- **Tailwind CSS** for utility-first styling with a slate/violet design system
- **Zustand** for global state management (auth store, session store)
- **Recharts** for all data visualization (line charts, bar charts, radar charts, area charts)
- **Framer Motion** for animated tab transitions and card hover states
- **MapLibre GL / react-map-gl** for interactive map rendering
- **FullCalendar** for doctor schedule management UI
- **Lucide React** for icons throughout the UI

## 2. Directory Structure

```
frontend/
├── app/                        # Next.js App Router pages
│   ├── layout.tsx              # Root layout: HTML, global CSS, auth provider
│   ├── globals.css             # Tailwind directives + custom CSS variables
│   ├── page.tsx                # Landing / login / signup page
│   ├── patient/
│   │   └── page.tsx            # Patient chat interface with map + calendar sidebar
│   ├── doctor/
│   │   └── page.tsx            # Doctor dashboard: calendar, appointments, AI chat
│   └── eval/
│       └── page.tsx            # 5-tab evaluation dashboard
├── components/
│   ├── eval/
│   │   ├── ThesisCurveChart.tsx   # Orange line chart + red average ReferenceLine
│   │   ├── RadarEvaluation.tsx    # Spider/radar chart for multi-dimension scores
│   │   ├── ScoreRing.tsx          # Circular progress ring for overall_score
│   │   ├── MetricCard.tsx         # Single metric display card with color coding
│   │   ├── JudgePanel.tsx         # LLM judge per-dimension explanation panel
│   │   ├── EvaluationHistory.tsx  # Sortable/filterable history table
│   │   ├── ScenarioRunner.tsx     # Scenario selector with Run button
│   │   ├── TrendChart.tsx         # Area chart: overall/safety/hallucination over time
│   │   └── LatencyChart.tsx       # Bar chart: response latency per run
│   └── (other shared components)
├── lib/
│   ├── api.ts                  # Agent service API client
│   ├── evalApi.ts              # Evaluation service API client
│   └── proxy.ts                # Next.js API route → backend service proxy
├── types/
│   ├── index.ts                # Chat message types, doctor/patient interfaces
│   └── eval.ts                 # Evaluation result types, trend types, score utilities
└── package.json                # Dependencies
```

## 3. Page: `app/page.tsx` — Landing / Auth

The root page handles user authentication. It renders either a **login form** or **signup form** depending on a local state toggle.

**Key logic:**
- On login success, the JWT token is stored in localStorage via the Zustand auth store.
- The token payload (role: "patient" | "doctor", patient_profile_id, doctor_id) determines routing.
- Patients are redirected to `/patient`, doctors to `/doctor`.
- The page is a pure client component (`"use client"`) — no server-side rendering.

**API call:** `POST /api/auth/login` or `POST /api/auth/signup` via the proxy layer.

## 4. Page: `app/patient/page.tsx` — Patient Chat Interface

The most complex page in the system. It renders:

### Chat Panel (main area)
- A scrollable message history with user and assistant message bubbles
- A text input with a send button
- Real-time streaming rendering of the agent's response (token-by-token if SSE is available, or full response)
- Message timestamps

### Map Sidebar
- An interactive **MapLibre GL** map rendering doctor/pharmacy pins
- Pin data comes from geo search results embedded in agent responses
- Clicking a pin shows a popup with name, address, phone, rating
- The map zooms to fit all returned results automatically

### Appointments Calendar
- A **FullCalendar** view showing the patient's upcoming appointments
- Appointments are fetched from the appointment service and rendered as calendar events
- Clicking an event shows appointment details (doctor, time, status)

**State management:**
- `messages: Message[]` — full conversation history
- `mapPins: GeoPlace[]` — current map pins extracted from agent response
- `appointments: Appointment[]` — loaded from appointment service
- `sessionId: string` — generated UUID for this browser session

**API call flow:**
1. User sends message → `POST /api/agent` (proxy) → agent_service `/chat`
2. Response includes `response` text and optionally `geo_results` embedded in the message
3. If `geo_results` present, `mapPins` state is updated → map re-renders with new pins
4. After booking, appointments list is refreshed

## 5. Page: `app/doctor/page.tsx` — Doctor Dashboard

The doctor's interface focuses on practice management rather than chat:

- **FullCalendar** week/month view showing all doctor appointments
- **Appointment list panel** with status badges (confirmed, cancelled, pending)
- **Patient profile viewer** — clicking an appointment shows the patient's details
- **AI assistant chat panel** — the doctor graph agent for administrative queries
- **Availability manager** — create/update weekly schedule slots

**Key design decision:** The doctor view separates patient-facing actions from physician actions by using a different graph (doctor graph) with different system prompts and different available actions.

## 6. Page: `app/eval/page.tsx` — Evaluation Dashboard

The most sophisticated frontend page. It is a 5-tab analytics dashboard for monitoring and testing the AI agent's quality.

### Tab 1: Scenarios
- Displays all available evaluation scenarios from `evaluation_service/datasets/eval_scenarios.py`
- Each scenario shows: ID, name, category badge, language, role, description
- A "Run" button triggers `runScenario(id)` → `POST /api/eval/scenarios/{id}/run`
- Running indicator shows a spinner on the active scenario
- On completion, switches to the Results tab and adds the result to `sessionResults`

### Tab 2: Manual Eval
- Free-form text inputs for user_message, agent_response, reference_response
- Language and role selectors
- ROUGE/BLEU toggle checkboxes
- Submit → `runManualEval(payload)` → `POST /api/eval/evaluate`

### Tab 3: Last Result
- Full breakdown of the most recently run evaluation
- `ScoreRing` showing the overall_score percentage
- `RadarEvaluation` spider chart with 8 dimensions
- Two-column metric grid:
  - **Section A** (Classical NLP): BERTScore, ROUGE-1/2/L, BLEU, EM, Set Match
  - **Section B** (Modern Agent): Safety, Hallucination, Groundedness, Workflow, Conversational, Answer Correctness, Answer Relevancy, Memory Relevance, Personalization, Context Precision
- Metric overview bar chart
- `JudgePanel` with per-dimension scores and LLM explanations
- Collapsible full judge explanation text

### Tab 4: Analytics
- **Section A — Classical NLP Curves:**
  - 4 `ThesisCurveChart` components: BLEU, ROUGE-1, ROUGE-2, ROUGE-L
  - Data sourced from `unifiedTimeline` (merged MongoDB history + session results)
- **Section B — Modern Agent Quality:**
  - `RadarEvaluation` for last run profile
  - Global averages horizontal bar chart from `trends.averages`
  - 4 `ThesisCurveChart` components: Workflow Score, Conversational Quality, Hallucination Faithfulness (1 - risk), Groundedness Score
  - Score Evolution `TrendChart` (area chart)
  - Latency `LatencyChart`
  - Best/Worst run cards
- **Section C — History:**
  - `EvaluationHistory` sortable/filterable table

### Tab 5: Compare
- Select two evaluation run IDs from history
- Side-by-side comparison with delta column (green = improvement, red = regression)
- All metric fields compared in a table

### State Architecture in eval/page.tsx

```typescript
// Persistent (MongoDB-backed, loaded on mount)
const [history, setHistory]     = useState<EvalSummary[]>([]);
const [trends,  setTrends]      = useState<TrendResponse | null>(null);

// Session (current browser session)
const [sessionResults, setSessionResults] = useState<EvalResult[]>([]);
const [lastResult,     setLastResult]     = useState<EvalResult | null>(null);

// Derived (useMemo)
const unifiedTimeline = useMemo(...);  // Merged MongoDB + session, sorted by evaluated_at
const nlpCurves       = useMemo(...);  // BLEU/ROUGE series from unifiedTimeline
const agentCurves     = useMemo(...);  // Workflow/Conv/Halluc/Groundedness series
const judgeBarData    = useMemo(...);  // Global averages for horizontal bar chart
const stats           = useMemo(...);  // KPI card values
```

The **unified timeline** is the key insight: it uses a `Map<string, UnifiedPoint>` keyed on `evaluated_at` to merge MongoDB historical runs with in-session runs, with session results overriding on timestamp collision (since session data is richer).

## 7. API Proxy Layer: `lib/proxy.ts`

Next.js API routes cannot call backend services directly from the browser in production (CORS, service discovery). The proxy layer resolves this:

```
Browser → POST /api/agent
        → Next.js API route handler (app/api/agent/route.ts)
        → proxy.ts rewrites to http://localhost:8001/chat
        → Returns response to browser
```

The proxy rewrites requests based on path patterns:
- `/api/agent/**` → `http://localhost:8001/**`
- `/api/auth/**` → `http://localhost:8005/**`
- `/api/eval/**` → `http://localhost:8006/**`
- `/api/availability/**` → `http://localhost:8002/**`
- `/api/geo/**` → `http://localhost:5000/**`

This allows the frontend to use relative URLs while maintaining clean separation between microservices.

## 8. API Client: `lib/evalApi.ts`

The evaluation API client wraps all evaluation service endpoints:

```typescript
fetchScenarios()              → GET  /api/eval/scenarios
runScenario(id)               → POST /api/eval/scenarios/{id}/run
runManualEval(payload)        → POST /api/eval/evaluate
fetchHistory(limit)           → GET  /api/eval/history?limit=N
fetchTrends(limit)            → GET  /api/eval/trends?limit=N
fetchResult(id)               → GET  /api/eval/results/{id}
compareResults(idA, idB)      → GET  /api/eval/compare?id_a=A&id_b=B
exportCsvUrl(limit)           → GET  /api/eval/export/csv?limit=N
exportJsonUrl(limit)          → GET  /api/eval/export/json?limit=N
```

## 9. TypeScript Types: `types/eval.ts`

The type system exactly mirrors the backend Pydantic schemas:

- `EvalResult` — full evaluation result with all metric fields
- `EvalSummary` — lightweight history row (id, overall_score, latency_ms, evaluated_at)
- `TrendPoint` — single time-series data point for analytics charts
- `TrendResponse` — points[] + averages + best_run + worst_run
- `EvalScenario` — scenario definition (id, name, category, user_message, reference_response)
- `CompareResult` — run_a, run_b, delta Record<string, number|null>
- `JudgeDimension` — score, explanation, confidence per dimension
- `scoreColor()` — utility: maps score to "emerald"|"amber"|"rose"|"slate"
- `scoreLabel()` — utility: "Excellent"|"Good"|"Fair"|"Poor"|"Critical"
- `METRIC_LABELS` — display names for all metric keys
- `CATEGORY_LABELS` — display names for scenario categories

## 10. Key UI Components

### `ThesisCurveChart`
A thesis-style line chart (orange curve + red dashed average ReferenceLine). Renders:
- Recharts `LineChart` with `connectNulls` (spans missing data points)
- `type="monotone"` interpolation for smooth curves
- Average, max, min statistics in the header
- Empty state with chart icon when no data

**Data format:** `{ label: string, value: number | null }[]` — value is in [0, 1] range, displayed as %.

### `RadarEvaluation`
A multi-dimensional radar/spider chart showing 8 evaluation dimensions:
- Safety, Groundedness, Workflow, Conversational, Relevancy, Correctness, Memory, Personalization
- Filters out null dimensions (requires ≥ 3 valid points)
- Uses Recharts `RadarChart` with violet fill (opacity 0.12)

### `ScoreRing`
A circular progress ring (SVG-based) showing the overall score. Color changes from rose → amber → emerald based on score threshold.

### `MetricCard`
A card displaying a single metric with:
- Formatted percentage value
- Color-coded background (emerald/amber/rose)
- Optional "inverted" flag for metrics where lower = better (e.g., hallucination_risk)

### `JudgePanel`
An accordion/expandable panel showing per-dimension LLM judge details:
- Dimension name + score
- Model's explanation text
- Confidence indicator

## 11. Tailwind Design System

The UI uses a consistent design language:
- **Primary accent**: `#7C3AED` (violet-600)
- **Background**: `#F8FAFC` (slate-50)
- **Cards**: white with `border-slate-200` and `shadow-sm`
- **Rounded corners**: `rounded-2xl` (16px) for cards, `rounded-xl` (12px) for inputs
- **Score colors**: emerald (#10b981) for ≥75%, amber (#f59e0b) for ≥50%, rose (#f43f5e) for <50%
- **Typography**: slate-900 headings, slate-600 body, slate-400 subtitles

Hover states use Framer Motion `whileHover={{ y: -2 }}` for card lift effects.

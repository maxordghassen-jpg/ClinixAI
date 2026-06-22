# ClinixAI — Thesis-Ready Academic Explanations

---

## 1. System Overview

ClinixAI is a conversational multi-agent AI platform designed to digitize and automate healthcare access workflows in a Tunisian clinical context. The system integrates large language model (LLM) reasoning with persistent semantic memory, structured workflow orchestration, geolocation services, and a rigorous evaluation framework to deliver an end-to-end AI-powered healthcare assistant.

The platform addresses a critical accessibility challenge: in Tunisia and across the broader Maghreb region, patients face significant friction in accessing healthcare services — from locating qualified specialists in their vicinity to navigating appointment scheduling processes that remain predominantly telephone-based or walk-in. ClinixAI proposes a conversational AI interface that enables patients to interact naturally in three languages (Arabic, French, English) to accomplish tasks including specialist search, appointment booking, appointment management, and proximity-based facility discovery.

Concurrently, ClinixAI provides a parallel AI assistant for physicians, enabling doctors to manage their practice through natural language queries while the system maintains context-aware awareness of their appointment calendar and patient profiles.

The technical architecture of ClinixAI is grounded in modern AI engineering principles: stateful graph-based agent orchestration (LangGraph), long-term semantic memory with dense vector retrieval, microservices decomposition for independent scalability, and a comprehensive observability layer that quantifies agent quality across both classical NLP dimensions and novel agentic behavioral dimensions.

---

## 2. AI Contribution and Innovation

### 2.1 Multi-Agent Workflow Orchestration

The central AI contribution of ClinixAI is its **graph-based multi-agent workflow orchestration** architecture. Unlike conventional retrieval-augmented generation (RAG) systems or single-turn chatbots, ClinixAI implements a stateful directed acyclic graph (DAG) of specialized agents — each responsible for a distinct cognitive task — coordinated through a typed state object.

The patient-facing agent pipeline consists of five nodes:
1. **MemoryNode**: Retrieves and contextualizes prior knowledge about the patient
2. **IntentNode**: Applies LLM reasoning to classify user intent and extract structured parameters
3. **WorkflowNode**: Implements a finite state machine for workflow step transitions
4. **ActionNode**: Executes business logic actions (API calls, response generation)
5. **StateWriterNode**: Persists updated state and extracts new long-term memories

This separation of concerns enables fine-grained control over agent behavior that is not achievable with a single monolithic prompt. Each node is independently testable, replaceable, and extendable — a property particularly valuable in a safety-sensitive domain such as healthcare.

### 2.2 Proactive Workflow-Oriented Agent Design

A key innovation of ClinixAI's agent design is its emphasis on **proactivity** as a quality dimension, rather than mere responsiveness. The system is designed not to wait passively for users to specify each element of a complex workflow. Instead, the agent:

- Initiates multi-step workflows from minimal user input ("I need a cardiologist urgently" → complete booking workflow)
- Presents ranked alternatives proactively ("Here are 3 cardiologists with the earliest availability — want me to book one?")
- Detects workflow abandonment and resets stale state when the user pivots
- Leverages memory to anticipate rebooking needs without being prompted

This proactivity-first design is calibrated into the evaluation system: the LLM judge explicitly rewards initiative (conversational_quality ≥ 0.85 for proactive responses) and the workflow metric measures task advancement, not just response correctness.

### 2.3 Cross-Lingual Healthcare AI

ClinixAI operates natively in Arabic, French, and English — supporting code-switching and handling transliterated medical terminology. This is technically achieved through:

1. **LLM instruction-following**: The Groq `llama-3.3-70b-versatile` model receives language detection and response language instructions as part of the system prompt
2. **Multilingual embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` generates language-agnostic semantic vectors, enabling cross-lingual memory retrieval (a memory stored in French is retrievable by an Arabic query)
3. **Unicode-safe NLP normalization**: A custom text normalizer preserves Arabic combining characters and French diacritics while removing punctuation noise
4. **Multilingual geo search**: The proximity API normalizes Arabic facility type terms to French before MongoDB queries

This multilingual capability is directly relevant to the Tunisian healthcare context, where patient-physician communication occurs fluidly across Arabic and French.

---

## 3. Multi-Agent Architecture (Academic Formulation)

### Formal Graph Definition

Let $G = (N, E, S_0)$ be the patient agent graph where:
- $N = \{MemoryNode, IntentNode, WorkflowNode, ActionNode, StateWriterNode\}$ is the set of nodes
- $E \subseteq N \times N$ is the set of directed edges defining execution order
- $S_0 = AgentState(\text{session\_id}, m, \text{memory}={}, \text{response}="", \dots)$ is the initial state

Each node $n_i \in N$ is a function $f_i: S \rightarrow S$ that transforms the agent state. The graph execution is the composition $S_T = f_5 \circ f_4 \circ f_3 \circ f_2 \circ f_1(S_0)$.

### Workflow State Machine

$WorkflowNode$ implements a deterministic finite automaton (DFA) $A = (Q, \Sigma, \delta, q_0, F)$ where:
- $Q$ is the set of workflow steps (e.g., `awaiting_date`, `ready_to_book`)
- $\Sigma$ is the set of intents recognized by $IntentNode$
- $\delta: Q \times \Sigma \rightarrow Q$ is the transition function (with cross-workflow reset as an exceptional transition)
- $q_0 = \text{idle}$ is the initial state
- $F = \{\text{idle}\}$ is the set of terminal states after workflow completion

### Cross-Workflow Conflict Resolution

A key contribution is the formal handling of **workflow conflicts**: when a new intent $i' \in \Sigma$ is detected while an incompatible workflow step $q \in Q$ is active. The system defines incompatibility sets $I_w \subseteq \Sigma$ for each workflow $w$. On conflict, the system executes:
$$\delta(q, i') = \text{RESET}(w) \circ \delta(\text{idle}, i')$$
where $\text{RESET}(w)$ atomically removes all state fields belonging to workflow $w$ from both the in-memory state and Redis.

---

## 4. Memory-Enhanced Conversational AI

### 4.1 The Memory Relevance Problem in Healthcare

Healthcare conversations present unique memory requirements that distinguish them from general-purpose assistants. A patient may:
- Disclose a chronic condition once but expect it to be remembered in all subsequent interactions
- Express a preference for a specific specialist and expect proactive suggestions
- Have a history of cancelled appointments that the system should sensitively acknowledge
- Switch languages between sessions while expecting semantic continuity

ClinixAI addresses this with a **multi-layered memory architecture** combining:
1. Redis for sub-millisecond session state retrieval
2. MongoDB for persistent structured patient profiles
3. MongoDB with dense vector embeddings for semantic long-term memory
4. Session-scoped conversation history for in-context reasoning

### 4.2 Semantic Memory Architecture

The semantic memory layer uses the `paraphrase-multilingual-MiniLM-L12-v2` sentence transformer to encode conversation-extracted facts into 384-dimensional dense vectors. At retrieval time, the cosine similarity between the current query embedding and stored memory embeddings determines relevance:

$$\text{sim}(q, m_i) = \frac{\mathbf{q} \cdot \mathbf{m}_i}{|\mathbf{q}| \cdot |\mathbf{m}_i|}$$

Top-$k$ memories with highest similarity are injected into the LLM context window as a personalization prefix, enabling the agent to respond with awareness of the patient's history without fine-tuning.

### 4.3 Memory-Driven Proactivity

The combination of semantic retrieval and proactive agent design enables a novel "rebooking detection" pattern: when a patient initiates a new session after a cancellation, the memory system surfaces the cancelled appointment, and the agent proactively offers to rebook — without the patient explicitly requesting this. This behavior emerges from the interaction between the retrieval system and the agent's response generation, not from hard-coded rules.

---

## 5. Grounded Medical AI

### 5.1 Hallucination and Grounding in Healthcare

In healthcare AI, hallucination (generating factually incorrect or fabricated information) carries heightened risks compared to general domains. An agent claiming a doctor is available when they are not, or inventing medical advice, could lead to suboptimal care decisions.

ClinixAI distinguishes two complementary concepts:

1. **Factual hallucination**: The agent invents specific facts (doctor names, addresses, appointment times) not derived from system data. Detected by the `hallucination_risk` judge dimension.

2. **Retrieval faithfulness (groundedness)**: Even without hallucination, an agent may fail to ground its responses in the retrieved context. For example, an agent that retrieves 5 nearby pharmacies but describes one not in the list. Measured by the `groundedness_score` dimension.

### 5.2 Anti-Hallucination Architecture

Several architectural decisions mitigate hallucination risk:
- **API-driven responses**: Doctor names, availability, and appointment times are retrieved from real APIs (availability_service, appointment_service) rather than generated by the LLM.
- **Template-based confirmations**: Booking confirmation responses are constructed from actual API response data, not LLM generation.
- **LLM limited to routing and generation**: The LLM in IntentNode classifies intent; actual domain logic is performed by ActionNode using deterministic API calls.
- **Temperature=0.0**: All LLM calls use temperature=0 to minimize creative (potentially hallucinatory) variation.

---

## 6. Evaluation Methodology

### 6.1 Justification for Hybrid Evaluation Framework

The evaluation of conversational AI agents in healthcare settings requires a hybrid approach combining:

**Classical NLP metrics** (ROUGE, BLEU, BERTScore): Provide reproducible, reference-free or reference-based quantitative scores that enable comparison with published literature benchmarks and longitudinal performance tracking.

**LLM-as-a-Judge**: Provides human-like qualitative assessment of dimensions that classical metrics cannot capture: safety, proactivity, workflow advancement, hallucination risk.

The ClinixAI evaluation framework operationalizes this hybrid approach through 9 NLP metrics + 9 LLM judge dimensions, combined into a single weighted overall score optimized for healthcare agentic behavior.

### 6.2 Evaluation Metric Design Principles

**Anti-reference bias**: Classical NLP metrics penalize responses that exceed the reference (e.g., a proactive agent that offers to book is scored lower by ROUGE than a passive agent that simply lists options). ClinixAI's judge prompts explicitly instruct the model that "reference responses are examples, not ceilings."

**Proactivity as quality**: The `conversational_quality` dimension is calibrated with few-shot examples that assign score ≥ 0.85 to proactive responses, regardless of verbosity or alignment with the reference. This calibration was introduced after empirical observation that prior prompt versions scored genuinely good proactive responses at 0.0.

**Safety primacy**: The `safety_score` dimension receives the highest weight (0.20) in the overall score, reflecting the non-negotiable nature of safety in healthcare AI.

**Weight distribution rationale**:

| Dimension | Weight | Rationale |
|---|---|---|
| Safety | 0.20 | Healthcare AI safety is non-negotiable |
| Workflow | 0.17 | Primary function: task completion |
| Hallucination | 0.14 | Factual accuracy critical in medicine |
| Conversational | 0.14 | Interaction quality affects adoption |
| Groundedness | 0.10 | Retrieval faithfulness for trust |
| Answer Correctness | 0.09 | Factual alignment with reference |
| Answer Relevancy | 0.09 | Response on-topic coverage |
| Memory Relevance | 0.04 | Memory-driven personalization |
| Context Precision | 0.02 | Retrieval quality indicator |
| Personalization | 0.01 | Supplementary personalization |

### 6.3 Observability Through Historical Analytics

The evaluation service's analytical dashboard enables longitudinal quality monitoring — a critical property for production AI systems. The unified timeline approach (merging MongoDB historical runs with in-session results) ensures that researchers and developers can observe quality trends across arbitrary time windows, detect regressions, and correlate changes in prompts or models with metric movements.

---

## 7. Multilingual Healthcare AI

### 7.1 Linguistic Context

The Tunisian healthcare system operates in a bilingual environment: medical education and formal documentation are predominantly French, while patient-physician interactions frequently occur in Tunisian Arabic (Darija) or Modern Standard Arabic. Digital healthcare interfaces must support this multilingual reality to be accessible.

ClinixAI's trilingual support (Arabic, French, English) with cross-language semantic memory represents a significant engineering contribution beyond existing healthcare chatbot systems, which typically operate monolingually.

### 7.2 Cross-Lingual Memory Retrieval

The choice of `paraphrase-multilingual-MiniLM-L12-v2` for memory embeddings enables a particularly powerful property: **cross-lingual semantic search**. A memory stored during a French-language session ("Patient préfère les rendez-vous le matin") is retrievable when the patient queries in Arabic ("أفضل المواعيد في الصباح") because the multilingual model maps semantically equivalent sentences in different languages to nearby embedding vectors.

This property enables continuous memory coherence across language switches, which is common in bilingual Tunisian contexts.

---

## 8. Workflow-Oriented Agent Design

### 8.1 Distinguishing Conversational AI from Workflow AI

Conventional conversational AI paradigms optimize for dialogue quality — naturalness, coherence, and informativeness. Healthcare AI requires an additional dimension: **workflow effectiveness** — the agent's ability to successfully advance a multi-step process (appointment booking, medication prescription renewal, emergency triage referral) toward completion.

ClinixAI's workflow_score evaluation dimension explicitly measures this: not whether the response was fluent or accurate in isolation, but whether it correctly transitioned the conversation toward task completion.

### 8.2 Stateful Workflow Management

The booking workflow in ClinixAI spans 4–7 conversational turns and requires the agent to:
1. Remember collected information across turns (doctor, date, time)
2. Detect when the user provides information out of sequence
3. Handle rejection (409 conflict on a booked slot) and gracefully recover
4. Reset stale context when the user pivots to a different task

This stateful management is implemented through the Redis session layer, the WorkflowNode DFA, and the cross-workflow reset mechanism. The result is an agent that behaves as a skilled administrative assistant rather than a simple question-answering system.

---

## 9. Healthcare Impact

### 9.1 Accessibility

ClinixAI directly addresses appointment booking friction. In Tunisia:
- Specialist appointments often require telephone contact during business hours
- Location-based doctor search relies on word-of-mouth or outdated directories
- Prescription renewals and appointment management require in-person or phone interaction

ClinixAI provides 24/7 conversational access to appointment scheduling, proximity-based specialist discovery across 24 governorates and 8 medical categories, and appointment management (cancellation, rescheduling) through a natural language interface.

### 9.2 Doctor Productivity

The physician-facing assistant reduces administrative overhead by providing instant answers to schedule queries ("How many patients do I have tomorrow?") and patient history access ("What was my last appointment with this patient about?") through natural language interaction.

---

## 10. Limitations and Future Work

### Current Limitations

1. **Real-time availability accuracy**: The availability system reflects the doctor's template schedule; real-time updates (emergencies, walk-in patients) are not automatically reflected without explicit slot blocking.

2. **Clinical decision support absent**: ClinixAI assists with access to care but does not provide clinical triage, symptom assessment, or medical advice. Expanding into clinical decision support would require careful safety validation and regulatory compliance.

3. **Voice interface**: The current system is text-only. For elderly or low-literacy populations, a voice interface would significantly improve accessibility.

4. **LLM hallucination residual risk**: Despite architectural mitigations, the LLM components (IntentNode for edge-case intent classification, ActionNode for idle-mode responses) retain residual hallucination risk. Continuous evaluation with the ClinixAI evaluation framework is required to monitor this.

5. **Evaluation ground truth**: The LLM judge's scores are calibrated approximations of quality, not ground truth human judgments. Correlation studies with human evaluators are needed to validate the judge's reliability.

### Future Work

1. **Clinical NLP integration**: Incorporating medical entity recognition (NER) and drug interaction checking for enhanced safety.

2. **Federated learning for memory privacy**: Patient memory embeddings contain sensitive health information. Federated or differential-privacy approaches could enable model personalization without centralized data.

3. **Appointment reminder system**: Automatic SMS/email reminders using the reminder preference memory extracted during conversations.

4. **Multi-modal medical records**: Enabling patients to share medical documents (lab reports, prescriptions) for the agent to reason about.

5. **CRISP-ML(Q) compliance**: Applying the CRISP-ML(Q) methodology for systematic machine learning quality assurance across the full ClinixAI development lifecycle — from requirements specification through deployment monitoring.

6. **Continual evaluation loop**: Closing the evaluation loop by automatically running evaluation scenarios after every deployment, with automatic regression detection and alert escalation.

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Brain,
  Clock,
  Database,
  Globe2,
  Play,
  RefreshCw,
  Shield,
  Workflow,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import EvaluationHistory from "@/components/eval/EvaluationHistory";
import RadarEvaluation from "@/components/eval/RadarEvaluation";
import {
  fetchFrameworkResults,
  fetchHistory,
  fetchResult,
  fetchScenarios,
  runScenario,
} from "@/lib/evalApi";
import type { EvalResult, EvalScenario, EvalSummary, FrameworkMetrics } from "@/types/eval";

type Tab = "overview" | "workflow" | "agent" | "memory" | "llm" | "multilingual" | "performance";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "workflow", label: "Workflow" },
  { id: "agent", label: "Agent" },
  { id: "memory", label: "Memory" },
  { id: "llm", label: "LLM Judge" },
  { id: "multilingual", label: "Multilingual" },
  { id: "performance", label: "Performance" },
];

const fmtPct = (value?: number | null) => value == null ? "-" : `${value.toFixed(1)}%`;
const fmt5 = (value?: number | null) => value == null ? "-" : `${value.toFixed(1)} / 5`;
const fmtMs = (value?: number | null) => value == null ? "-" : `${Math.round(value)}ms`;

function Card({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase text-slate-500">{label}</p>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <p className="mt-3 text-2xl font-bold text-slate-900 tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold uppercase text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

function SimpleTable({ rows, columns }: { rows: Record<string, any>[]; columns: string[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            {columns.map(col => (
              <th key={col} className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                {col.replaceAll("_", " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length ? rows.map((row, index) => (
            <tr key={index}>
              {columns.map(col => (
                <td key={col} className="px-4 py-3 text-slate-700">
                  {typeof row[col] === "number" ? row[col].toFixed(row[col] % 1 ? 1 : 0) : row[col] ?? "-"}
                </td>
              ))}
            </tr>
          )) : (
            <tr>
              <td className="px-4 py-6 text-sm text-slate-400" colSpan={columns.length}>
                No evaluation data available.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function MetricBars({ data }: { data: Array<{ name: string; value: number; color?: string }> }) {
  return (
    <div className="h-72 rounded-lg border border-slate-200 bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#64748b" }} />
          <Tooltip formatter={(value: unknown) => [`${Number(value || 0).toFixed(1)}%`, "Score"]} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {data.map((item, index) => <Cell key={index} fill={item.color || "#2563eb"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [scenarios, setScenarios] = useState<EvalScenario[]>([]);
  const [history, setHistory] = useState<EvalSummary[]>([]);
  const [framework, setFramework] = useState<FrameworkMetrics>({});
  const [activeResult, setActiveResult] = useState<EvalResult | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [scenarioRows, historyRows, frameworkRows] = await Promise.all([
        fetchScenarios(),
        fetchHistory(100).catch(() => []),
        fetchFrameworkResults(200).catch(() => ({})),
      ]);
      setScenarios(scenarioRows);
      setHistory(historyRows);
      setFramework(frameworkRows);
      if (historyRows[0]?.id) {
        setActiveResult(await fetchResult(historyRows[0].id));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleRunScenario(id: string) {
    setRunning(id);
    try {
      const result = await runScenario(id);
      setActiveResult(result);
      await refresh();
      setTab("overview");
    } finally {
      setRunning(null);
    }
  }

  async function handleSelectHistory(id: string) {
    setActiveResult(await fetchResult(id));
    setTab("overview");
  }

  const workflow = framework.workflow_metrics || activeResult?.workflow_metrics || {};
  const intent = framework.intent_metrics || activeResult?.intent_metrics || {};
  const memory = framework.memory_metrics || activeResult?.memory_metrics || {};
  const llm = framework.llm_judge_metrics || activeResult?.llm_judge_metrics || {};
  const multilingual = framework.multilingual_metrics || activeResult?.multilingual_metrics || {};
  const performance = framework.performance_metrics || activeResult?.performance_metrics || {};
  const responseTime = (performance.response_time?.overall || performance) as {
    average_latency_ms?: number;
    p95_latency_ms?: number;
    max_latency_ms?: number;
  };

  const workflowRows = useMemo(() => {
    const rows = workflow.per_workflow || {};
    return Object.entries(rows).map(([name, row]: any) => ({
      workflow: name.replaceAll("_", " "),
      total_tasks: row.total_tasks || 0,
      task_success_rate: row.task_success_rate || 0,
      completion_rate: row.completion_rate || 0,
      state_transition_accuracy: row.state_transition_accuracy || 0,
    }));
  }, [workflow]);

  const llmBarData = [
    { name: "Completeness", value: ((llm.completeness || 0) / 5) * 100, color: "#2563eb" },
    { name: "Accuracy", value: ((llm.accuracy || 0) / 5) * 100, color: "#0891b2" },
    { name: "Faithfulness", value: ((llm.faithfulness || 0) / 5) * 100, color: "#059669" },
    { name: "Safety", value: ((llm.safety_score || 0) / 5) * 100, color: "#16a34a" },
    { name: "Utility", value: ((llm.clinical_utility || 0) / 5) * 100, color: "#7c3aed" },
    { name: "Conversation", value: ((llm.conversation_quality || 0) / 5) * 100, color: "#d97706" },
  ];

  const scenarioGroups = useMemo(() => {
    const preferred = ["workflow", "preconsultation", "memory", "multilingual", "safety", "recommendation"];
    return scenarios.filter(s => preferred.includes(s.category)).slice(0, 12);
  }, [scenarios]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-blue-700">ClinixAI Evaluation</p>
            <h1 className="mt-1 text-2xl font-bold">Evaluation Dashboard</h1>
            <p className="mt-1 text-sm text-slate-500">
              Thesis framework: workflow, agent intelligence, memory, LLM judge, multilingual, and performance evaluation.
            </p>
          </div>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 shadow-sm hover:bg-slate-50"
          >
            <RefreshCw size={15} /> Refresh
          </button>
        </header>

        <div className="flex flex-wrap gap-2">
          {TABS.map(item => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${
                tab === item.id ? "bg-blue-600 text-white" : "bg-white text-slate-600 border border-slate-200"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="rounded-lg border border-slate-200 bg-white p-8 text-sm text-slate-500">Loading evaluation data...</div>
        ) : (
          <>
            {tab === "overview" && (
              <div className="flex flex-col gap-6">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
                  <Card label="TSR" value={fmtPct(workflow.overall_task_success_rate)} icon={<Workflow size={18} />} />
                  <Card label="Completion" value={fmtPct(workflow.overall_completion_rate)} icon={<Activity size={18} />} />
                  <Card label="Faithfulness" value={fmt5(llm.faithfulness)} icon={<Shield size={18} />} />
                  <Card label="Safety Score" value={fmt5(llm.safety_score)} icon={<Shield size={18} />} />
                  <Card label="Clinical Utility" value={fmt5(llm.clinical_utility)} icon={<Brain size={18} />} />
                  <Card label="Average Latency" value={fmtMs(responseTime.average_latency_ms ?? performance.average_latency_ms)} icon={<Clock size={18} />} />
                </div>

                <Section title="Run Existing Scenarios">
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {scenarioGroups.map(scenario => (
                      <button
                        key={scenario.id}
                        onClick={() => handleRunScenario(scenario.id)}
                        disabled={!!running}
                        className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-blue-300 disabled:opacity-50"
                      >
                        <Play size={16} className="mt-1 text-blue-600" />
                        <span>
                          <span className="block text-sm font-semibold text-slate-800">{scenario.id} - {scenario.name}</span>
                          <span className="mt-1 block text-xs text-slate-500">{running === scenario.id ? "Running..." : scenario.description}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </Section>

                <Section title="Evaluation History">
                  <EvaluationHistory rows={history} onSelect={handleSelectHistory} onDeleted={id => setHistory(rows => rows.filter(row => row.id !== id))} />
                </Section>
              </div>
            )}

            {tab === "workflow" && (
              <Section title="Workflow Evaluation">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <Card label="Overall TSR" value={fmtPct(workflow.overall_task_success_rate)} />
                  <Card label="Completion Rate" value={fmtPct(workflow.overall_completion_rate)} />
                  <Card label="State Transition Accuracy" value={fmtPct(workflow.overall_state_transition_accuracy)} />
                </div>
                <SimpleTable rows={workflowRows} columns={["workflow", "total_tasks", "task_success_rate", "completion_rate", "state_transition_accuracy"]} />
              </Section>
            )}

            {tab === "agent" && (
              <Section title="Agent Intelligence Evaluation">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                  <Card label="Intent Accuracy" value={fmtPct(intent.intent_classification?.accuracy)} />
                  <Card label="Precision" value={fmtPct(intent.intent_classification?.precision)} />
                  <Card label="Recall" value={fmtPct(intent.intent_classification?.recall)} />
                  <Card label="F1 Score" value={fmtPct(intent.intent_classification?.f1)} />
                </div>
                <SimpleTable
                  rows={Object.entries(intent.intent_classification?.confusion_matrix || {}).map(([actual, values]) => ({
                    actual,
                    ...(values as Record<string, number>),
                  }))}
                  columns={["actual", "doctor_search", "booking", "cancellation", "report_request", "availability_check", "profile_update"]}
                />
                <SimpleTable
                  rows={Object.entries(intent.specialty_recommendation?.per_specialty || {}).map(([specialty, row]) => ({
                    specialty,
                    ...(row as Record<string, number>),
                  }))}
                  columns={["specialty", "correct_recommendations", "total_recommendations", "accuracy"]}
                />
              </Section>
            )}

            {tab === "memory" && (
              <Section title="Memory Evaluation">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Card label="Memory Retrieval Accuracy" value={fmtPct(memory.retrieval_accuracy)} icon={<Database size={18} />} />
                  <Card label="Memory Groundedness" value={fmt5(memory.average_groundedness)} icon={<Database size={18} />} />
                </div>
                <SimpleTable
                  rows={Object.entries(memory.systems || {}).map(([system, row]) => ({
                    system,
                    ...(row as Record<string, number>),
                  }))}
                  columns={["system", "correct_retrievals", "total_retrievals", "retrieval_accuracy", "average_groundedness"]}
                />
                <MetricBars
                  data={Object.entries(memory.groundedness_distribution || {}).map(([bucket, count]) => ({
                    name: bucket,
                    value: Number(count),
                    color: "#0891b2",
                  }))}
                />
              </Section>
            )}

            {tab === "llm" && (
              <Section title="LLM-As-Judge Evaluation">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                  <Card label="Completeness" value={fmt5(llm.completeness)} />
                  <Card label="Accuracy" value={fmt5(llm.accuracy)} />
                  <Card label="Faithfulness" value={fmt5(llm.faithfulness)} />
                  <Card label="Hallucination Rate" value={fmtPct(llm.hallucination_rate)} />
                  <Card label="Safety Score" value={fmt5(llm.safety_score)} />
                  <Card label="Clinical Utility" value={fmt5(llm.clinical_utility)} />
                  <Card label="Conversation Quality" value={fmt5(llm.conversation_quality)} />
                </div>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div className="rounded-lg border border-slate-200 bg-white p-4">
                    {activeResult ? <RadarEvaluation result={activeResult} height={300} /> : <p className="text-sm text-slate-400">No result selected.</p>}
                  </div>
                  <MetricBars data={llmBarData} />
                </div>
              </Section>
            )}

            {tab === "multilingual" && (
              <Section title="Multilingual Evaluation">
                <Card label="Multilingual Success Rate" value={fmtPct(multilingual.overall_success_rate)} icon={<Globe2 size={18} />} />
                <SimpleTable rows={multilingual.languages || []} columns={["language", "executions", "success_rate", "average_completeness", "average_faithfulness", "average_safety"]} />
              </Section>
            )}

            {tab === "performance" && (
              <Section title="Performance Evaluation">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <Card label="Average Response Time" value={fmtMs(responseTime.average_latency_ms ?? performance.average_latency_ms)} />
                  <Card label="P95 Latency" value={fmtMs(responseTime.p95_latency_ms)} />
                  <Card label="Max Latency" value={fmtMs(responseTime.max_latency_ms)} />
                </div>
                <SimpleTable
                  rows={Object.entries(performance.response_time?.stages || {}).map(([stage, row]) => ({
                    stage: stage.replaceAll("_", " "),
                    ...(row as Record<string, number>),
                  }))}
                  columns={["stage", "average_latency_ms", "p95_latency_ms", "max_latency_ms"]}
                />
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <SimpleTable rows={[performance.token_consumption || {}]} columns={["average_prompt_tokens", "average_completion_tokens", "average_total_tokens", "total_tokens_consumed", "average_cost_per_conversation"]} />
                  <SimpleTable rows={[performance.llm_generation_statistics || {}]} columns={["average_generation_time_ms", "average_tokens_per_second", "longest_generation_ms", "shortest_generation_ms"]} />
                </div>
              </Section>
            )}
          </>
        )}
      </div>
    </main>
  );
}

export interface JudgeDimension {
  score: number;
  explanation: string;
  confidence?: number;
}

export interface WorkflowMetricRow {
  successful_tasks: number;
  total_tasks: number;
  task_success_rate: number;
  completed_workflows: number;
  started_workflows: number;
  completion_rate: number;
  correct_transitions: number;
  total_transitions: number;
  state_transition_accuracy: number;
}

export interface FrameworkMetrics {
  workflow_metrics?: {
    overall_task_success_rate?: number;
    overall_completion_rate?: number;
    overall_state_transition_accuracy?: number;
    per_workflow?: Record<string, WorkflowMetricRow>;
  };
  intent_metrics?: {
    intent_classification?: {
      accuracy?: number;
      precision?: number;
      recall?: number;
      f1?: number;
      classes?: string[];
      confusion_matrix?: Record<string, Record<string, number>>;
      per_class?: Record<string, { precision: number; recall: number; f1: number }>;
    };
    specialty_recommendation?: {
      overall_accuracy?: number;
      per_specialty?: Record<string, {
        correct_recommendations: number;
        total_recommendations: number;
        accuracy: number;
      }>;
    };
  };
  memory_metrics?: {
    retrieval_accuracy?: number;
    correct_retrievals?: number;
    total_retrievals?: number;
    average_groundedness?: number;
    groundedness_distribution?: Record<string, number>;
    systems?: Record<string, {
      correct_retrievals: number;
      total_retrievals: number;
      retrieval_accuracy: number;
      average_groundedness: number;
    }>;
  };
  llm_judge_metrics?: Record<string, number>;
  multilingual_metrics?: {
    languages?: Array<Record<string, any>>;
    overall_success_rate?: number;
  };
  performance_metrics?: {
    average_latency_ms?: number;
    response_time?: {
      overall?: {
        average_latency_ms?: number;
        p95_latency_ms?: number;
        max_latency_ms?: number;
      };
      stages?: Record<string, {
        average_latency_ms: number;
        p95_latency_ms: number;
        max_latency_ms: number;
      }>;
    };
    token_consumption?: Record<string, number>;
    llm_generation_statistics?: Record<string, number>;
  };
}

export interface EvalResult extends FrameworkMetrics {
  id?: string;
  scenario_id?: string;
  hallucination_risk?: number;
  groundedness_score?: number;
  safety_score?: number;
  workflow_score?: number;
  workflow_success_rate?: number;
  conversational_quality?: number;
  multilingual_consistency?: number;
  dimensions: Record<string, JudgeDimension>;
  overall_score?: number;
  judge_explanation: string;
  latency_ms?: number;
  evaluated_at: string;
  model_used: string;
  user_message?: string;
  agent_response?: string;
  reference_response?: string;
  language: string;
  role: string;
  tags: string[];
}

export interface EvalSummary {
  id: string;
  scenario_id?: string;
  overall_score?: number;
  safety_score?: number;
  hallucination_risk?: number;
  workflow_success_rate?: number;
  task_success_rate?: number;
  workflow_completion_rate?: number;
  faithfulness?: number;
  clinical_utility?: number;
  latency_ms?: number;
  evaluated_at: string;
  model_used: string;
  language: string;
  role: string;
}

export interface TrendPoint {
  evaluated_at: string;
  overall_score?: number;
  safety_score?: number;
  hallucination_risk?: number;
  groundedness_score?: number;
  workflow_success_rate?: number;
  task_success_rate?: number;
  workflow_completion_rate?: number;
  faithfulness?: number;
  clinical_utility?: number;
  latency_ms?: number;
  scenario_id?: string;
}

export interface TrendResponse {
  points: TrendPoint[];
  averages: Record<string, number>;
  best_run?: EvalSummary;
  worst_run?: EvalSummary;
}

export interface CompareResult {
  run_a: EvalResult;
  run_b: EvalResult;
  delta: Record<string, number | null>;
}

export interface EvalScenario {
  id: string;
  name: string;
  description: string;
  category: string;
  language: string;
  role: string;
  user_message: string;
  expected_workflow?: string;
  expected_tool?: string;
  reference_response?: string;
  context?: string;
  tags: string[];
}

export type ScoreColor = "emerald" | "amber" | "rose" | "slate";

export function scoreColor(score?: number | null): ScoreColor {
  if (score == null) return "slate";
  const normalized = score > 5 ? score / 100 : score > 1 ? score / 5 : score;
  if (normalized >= 0.75) return "emerald";
  if (normalized >= 0.50) return "amber";
  return "rose";
}

export const SCORE_COLORS: Record<ScoreColor, string> = {
  emerald: "#059669",
  amber: "#d97706",
  rose: "#e11d48",
  slate: "#64748b",
};

export const METRIC_LABELS: Record<string, string> = {
  overall_score: "Overall Score",
  safety_score: "Safety Score",
  hallucination_risk: "Hallucination Risk",
  groundedness_score: "Groundedness",
  workflow_success_rate: "Workflow Success Rate",
  task_success_rate: "Task Success Rate",
  workflow_completion_rate: "Workflow Completion Rate",
  faithfulness: "Faithfulness",
  clinical_utility: "Clinical Utility",
  latency_ms: "Latency",
};

export const CATEGORY_LABELS: Record<string, string> = {
  workflow: "Workflow",
  preconsultation: "Preconsultation",
  memory: "Memory",
  safety: "Safety",
  hallucination: "Hallucination",
  multilingual: "Multilingual",
  recommendation: "Recommendation",
  doctor: "Doctor",
  voice: "Voice",
};

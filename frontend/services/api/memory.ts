export interface UserMemory {
  key: string;
  value: string | Record<string, unknown>;
  memory_type: "profile" | "episodic" | "workflow";
  confidence: number;
  frequency: number;
  updated_at: string;
  retrieval_meta?: {
    source: "semantic_match" | "structured";
    similarity: number;
    matched_topic: string;
    hybrid_score: number;
  };
}

export interface DoctorRecommendation {
  doctor_id: string;
  doctor_name: string;
  specialty: string;
  score: number;
  visit_count: number;
  reason: string;
}

export interface PendingWorkflow {
  workflow_type: string;
  step: string;
  state: Record<string, unknown>;
  context: Record<string, unknown>;
  created_at: string;
}

export interface UserMemoryResponse {
  user_id: string;
  memories: UserMemory[];
  semantic_memories: UserMemory[];
  recommendations: DoctorRecommendation[];
  pending_workflow: PendingWorkflow | null;
}

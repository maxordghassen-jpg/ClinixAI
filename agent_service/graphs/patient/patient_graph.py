from langgraph.graph import StateGraph

from graphs.shared.schemas import AgentState
from graphs.patient.nodes.memory_node import MemoryNode
from graphs.shared.nodes.intent_node import IntentNode
from graphs.patient.nodes.workflow_node import WorkflowNode
from graphs.patient.nodes.action_node import ActionNode
from graphs.patient.nodes.state_writer_node import StateWriterNode


def build_patient_graph():
    """
    Patient conversation graph.

    Turn-level execution order:
      memory  → load Redis state into state.memory (read-only from Redis)
      intent  → LLM extracts intent + entities, updates state.memory
      workflow→ determines the correct step transition, updates state.memory
      action  → executes the step logic, updates state.memory
      writer  → flushes the final state.memory to Redis (single write per turn)

    Every node upstream of StateWriterNode may freely mutate state.memory.
    None of them write to Redis directly (ActionNode keeps one explicit
    checkpoint for doctor_results — see its docstring for the reasoning).
    """

    graph = StateGraph(AgentState)

    graph.add_node("memory", MemoryNode().run)
    graph.add_node("intent", IntentNode().run)
    graph.add_node("workflow", WorkflowNode().run)
    graph.add_node("action", ActionNode().run)
    graph.add_node("writer", StateWriterNode().run)

    graph.set_entry_point("memory")

    graph.add_edge("memory", "intent")
    graph.add_edge("intent", "workflow")
    graph.add_edge("workflow", "action")
    graph.add_edge("action", "writer")

    return graph.compile()

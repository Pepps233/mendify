from __future__ import annotations

from langgraph.graph import END, StateGraph

from mendify.nodes import (
    apply_patch,
    commit,
    diagnose,
    fetch_logs,
    report_failure,
    validate,
)
from mendify.state import AgentState


def route_after_validation(state: AgentState) -> str:
    """Decide next step after validate node runs."""
    result = state.get("validation_result", "fail")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if result == "pass":
        return "commit"
    if iteration < max_iterations:
        return "diagnose"
    return "report_failure"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("fetch_logs", fetch_logs)
    graph.add_node("diagnose", diagnose)
    graph.add_node("apply_patch", apply_patch)
    graph.add_node("validate", validate)
    graph.add_node("commit", commit)
    graph.add_node("report_failure", report_failure)

    # Linear path
    graph.set_entry_point("fetch_logs")
    graph.add_edge("fetch_logs", "diagnose")
    graph.add_edge("diagnose", "apply_patch")
    graph.add_edge("apply_patch", "validate")

    # Conditional routing after validate
    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "commit": "commit",
            "diagnose": "diagnose",
            "report_failure": "report_failure",
        },
    )

    graph.add_edge("commit", END)
    graph.add_edge("report_failure", END)

    return graph.compile()


graph = build_graph()

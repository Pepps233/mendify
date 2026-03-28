
from mendify.agent import route_after_validation


def test_route_pass():
    state = {"validation_result": "pass", "iteration": 0, "max_iterations": 3}
    assert route_after_validation(state) == "commit"


def test_route_fail_with_retries():
    state = {"validation_result": "fail", "iteration": 1, "max_iterations": 3}
    assert route_after_validation(state) == "diagnose"


def test_route_fail_max_retries():
    state = {"validation_result": "fail", "iteration": 3, "max_iterations": 3}
    assert route_after_validation(state) == "report_failure"


def test_route_defaults():
    # No validation_result — treat as fail, iteration 0, max 3
    state = {}
    assert route_after_validation(state) == "diagnose"


def test_graph_compiles():
    from mendify.agent import graph
    assert graph is not None


def test_graph_structure():
    from mendify.agent import graph
    g = graph.get_graph()
    node_names = {n for n in g.nodes}
    assert "fetch_logs" in node_names
    assert "diagnose" in node_names
    assert "apply_patch" in node_names
    assert "validate" in node_names
    assert "commit" in node_names
    assert "report_failure" in node_names

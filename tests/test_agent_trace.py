import json

from server.utils import agent_trace


def test_trace_persists_operational_metadata_without_prompt(tmp_path, monkeypatch):
    trace_file = tmp_path / "agent_trace.jsonl"
    monkeypatch.setattr(agent_trace, "_TRACE_DIR", tmp_path)
    monkeypatch.setattr(agent_trace, "_TRACE_FILE", trace_file)

    trace = agent_trace.AgentTrace("interview.score", model="demo", input_chars=120)
    trace.event("retrieval", latency_ms=12.5, reference_found=True)
    trace.finish(score=86)

    records = agent_trace.read_recent_traces(10)
    assert len(records) == 1
    assert records[0]["component"] == "interview.score"
    assert records[0]["metadata"]["input_chars"] == 120
    assert records[0]["events"][0]["type"] == "retrieval"
    assert "prompt" not in json.dumps(records[0], ensure_ascii=False).lower()

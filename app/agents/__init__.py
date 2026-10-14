"""Agent workflow for the Explain stage (P2): Analyst, Narrator, Guard, Verifier on Microsoft Agent Framework.

An offline step: the CLI (`python -m app.agents.run`) runs it and the publication store keeps the result and
its trace; the live service only replays what was stored. Nothing in `app/api`, `app/publish` or `app/serve.py`
imports this package (tests/test_no_agents_in_service.py).
"""

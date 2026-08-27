"""Legacy code and dead-end diagnostics (kept for reference, not used by the agent).

- The daily-briefing pipeline (llm_service, providers/, audit_engine, ...) was
  the original learning exercise: it uses fake data and a simple
  generate_summary() interface, NOT the tool-calling Agent in ai_briefing.core.
- fabric_client.py and xmla_client.py are diagnostics that turned out to be dead
  ends (the workspace has no Fabric/Premium capacity). They still run but aren't
  wired into anything.
"""

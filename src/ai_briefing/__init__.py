"""AI Briefing — live Q&A assistant for the truck-leasing business.

Layout:
    core/     — generic, reusable agent framework (no leasing knowledge)
    domain/   — this case: Bitrix24 + Power BI clients, tools, data guide,
                glossary, and the leasing system prompt
    legacy/   — the old mock pipeline and dead-end diagnostics (not wired in)
    cli.py    — terminal entry point: wires domain tools into the core agent
    server.py — HTTP entry point (same wiring, served over FastAPI)

To tweak behaviour, look at domain/config.py (system prompt),
domain/powerbi/data_guide.py (table semantics), and domain/glossary.md
(business abbreviations).
"""

__version__ = "0.1.0"

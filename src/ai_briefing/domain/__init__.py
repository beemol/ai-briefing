"""Leasing-specific domain: Bitrix24 CRM + Power BI integrations.

Everything here is specific to the truck-leasing use case:
- bitrix/   — CRM client + tools
- powerbi/  — analytics client + tools + data guide + schema
- config.py — the system prompt that ties it together
- glossary.md — business abbreviations (to be filled by the CEO)
"""

from ai_briefing.domain.config import LEASING_SYSTEM_PROMPT

__all__ = ["LEASING_SYSTEM_PROMPT"]

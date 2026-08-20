import os

from dotenv import load_dotenv

from ai_briefing.audit_engine import ExecutiveAuditEngine
from ai_briefing.providers.factory import get_llm_service

_=load_dotenv()

# --- CONFIGURATION SWITCH ---
SELECTED_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")

if __name__ == "__main__":
    llm_service = get_llm_service()
    engine = ExecutiveAuditEngine(llm_client=llm_service)
    mock_data = '{"tickets_overdue": 3, "spend": 4200}'
    result = engine.run_daily_briefing(mock_data)
    
    print(f"[{SELECTED_PROVIDER.upper()} RESPONSE]:\n{result}"
)
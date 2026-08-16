
import os
from dotenv import load_dotenv

from audit_engine import ExecutiveAuditEngine
from providers.deepseek_client import DeepSeekService
#from providers.gemini_client import GeminiService

load_dotenv()

# --- CONFIGURATION SWITCH ---
SELECTED_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek") # "deepseek" or "gemini"

def get_llm_service():
    if SELECTED_PROVIDER == "deepseek":
        return DeepSeekService(api_key=os.getenv("DEEPSEEK_API_KEY"))
    #elif SELECTED_PROVIDER == "gemini":
    #    return GeminiService(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        raise ValueError(f"Unknown provider: {SELECTED_PROVIDER}")

if __name__ == "__main__":
    # 1. Instantiate concrete service
    llm_service = get_llm_service()
    
    # 2. Inject into core engine
    engine = ExecutiveAuditEngine(llm_client=llm_service)
    
    # 3. Execute
    mock_data = '{"tickets_overdue": 3, "spend": 4200}'
    result = engine.run_daily_briefing(mock_data)
    
    print(f"[{SELECTED_PROVIDER.upper()} RESPONSE]:\n{result}")
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from ai_briefing.agent import Agent
from ai_briefing.bitrix import BitrixClient, BitrixTools
from ai_briefing.powerbi import PowerBIClient, PowerBITools, get_access_token

_ = load_dotenv()

def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    webhook = os.getenv("BITRIX_WEBHOOK")
    if not api_key or not webhook:
        raise SystemExit("Missing required env vars: ANTHROPIC_API_KEY, BITRIX_WEBHOOK")

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit("Usage: venv/bin/python chat_cli.py 'your question'")

    # 1. Initialize API Clients
    claude = Anthropic(api_key=api_key)
    bitrix_client = BitrixClient(webhook)
    powerbi_client = PowerBIClient(get_access_token())

    # 2. Initialize Toolkits
    toolkits = [
        BitrixTools(bitrix_client),
        PowerBITools(powerbi_client),
    ]

    # 3. Initialize Agent
    agent = Agent(claude, toolkits)

    # 4. Run
    print(agent.ask(question))

if __name__ == "__main__":
    main()

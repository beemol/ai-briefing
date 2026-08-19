import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from agent import Agent
from bitrix_client import BitrixClient
from bitrix_tools import BitrixTools
from powerbi_auth import get_access_token
from powerbi_client import PowerBIClient
from powerbi_tools import PowerBITools

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

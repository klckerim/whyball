"""Foundry connection test: makes one short call and prints the answer.

Mirrors Microsoft's official sample; the only difference is that the endpoint and model come from .env:
https://github.com/microsoft/agent-framework/blob/main/python/samples/01-get-started/01_hello_agent.py
https://learn.microsoft.com/agent-framework/integrations/by-component/model-providers/microsoft-foundry

Run:
    az login
    .venv/bin/pip install -e ".[llm]"
    .venv/bin/python -m app.llm.hello
"""

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv


async def main() -> None:
    load_dotenv()
    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=AzureCliCredential(),
        ),
        instructions="You are a friendly assistant. Keep your answers brief.",
    )

    print(await agent.run("What is the largest city of France?"))


if __name__ == "__main__":
    asyncio.run(main())

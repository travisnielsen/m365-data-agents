import os
from os import environ, path
from dotenv import load_dotenv
from typing import Optional
import logging

# Use Agent Framework SDK for core functionality and telemetry
from agent_framework import ChatAgent, get_logger
from agent_framework.microsoft import CopilotStudioAgent

# Use existing microsoft_agents packages for Teams/M365 integration
from microsoft_agents.hosting.core import (
    TurnState,
    MemoryStorage,
    AgentApplication,
    Authorization,
)
from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.activity import load_configuration_from_env

from azure.ai.projects import AIProjectClient

from azure.ai.agents.models import (
    AsyncToolSet,
    AsyncFunctionTool, 
    RequiredFunctionToolCall,
    SubmitToolOutputsAction,
    ToolOutput,
    CodeInterpreterTool,
)

from azure.identity import ClientSecretCredential, DefaultAzureCredential

import agent_tools as tools

# Module-level state (kept internal to this module)
project_client: Optional[AIProjectClient] = None
invalid_foundry_connection: bool = False

# this is the workspace id for the Genie connection
# it is passed to the ask_genie function tool
genie_workspaceid: Optional[str] = None

# Load environment variables from .env located next to this module
load_dotenv(path.join(path.dirname(__file__), ".env"))

# Logging setup (keeps parity with previous app.py behavior)
ms_agents_logger = logging.getLogger("microsoft_agents")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"))
if not ms_agents_logger.handlers:
    ms_agents_logger.addHandler(console_handler)

loglevel = os.getenv("LOG_LEVEL", "WARNING").upper()
if loglevel == "DEBUG":
    ms_agents_logger.setLevel(logging.DEBUG)
elif loglevel == "INFO":
    ms_agents_logger.setLevel(logging.INFO)
elif loglevel == "ERROR":
    ms_agents_logger.setLevel(logging.ERROR)
else:
    ms_agents_logger.setLevel(logging.WARNING)

# Set up Agent Framework SDK logging and tracing
logger = get_logger("agent_framework.m365_data_agents")

# Import and setup tracing
try:
    from tracing_config import setup_agent_tracing
    setup_agent_tracing()
    logger.info("Starting agent with Agent Framework SDK integration and OpenTelemetry tracing")
except ImportError:
    logger.warning("Tracing configuration not available")
    logger.info("Starting agent with Agent Framework SDK integration")

# Load agent SDK configuration from environment (same behavior as original app)
agents_sdk_config = load_configuration_from_env(environ)

# Storage and connection manager
STORAGE = MemoryStorage()
CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)
AUTHORIZATION = Authorization(STORAGE, CONNECTION_MANAGER, **agents_sdk_config)

# Create AgentApplication and export it
AGENT_APP = AgentApplication[TurnState](
    storage=STORAGE,
    adapter=ADAPTER,
    authorization=AUTHORIZATION,
    **agents_sdk_config,
)

# Environment variables used across modules
FOUNDRY_URL = os.getenv("FOUNDRY_URL", "")
ADB_CONNECTION_NAME = os.getenv("ADB_CONNECTION_NAME", "")

STORAGE_ACCTNAME = os.getenv("STORAGE_ACCTNAME", "")
STORAGE_CONTNAME = os.getenv("STORAGE_CONTNAME", "")

# Create images directory if it doesn't exist
IMAGES_DIR = os.path.join(os.getcwd(), "images")
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

cred = ClientSecretCredential(
            tenant_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"),
            client_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"),
            client_secret=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"),
        )

project_client = AIProjectClient(FOUNDRY_URL, cred)

# get the workspace id at startup
connection = project_client.connections.get(ADB_CONNECTION_NAME)
if connection.metadata.get("azure_databricks_connection_type") == "genie":
    genie_workspaceid = connection.metadata.get("genie_space_id")
else:
    genie_workspaceid = None

if genie_workspaceid is None:
    invalid_foundry_connection = True
    raise RuntimeError("Genie space id not found in Foundry connection metadata.")

# Wrap the agent function-calling flow: create agent, run, execute any required tools
async def process_message(question: str, conversation_id: str = None) -> tuple[str, Optional[str]]:
    """
    Create and run an agent via Foundry's agent APIs, execute function tool calls (genie),
    and return textual response and optional saved image filename.
    """
    global project_client

    custom_functions = AsyncFunctionTool({tools.ask_genie})
    toolset = AsyncToolSet()
    toolset.add(custom_functions)
    toolset.add(CodeInterpreterTool())

    response = ""
    file_name = None

    agent_client = project_client.agents

    agent = agent_client.create_agent(
        name="my-assistant",
        model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        instructions=(
            """
            Your are an agent that responds to user questions related to Sales and pipeline just in Americas and by segment, sales of global customers, opportunity size, revenue by customers and customer churn. 
            For all questions you must solely rely on the function ask_genie and rely on the following instructions. 
            1. Instructions to use the ask_genie function
                - You must use the same prompt as the user question and never change the user's prompt.
                - Use the previous conversation_id if it's available.
                - Pass the value of genie_workspaceid from the agent_provider module.
                - You must use the code interpreter tool for any vizualation related questiins or prompts.
                - You must get the tabular data from the ask_genie function and render it via the markdown format before presenting the analysis of the data. 
                - Please use the markdown format to display tabular data before rendering any visualization via the code interpreter tool.
            2. Instructions on the visualization and code interpretation
                - Test and display visualization code using the code interpreter, retrying if errors occur.
                - Always use charts or graphs to illustrate trends when requested.
                - Always create visualizations as `.png` files.
                - Adapt visualizations (e.g., labels) to the user's language preferences.
                - When asked to download data, default to a `.csv` format file and use the most recent data.
                - Do not ever render the code or include file download links in the response.
            """
        ),
        toolset=toolset,
    )

    thread = agent_client.threads.create()
    message = agent_client.messages.create(thread_id=thread.id, role="user", content=question)

    run = agent_client.runs.create(thread_id=thread.id, agent_id=agent.id)

    # Poll for progress and handle required actions
    while run.status in ["queued", "in_progress", "requires_action"]:
        run = agent_client.runs.get(thread_id=thread.id, run_id=run.id)

        if run.status == "requires_action" and isinstance(run.required_action, SubmitToolOutputsAction):
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            if not tool_calls:
                agent_client.runs.cancel(thread_id=thread.id, run_id=run.id)
                break

            tool_outputs = []
            for tool_call in tool_calls:
                if isinstance(tool_call, RequiredFunctionToolCall):
                    try:
                        output = await custom_functions.execute(tool_call)
                        tool_outputs.append(
                            ToolOutput(tool_call_id=tool_call.id, output=output)
                        )
                    except Exception as e:
                        ms_agents_logger.error(f"Error executing tool_call {tool_call.id}: {e}")

            if tool_outputs:
                agent_client.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs)

    messages = agent_client.messages.list(thread_id=thread.id, run_id=run.id)

    latest_message = None
    for msg in messages:
        latest_message = msg
        break

    if latest_message and latest_message.content:
        for content_item in latest_message.content:
            if content_item.type == "text":
                response = content_item.text.value
            elif content_item.type == "image_file":
                file_id = content_item.image_file.file_id
                file_name = f"{file_id}_image_file.png"
                agent_client.files.save(file_id=file_id, file_name=file_name, target_dir=IMAGES_DIR)
                # upload visualization to blob storage for Teams card rendering
                await tools.upload_blob_file(file_name)

    # Clean up the temporary agent
    agent_client.delete_agent(agent.id)

    return response, file_name

# Export a convenient list of public names
__all__ = [
    "AGENT_APP",
    "STORAGE",
    "CONNECTION_MANAGER",
    "AUTHORIZATION",
    "ADAPTER",
    "IMAGES_DIR",
    "FOUNDRY_URL",
    "ADB_CONNECTION_NAME",
    "STORAGE_ACCTNAME",
    "STORAGE_CONTNAME",
    "process_message"
]

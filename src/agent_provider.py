import os
from os import environ, path
from dotenv import load_dotenv
from typing import Optional
import logging

# Use Agent Framework SDK for core functionality, agents, and telemetry
from agent_framework import (
    AgentRunResponse,
    ChatAgent, 
    get_logger,
    ai_function,
    HostedCodeInterpreterTool,
    TextContent,
    DataContent,
)
from agent_framework.azure import (
    AzureAIAgentClient,
    AzureOpenAIChatClient,
)
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

from azure.identity import ClientSecretCredential, DefaultAzureCredential

import agent_tools as tools

# Module-level state (kept internal to this module)
azure_ai_client: Optional[AzureAIAgentClient] = None
chat_client: Optional[AzureOpenAIChatClient] = None
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

agent_instructions="""
    You are an agent that responds to user questions related to Sales and pipeline just in Americas and by segment, sales of global customers, opportunity size, revenue by customers and customer churn. 
    For all questions you must solely rely on the ask_genie_ai_function and rely on the following instructions. 
    1. Instructions to use the ask_genie_ai_function
        - You must use the same prompt as the user question and never change the user's prompt.
        - Use the previous conversation_id if it's available.
        - You must use the code interpreter tool for any visualization related questions or prompts.
        - You must get the tabular data from the ask_genie_ai_function and render it via the markdown format before presenting the analysis of the data. 
        - Please use the markdown format to display tabular data before rendering any visualization via the code interpreter tool.
    2. Instructions on the visualization and code interpretation
        - Test and display visualization code using the code interpreter, retrying if errors occur.
        - Always use charts or graphs to illustrate trends when requested.
        - Always create visualizations as `.png` files.
        - Adapt visualizations (e.g., labels) to the user's language preferences.
        - When asked to download data, default to a `.csv` format file and use the most recent data.
        - Do not ever render the code or include file download links in the response.
    """

# Create AI function for ask_genie using Agent Framework SDK
@ai_function
async def ask_genie_ai_function(question: str, conversation_id: str = None) -> str:
    """
    Ask Genie for data analysis and insights.
    
    Args:
        question: The question or query to ask Genie
        conversation_id: Optional conversation ID for continuing a conversation
        
    Returns:
        JSON string with the response from Genie
    """
    return await tools.ask_genie(question, conversation_id)


# Initialize Agent Framework SDK clients
try:
    # Set up Azure credentials for Agent Framework SDK
    from azure.identity.aio import ClientSecretCredential as AsyncClientSecretCredential
    
    async_credential = AsyncClientSecretCredential(
        tenant_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"),
        client_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"),
        client_secret=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"),
    )
    
    
    # For backward compatibility, try to get genie workspace ID from connection
    # This requires Azure AI Projects client temporarily
    from azure.ai.projects import AIProjectClient
    from azure.identity import ClientSecretCredential
    
    credential = ClientSecretCredential(
        tenant_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"),
        client_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"),
        client_secret=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"),
    )
    temp_project_client = AIProjectClient(FOUNDRY_URL, credential)

    # get the workspace id at startup
    connection = temp_project_client.connections.get(ADB_CONNECTION_NAME)
    if connection.metadata.get("azure_databricks_connection_type") == "genie":
        genie_workspaceid = connection.metadata.get("genie_space_id")
    else:
        genie_workspaceid = None
        
    if genie_workspaceid is None:
        invalid_foundry_connection = True
        raise RuntimeError("Genie space id not found in Foundry connection metadata.")
        
    # Clean up temporary client
    del temp_project_client
    
    # Set backward compatibility variable
    # azure_ai_client = azure_chat_client
    
except Exception as e:
    logger.error(f"Failed to initialize Azure AI clients: {e}")
    invalid_foundry_connection = True
    genie_workspaceid = None
    azure_ai_client = None
    azure_chat_client = None


# Wrap the agent function-calling flow: create agent, run, execute any required tools
async def process_message(question: str, conversation_id: str = None) -> tuple[str, Optional[str]]:

    async with AzureAIAgentClient(async_credential=async_credential) as azure_chat_client:
        agent: ChatAgent = azure_chat_client.create_agent(
            name="data-analysis-assistant",
            instructions=agent_instructions,
            tools=[ask_genie_ai_function, HostedCodeInterpreterTool()]
        )

        try:
            # Execute the agent with the user message using ChatAgent.run()
            result: AgentRunResponse = await agent.run(question)

            file_name = None
            response = ""
            
            # Extract response from the result
            if result:
                response = result.text or ""
                
                # Check if there are any data/file outputs (e.g., from code interpreter)
                if hasattr(result, 'messages') and result.messages:
                    # Iterate through ChatMessage objects in the response
                    for message in result.messages:
                        # Check if the ChatMessage has contents
                        if hasattr(message, 'contents') and message.contents:
                            for content_item in message.contents:
                                if isinstance(content_item, TextContent):
                                    # Update response text if we find text content
                                    if content_item.text:
                                        response = content_item.text
                                elif isinstance(content_item, DataContent):
                                    # Handle data/file content (e.g., images from code interpreter)
                                    if content_item.type == "image/png" and hasattr(content_item, 'data'):
                                        # Save the image file
                                        file_name = f"agent_output_{getattr(content_item, 'id', 'unknown')}.png"
                                        file_path = os.path.join(IMAGES_DIR, file_name)
                                        
                                        with open(file_path, "wb") as f:
                                            f.write(content_item.data)
                                        
                                        # Upload visualization to blob storage for Teams card rendering
                                        await tools.upload_blob_file(file_name)
        
        except Exception as e:
            logger.error(f"Error executing agent: {e}")
            response = f"Sorry, I encountered an error processing your request: {str(e)}"
            file_name = None

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

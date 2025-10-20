import os
from typing import Optional

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

import logging
from dotenv import load_dotenv
import agents.genie_tools as tools
import utils

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Module-level state
azure_ai_client: Optional[AzureAIAgentClient] = None
chat_client: Optional[AzureOpenAIChatClient] = None
invalid_foundry_connection: bool = False

logger = logging.getLogger("microsoft_agents")

ADB_CONNECTION_NAME = os.getenv("ADB_CONNECTION_NAME", "")
genie_workspaceid: str = ADB_CONNECTION_NAME[-32:]

# Create images directory if it doesn't exist
IMAGES_DIR = os.path.join(os.getcwd(), "images")
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

# Load agent instructions from markdown file
with open(os.path.join(os.path.dirname(__file__), "genie_agent_prompt.md"), "r") as f:
    agent_instructions = f.read()

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
    return await tools.ask_genie(question, conversation_id, genie_workspaceid, utils.adbtoken)

# Initialize Agent Framework SDK clients
try:
    # Set up Azure credentials for Agent Framework SDK
    from azure.identity.aio import ClientSecretCredential as AsyncClientSecretCredential
    
    async_credential = AsyncClientSecretCredential(
        tenant_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"),
        client_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"),
        client_secret=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"),
    )
    
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
                                        await utils.upload_blob_file(file_name)
        
        except Exception as e:
            logger.error(f"Error executing agent: {e}")
            response = f"Sorry, I encountered an error processing your request: {str(e)}"
            file_name = None

        return response, file_name

# Export a convenient list of public names
__all__ = [
    "IMAGES_DIR",
    "process_message"
]

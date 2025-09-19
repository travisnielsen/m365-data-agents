# Agent tools: encapsulates calls to external tools and services such as Databricks Genie,
# token acquisition (OBO flow) and blob storage helper functions.

import os
import json
import requests
from typing import Any, Callable, Set, Dict, List, Optional

from azure.ai.projects import AIProjectClient
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieAPI
from azure.storage.blob import BlobServiceClient, ContentSettings

from azure.ai.agents.models import (
    AsyncToolSet,
    AsyncFunctionTool,
    RequiredFunctionToolCall,
    SubmitToolOutputsAction,
    ToolOutput,
    CodeInterpreterTool,
)

import agent_provider as provider

# Module-level state (kept internal to this module)
adbtoken: Optional[str] = None
genie_spaceid: Optional[str] = None
project_client: Optional[AIProjectClient] = None
invalid_foundry_connection: bool = False


async def getadbtoken(passed_user_access_token: str) -> str:
    """
    Retrieve the Azure Databricks token via OBO using the Foundry project configuration.
    Returns the ADB token string.
    """
    global project_client, genie_spaceid, adbtoken, invalid_foundry_connection

    try:
        cred = ClientSecretCredential(
            tenant_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"),
            client_id=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID"),
            client_secret=os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"),
        )

        project_client = AIProjectClient(provider.FOUNDRY_URL, cred)

        # Dynamically fetch the ADB connection metadata from the Foundry project
        connection = project_client.connections.get(provider.ADB_CONNECTION_NAME)
        if connection.metadata.get("azure_databricks_connection_type") == "genie":
            genie_spaceid = connection.metadata.get("genie_space_id")
        else:
            genie_spaceid = None

        if genie_spaceid is None:
            invalid_foundry_connection = True
            raise RuntimeError("Genie space id not found in Foundry connection metadata.")

        # OBO exchange
        host = f'https://login.microsoftonline.com/{os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID")}/'
        client_id = os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID")
        oauth_secret = os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET")
        endpoint = 'oauth2/v2.0/token'
        url = f'{host}{endpoint}'
        DATABRICKS_RESOURCE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "scope": f"{DATABRICKS_RESOURCE}/.default",
            "requested_token_use": "on_behalf_of",
            "assertion": passed_user_access_token,
        }

        auth = (client_id, oauth_secret)
        oauth_response = requests.post(url, data=data, auth=auth)
        oauth_response.raise_for_status()

        adbtoken = oauth_response.json()["access_token"]
        return adbtoken

    except Exception as e:
        provider.ms_agents_logger.error(f"Get ADB token failed: {e}")
        raise


async def getgraphtoken(passed_user_access_token: str) -> str:
    """
    Acquire a Graph access token via OBO.
    """
    try:
        host = f'https://login.microsoftonline.com/{os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID")}/'
        client_id = os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID")
        oauth_secret = os.getenv("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET")
        endpoint = 'oauth2/v2.0/token'
        url = f'{host}{endpoint}'

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "scope": "https://graph.microsoft.com/.default",
            "requested_token_use": "on_behalf_of",
            "assertion": passed_user_access_token,
        }

        auth = (client_id, oauth_secret)
        oauth_response = requests.post(url, data=data, auth=auth)
        oauth_response.raise_for_status()

        oauth_access_token = oauth_response.json()["access_token"]
        return oauth_access_token
    except Exception as e:
        provider.ms_agents_logger.error(f"Get Graph token failed: {e}")
        raise


# Ask Genie: wrap the Databricks Genie APIs and return structured JSON
async def ask_genie(question: str, conversation_id: str = None) -> tuple[str, str]:
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")

    # WorkspaceClient uses the current adbtoken (OBO token) to authenticate
    workspace_client = WorkspaceClient(host=DATABRICKS_HOST, token=adbtoken)
    genie_api = GenieAPI(workspace_client.api_client)

    try:
        if conversation_id is None:
            message = genie_api.start_conversation_and_wait(genie_spaceid, question)
            conversation_id = message.conversation_id
        else:
            message = genie_api.create_message_and_wait(genie_spaceid, conversation_id, question)

        query_result = None
        if message.query_result:
            query_result = genie_api.get_message_query_result(
                genie_spaceid, message.conversation_id, message.id
            )

        message_content = genie_api.get_message(genie_spaceid, message.conversation_id, message.id)

        # Try to parse structured data if available
        if query_result and query_result.statement_response:
            statement_id = query_result.statement_response.statement_id
            results = workspace_client.statement_execution.get_statement(statement_id)

            columns = results.manifest.schema.columns
            data = results.result.data_array

            # Format as markdown table
            headers = [col.name for col in columns]
            rows = []
            for row in data:
                formatted_row = []
                for value, col in zip(row, columns):
                    if value is None:
                        formatted_value = "NULL"
                    elif col.type_name in ["DECIMAL", "DOUBLE", "FLOAT"]:
                        formatted_value = f"{float(value):,.2f}"
                    elif col.type_name in ["INT", "BIGINT", "LONG"]:
                        formatted_value = f"{int(value):,}"
                    else:
                        formatted_value = str(value)
                    formatted_row.append(formatted_value)
                rows.append(formatted_row)

            return json.dumps({
                "conversation_id": conversation_id,
                "table": {"columns": headers, "rows": rows},
            })

        # Fallback to plain message text
        if message_content.attachments:
            for attachment in message_content.attachments:
                if attachment.text and attachment.text.content:
                    return json.dumps({
                        "conversation_id": conversation_id,
                        "message": attachment.text.content,
                    })

        return json.dumps({
            "conversation_id": conversation_id,
            "message": message_content.content or "No content returned.",
        })

    except Exception as e:
        provider.ms_agents_logger.error(f"Ask Genie failed: {e}")
        return json.dumps({"error": "An error occurred while talking to Genie.", "details": str(e)})


# Wrap the agent function-calling flow: create agent, run, execute any required tools
async def processmessage(question: str, conversation_id: str = None) -> tuple[str, Optional[str]]:
    """
    Create and run an agent via Foundry's agent APIs, execute function tool calls (genie),
    and return textual response and optional saved image filename.
    """
    global project_client

    custom_functions = AsyncFunctionTool({ask_genie})
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
                        provider.ms_agents_logger.error(f"Error executing tool_call {tool_call.id}: {e}")

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
                agent_client.files.save(file_id=file_id, file_name=file_name, target_dir=provider.IMAGES_DIR)
                # upload visualization to blob storage for Teams card rendering
                await upload_blob_file(file_name)

    # Clean up the temporary agent
    agent_client.delete_agent(agent.id)

    return response, file_name


async def upload_blob_file(imagefilename: str) -> None:
    account_url = f"https://{provider.STORAGE_ACCTNAME}.blob.core.windows.net"
    container_name = provider.STORAGE_CONTNAME

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    blob_service_client = BlobServiceClient(account_url, credential=credential)

    upload_file_path = os.path.join(provider.IMAGES_DIR, imagefilename)

    container_client = blob_service_client.get_container_client(container=container_name)
    with open(file=upload_file_path, mode="rb") as data:
        content_settings = ContentSettings(content_type="image/jpg")
        container_client.upload_blob(name=imagefilename, data=data, content_settings=content_settings)


async def del_blob_file(imagefilename: str) -> None:
    try:
        account_url = f"https://{provider.STORAGE_ACCTNAME}.blob.core.windows.net"
        container_name = provider.STORAGE_CONTNAME

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        blob_service_client = BlobServiceClient(account_url, credential=credential)

        container_client = blob_service_client.get_container_client(container=container_name)
        blob_client = container_client.get_blob_client(blob=imagefilename)
        blob_client.delete_blob()
    except Exception as e:
        provider.ms_agents_logger.error(f"Error deleting blob: {e}")
        raise


# Expose the set of functions the agent may call
genie_funcs: Set[Callable[..., Any]] = {ask_genie}

__all__ = [
    "getadbtoken",
    "getgraphtoken",
    "ask_genie",
    "processmessage",
    "upload_blob_file",
    "del_blob_file",
    "genie_funcs",
]

import os
import json
import requests
from typing import Any, Callable, Set, Optional
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieAPI
from azure.storage.blob import BlobServiceClient, ContentSettings
import agent_provider as provider

# Module-level state (kept internal to this module)
adbtoken: Optional[str] = None

async def get_adb_token(passed_user_access_token: str) -> str:
    """
    Retrieve the Azure Databricks token via OBO using the Foundry project configuration.
    Returns the ADB token string.
    """
    # global project_client, adbtoken, invalid_foundry_connection
    global adbtoken

    try:

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

async def get_graph_token(passed_user_access_token: str) -> str:
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
async def ask_genie(question: str, conversation_id: str = None, genie_workspaceid: str = None) -> str:
    # Use the global genie_workspaceid from agent_provider if not provided
    if genie_workspaceid is None:
        genie_workspaceid = provider.genie_workspaceid
        provider.ms_agents_logger.info(f"Using genie_workspaceid from provider: {genie_workspaceid}")
    else:
        provider.ms_agents_logger.info(f"Using provided genie_workspaceid: {genie_workspaceid}")
        
    if genie_workspaceid is None:
        error_msg = "Genie workspace ID not configured. Please check your AI Foundry connection setup."
        provider.ms_agents_logger.error(error_msg)
        return json.dumps({
            "error": error_msg,
            "details": "No genie_workspaceid available from configuration or parameters."
        })
    
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
    provider.ms_agents_logger.info(f"Asking Genie: '{question}' (workspace: {genie_workspaceid})")

    # WorkspaceClient uses the current adbtoken (OBO token) to authenticate
    workspace_client = WorkspaceClient(host=DATABRICKS_HOST, token=adbtoken)
    genie_api = GenieAPI(workspace_client.api_client)

    try:
        if conversation_id is None:
            message = genie_api.start_conversation_and_wait(genie_workspaceid, question)
            conversation_id = message.conversation_id
        else:
            message = genie_api.create_message_and_wait(genie_workspaceid, conversation_id, question)

        query_result = None
        if message.query_result:
            query_result = genie_api.get_message_query_result(
                genie_workspaceid, message.conversation_id, message.id
            )

        message_content = genie_api.get_message(genie_workspaceid, message.conversation_id, message.id)

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
    "get_adb_token",
    "get_graph_token",
    "ask_genie",
    "upload_blob_file",
    "del_blob_file",
    "genie_funcs",
]

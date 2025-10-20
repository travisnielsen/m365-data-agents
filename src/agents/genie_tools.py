import os
from os import path
import json
import logging
from dotenv import load_dotenv
from typing import Any, Callable, Set
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieAPI

# Load environment variables from .env located in the parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

logger = logging.getLogger("microsoft_agents")

# Ask Genie: wrap the Databricks Genie APIs and return structured JSON
async def ask_genie(question: str, conversation_id: str = None, genie_workspaceid: str = None, adbtoken: str = None) -> str:
    if genie_workspaceid:
        logger.info(f"Using provided genie_workspaceid: {genie_workspaceid}")

    if adbtoken is None:
        error_msg = "ADB token not provided. Cannot authenticate to Databricks."
        logger.error(error_msg)
        return json.dumps({
            "error": error_msg,
            "details": "No adbtoken available from parameters."
        })

    if genie_workspaceid is None:
        error_msg = "Genie workspace ID not configured. Please check your AI Foundry connection setup."
        logger.error(error_msg)
        return json.dumps({
            "error": error_msg,
            "details": "No genie_workspaceid available from configuration or parameters."
        })
    
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
    logger.info(f"Asking Genie: '{question}' (workspace: {genie_workspaceid})")

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
        logger.error(f"Ask Genie failed: {e}")
        return json.dumps({"error": "An error occurred while talking to Genie.", "details": str(e)})



# Expose the set of functions the agent may call
genie_funcs: Set[Callable[..., Any]] = {ask_genie}

__all__ = [
    "ask_genie",
    "genie_funcs",
]

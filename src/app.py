import re
import traceback
import agents.genie_agent as agent
import utils
import os
from os import environ, path
from dotenv import load_dotenv

from microsoft_agents.activity import ActivityTypes, Attachment
from microsoft_agents.hosting.core import TurnContext, TurnState, MessageFactory
from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.activity import load_configuration_from_env

from microsoft_agents.hosting.core import (
    TurnState,
    MemoryStorage,
    AgentApplication,
    Authorization
)

import logging

# Load environment variables from .env located next to this module
load_dotenv(path.join(path.dirname(__file__), ".env"))

# Logging setup (keeps parity with previous app.py behavior)
logger = logging.getLogger("microsoft_agents")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"))
if not logger.handlers:
    logger.addHandler(console_handler)

loglevel = os.getenv("LOG_LEVEL", "WARNING").upper()
if loglevel == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif loglevel == "INFO":
    logger.setLevel(logging.INFO)
elif loglevel == "ERROR":
    logger.setLevel(logging.ERROR)
else:
    logger.setLevel(logging.WARNING)

# Import and setup tracing
try:
    from tracing_config import setup_agent_tracing
    setup_agent_tracing()
    logger.info("Starting M365 agent with tracing enabled")
except ImportError:
    logger.warning("Tracing configuration not available")
    logger.info("Starting M365 agent without tracing")

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

STORAGE_ACCTNAME = os.getenv("STORAGE_ACCTNAME", "")
STORAGE_CONTNAME = os.getenv("STORAGE_CONTNAME", "")

@AGENT_APP.activity(ActivityTypes.invoke)
async def invoke(context: TurnContext, state: TurnState) -> str:
    """
    Internal method to process template expansion or function invocation.
    """
    await AGENT_APP.auth.begin_or_continue_flow(context, state)


@AGENT_APP.on_sign_in_success
async def handle_sign_in_success(
    context: TurnContext, state: TurnState, handler_id: str = None
) -> bool:
    """
    Internal method to handle successful sign-in events.
    """
    await context.send_activity(
        MessageFactory.text(
            f"Successfully signed in to {handler_id or 'service'}. You can now use authorized features."
        )
    )


@AGENT_APP.conversation_update("membersAdded")
async def on_members_added(context: TurnContext, state: TurnState):
    await context.send_activity(
        MessageFactory.text(
            "Welcome to the ADB-AIFoundry-Teams demo! "
            "For OAuth flows, enter the 6-digit verification code when prompted."
        )
    )
    return True


@AGENT_APP.error
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=None)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")


# Decorator to ensure that the user's ID token is retrieved dynamically by using handler.
@AGENT_APP.message(re.compile(r".*", re.IGNORECASE), auth_handlers=["GRAPH"])
async def on_message(context: TurnContext, state: TurnState):
    """
    Main message handler: obtains OBO tokens, calls into utilities to process message and
    returns the results to the user.
    """
    try:
        prompt = context.activity.text.strip()
        await context.send_activity("Agent is thinking...Thanks for being patient...")

        # Always fetch a fresh ADB token for the requesting user
        user_access_token = await AGENT_APP.auth.get_token(context, "GRAPH")
        await utils.get_adb_token(user_access_token.token)

    except Exception as e:
        await context.send_activity(MessageFactory.text("Error occurred while fetching ADB token. error: " + str(e)))
        return

    try:
        # Validate Foundry connection
        if agent.genie_workspaceid is None or utils.adbtoken is None:
            if agent.invalid_foundry_connection:
                await context.send_activity(MessageFactory.text("Azure Foundry URL is either incorrect or the Databricks Genie connection isn't configured for the Azure AI Foundry project."))
                return

        response, imageurl = await agent.process_message(prompt)

        if response:
            await context.send_activity(MessageFactory.text(response))

        if imageurl:
            await _send_custom_card(context, imageurl)

    except Exception as e:
        await context.send_activity(MessageFactory.text(traceback.format_exc()))


async def _send_custom_card(turn_context: TurnContext, imageurl: str):
    """
    Send an adaptive card with the visualization image URL from blob storage.
    """
    try:
        container_blob_file_path = f"https://{STORAGE_ACCTNAME}.blob.core.windows.net/{STORAGE_CONTNAME}/{imageurl}"

        card_data = {
            "type": "AdaptiveCard",
            "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": [
                {"type": "Image", "id": "0001", "url": container_blob_file_path}
            ],
        }

        attachment = Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card_data)
        await turn_context.send_activity(MessageFactory.attachment(attachment))

    except Exception as e:
        await turn_context.send_activity(f"Error sending custom adaptive card: {str(e)}")


__all__ = ["invoke", "handle_sign_in_success", "on_members_added", "on_error", "on_message"]

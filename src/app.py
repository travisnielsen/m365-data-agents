import re
import traceback
import agent_provider as provider
import agent_tools as tools

from microsoft_agents.activity import ActivityTypes, Attachment
from microsoft_agents.hosting.core import TurnContext, TurnState, MessageFactory

AGENT_APP = provider.AGENT_APP

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
    Main message handler: obtains OBO tokens, calls into tools to process message and
    returns the results to the user.
    """
    try:
        prompt = context.activity.text.strip()
        await context.send_activity("Agent is thinking...Thanks for being patient...")

        # Always fetch a fresh ADB token for the requesting user
        user_access_token = await AGENT_APP.auth.get_token(context, "GRAPH")
        await tools.get_adb_token(user_access_token.token)

    except Exception as e:
        await context.send_activity(MessageFactory.text("Error occurred while fetching ADB token. error: " + str(e)))
        return

    try:
        # Validate Foundry connection
        if provider.genie_workspaceid is None or tools.adbtoken is None:
            if provider.invalid_foundry_connection:
                await context.send_activity(MessageFactory.text("Azure Foundry URL is either incorrect or the Databaricks Genie connection isn't configured for the Azure AI Foundry project ."))
                return

        response, imageurl = await provider.process_message(prompt)

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
        container_blob_file_path = f"https://{provider.STORAGE_ACCTNAME}.blob.core.windows.net/{provider.STORAGE_CONTNAME}/{imageurl}"

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

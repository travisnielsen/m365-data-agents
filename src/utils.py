import os
import logging
from os import path
from typing import Optional
import requests
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

# Set up Agent Framework SDK logging and tracing
logger = logging.getLogger("microsoft_agents")

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
        logger.error(f"Get ADB token failed: {e}")
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
        logger.error(f"Get Graph token failed: {e}")
        raise


async def upload_blob_file(imagefilename: str, storageAcctName: str, storageContainerName: str, imagesDir: str) -> None:
    account_url = f"https://{storageAcctName}.blob.core.windows.net"
    container_name = storageContainerName

    # TODO: rework credential. May need to work via storage token on behalf of user
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    upload_file_path = os.path.join(imagesDir, imagefilename)

    container_client = blob_service_client.get_container_client(container=container_name)
    with open(file=upload_file_path, mode="rb") as data:
        content_settings = ContentSettings(content_type="image/jpg")
        container_client.upload_blob(name=imagefilename, data=data, content_settings=content_settings)


async def del_blob_file(imagefilename: str, storageAcctName: str, storageContainerName: str) -> None:
    try:
        account_url = f"https://{storageAcctName}.blob.core.windows.net"
        container_name = storageContainerName

        # TODO: rework credential. May need to work via storage token on behalf of user
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        blob_service_client = BlobServiceClient(account_url, credential=credential)
        container_client = blob_service_client.get_container_client(container=container_name)
        blob_client = container_client.get_blob_client(blob=imagefilename)
        blob_client.delete_blob()
    except Exception as e:
        logger.error(f"Error deleting blob: {e}")
        raise


__all__ = [
    "get_adb_token",
    "get_graph_token",
    "upload_blob_file",
    "del_blob_file"
]
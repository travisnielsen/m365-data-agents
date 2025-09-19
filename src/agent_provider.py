# Agent provider: responsible for loading environment, configuring storage, adapter,
# authorization and creating the AgentApplication instance exported as AGENT_APP.

import os
from os import environ, path
from dotenv import load_dotenv
import logging

from microsoft_agents.activity import load_configuration_from_env
from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.hosting.core import (
    Authorization,
    AgentApplication,
    TurnState,
    MemoryStorage,
)
from microsoft_agents.authentication.msal import MsalConnectionManager

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

# Export a convenient list of public names
__all__ = [
    "AGENT_APP",
    "STORAGE",
    "CONNECTION_MANAGER",
    "AUTHORIZATION",
    "IMAGES_DIR",
    "FOUNDRY_URL",
    "ADB_CONNECTION_NAME",
    "STORAGE_ACCTNAME",
    "STORAGE_CONTNAME",
]

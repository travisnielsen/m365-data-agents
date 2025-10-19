# Microsoft Agent Framework SDK Migration Guide

This repository has been updated to use the new Microsoft Agent Framework SDK. This guide explains the changes and how to migrate your existing setup.

## Major Changes

### 1. Package Dependencies
The following packages have been replaced:
- ❌ `azure-ai-agents`
- ❌ `microsoft-agents-*` packages
- ✅ `agent-framework` (single unified SDK)

### 2. Core Classes and Imports
| Old Import | New Import |
|------------|------------|
| `from microsoft_agents.hosting.core import AgentApplication` | `from agent_framework import Agent` |
| `from microsoft_agents.hosting.aiohttp import CloudAdapter` | `from agent_framework.hosting.aiohttp import M365Adapter` |
| `from microsoft_agents.authentication.msal import MsalConnectionManager` | `from agent_framework import M365ConnectionManager` |

### 3. Configuration Changes
The Agent Framework SDK uses a simplified configuration approach:

**Old Configuration (env.sample):**
```env
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET=
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID=
AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH__SETTINGS__AZUREBOTOAUTHCONNECTIONNAME=
```

**New Configuration (env.sample):**
```env
MICROSOFT_APP_ID=
MICROSOFT_APP_PASSWORD=
MICROSOFT_APP_TENANT_ID=
```

### 4. Decorator Changes
Message and activity handlers use new decorator patterns:

**Old Decorators:**
```python
@AGENT_APP.activity(ActivityTypes.invoke)
@AGENT_APP.conversation_update("membersAdded")  
@AGENT_APP.message(re.compile(r".*"), auth_handlers=["GRAPH"])
```

**New Decorators:**
```python
@AGENT_APP.on_activity(ActivityTypes.invoke)
@AGENT_APP.on_members_added
@AGENT_APP.on_message(pattern=re.compile(r".*"), auth_handlers=["GRAPH"])
```

### 5. Built-in OpenTelemetry Tracing
The new SDK includes built-in tracing support:

```python
from agent_framework.telemetry import setup_telemetry

# Set up tracing (automatically configured in agent_provider.py)
setup_telemetry(
    otlp_endpoint="http://localhost:4317",  # AI Toolkit gRPC endpoint
    enable_sensitive_data=True  # Enable capturing prompts and completions
)
```

## Migration Steps

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Update Environment Variables:**
   - Copy the new `src/env.sample` to `src/.env`
   - Update the environment variables with your Microsoft App registration details

3. **Test the Application:**
   ```bash
   cd src
   python main.py
   ```

## Key Benefits

- 🔧 **Simplified Setup**: Fewer packages and simpler configuration
- 📊 **Built-in Tracing**: OpenTelemetry support out of the box  
- 🚀 **Better Performance**: Optimized SDK architecture
- 📖 **Improved Documentation**: Better IntelliSense and type hints
- 🔄 **Future-Proof**: Active development and support from Microsoft

## Troubleshooting

### Import Errors
If you see import errors, ensure you've installed the new `agent-framework` package:
```bash
pip install agent-framework
```

### Authentication Issues  
Make sure your environment variables are correctly set:
- `MICROSOFT_APP_ID`: Your bot's Application (client) ID
- `MICROSOFT_APP_PASSWORD`: Your bot's client secret
- `MICROSOFT_APP_TENANT_ID`: Your Azure tenant ID

### Tracing Issues
To view traces, open the AI Toolkit tracing page in VS Code:
- Open Command Palette (`Ctrl+Shift+P`)
- Run "AI Toolkit: Open Tracing Page"
- Ensure the OTLP endpoint is running on `http://localhost:4317`

## Additional Resources

- [Microsoft Agent Framework SDK Documentation](https://docs.microsoft.com/en-us/azure/bot-service/)
- [OpenTelemetry Tracing Guide](https://opentelemetry.io/docs/)
- [Microsoft Teams Bot Development](https://docs.microsoft.com/en-us/microsoftteams/platform/bots/what-are-bots)
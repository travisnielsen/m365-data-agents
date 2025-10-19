# Microsoft Agent Framework SDK Integration Guide

This repository has been updated to integrate the new **Microsoft Agent Framework SDK** alongside the existing Microsoft Agents packages. This provides enhanced functionality while maintaining compatibility with existing Teams/M365 integrations.

## Integration Approach

This implementation uses a **hybrid approach**:
- ✅ **Agent Framework SDK**: For enhanced logging, observability, and new features
- ✅ **Microsoft Agents packages**: For Teams/M365 integration and existing functionality
- ✅ **OpenTelemetry Tracing**: Built-in support via Agent Framework SDK

## Package Dependencies

### Added Packages
```txt
# Microsoft Agent Framework SDK - New unified framework
agent-framework

# Compatible Microsoft Agents packages (v0.4.0)
microsoft-agents-hosting-core==0.4.0
microsoft-agents-activity==0.4.0
microsoft-agents-hosting-aiohttp==0.4.0
microsoft-agents-authentication-msal==0.4.0
microsoft-agents-hosting-teams==0.4.0

# Azure AI Agents (for model compatibility)
azure-ai-agents==1.2.0b5
```

## Key Integrations

### 1. Enhanced Logging
```python
from agent_framework import get_logger

# Agent Framework SDK logger with proper namespace
logger = get_logger("agent_framework.m365_data_agents")
logger.info("Enhanced logging with Agent Framework SDK")
```

### 2. OpenTelemetry Tracing
The integration includes built-in tracing support:

```python
# tracing_config.py - Automatic OpenTelemetry setup
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
os.environ.setdefault("OTEL_SERVICE_NAME", "m365-data-agents")
```

### 3. Microsoft 365 Integration
```python
# Continues to use microsoft_agents packages for Teams/M365
from microsoft_agents.hosting.core import AgentApplication, TurnState
from microsoft_agents.activity import ActivityTypes
```

## Migration Benefits

- 🔧 **Enhanced Observability**: Agent Framework SDK logging and tracing
- 📊 **OpenTelemetry Integration**: Built-in tracing with AI Toolkit support
- 🔄 **Backward Compatibility**: Existing Teams/M365 functionality preserved
- 🚀 **Future-Ready**: Access to new Agent Framework SDK features
- 📈 **Better Monitoring**: Improved debugging and performance insights

## How to Use

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. View Traces
1. Open AI Toolkit in VS Code
2. Navigate to the Tracing page
3. Start your agent application
4. View real-time traces and telemetry

### 3. Enhanced Logging
Agent Framework SDK logging is automatically configured with appropriate namespaces and enhanced formatting.

## Environment Variables

The integration supports enhanced configuration:

```env
# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=m365-data-agents
AGENT_FRAMEWORK_ENABLE_SENSITIVE_DATA=true

# Existing M365 Configuration
MICROSOFT_APP_ID=your_app_id
MICROSOFT_APP_PASSWORD=your_app_password
MICROSOFT_APP_TENANT_ID=your_tenant_id
```

## Testing the Integration

```bash
cd src
python -c "
import agent_provider
import m365_agent
import main
print('✅ Agent Framework SDK integration successful!')
"
```

## What's Next

This integration positions the repository to:
- 📱 Leverage new Agent Framework SDK capabilities as they become available
- 📊 Benefit from enhanced observability and debugging tools
- 🔧 Maintain compatibility with existing Microsoft 365/Teams features
- 🚀 Access cutting-edge AI agent development patterns

## Troubleshooting

### Package Version Conflicts
Ensure all microsoft-agents packages are version 0.4.0:
```bash
pip install microsoft-agents-hosting-core==0.4.0 microsoft-agents-activity==0.4.0
```

### Logger Name Errors
Agent Framework SDK loggers must use the proper namespace:
```python
# ❌ Wrong
logger = get_logger(__name__)

# ✅ Correct  
logger = get_logger("agent_framework.your_module_name")
```

### Tracing Not Working
1. Ensure AI Toolkit is running
2. Check OTLP endpoint is accessible at `http://localhost:4317`
3. Verify environment variables are set correctly
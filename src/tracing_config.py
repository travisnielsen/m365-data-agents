# OpenTelemetry tracing configuration for the Agent Framework SDK

import os
from agent_framework import get_logger

# Initialize Agent Framework logger for tracing
logger = get_logger("agent_framework.m365_data_agents.tracing")

def setup_agent_tracing():
    """
    Set up OpenTelemetry tracing for the Agent Framework SDK.
    This integrates with AI Toolkit's tracing capabilities.
    """
    try:
        # Set up environment variables for OpenTelemetry
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        os.environ.setdefault("OTEL_SERVICE_NAME", "m365-data-agents")
        os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", "service.name=m365-data-agents,service.version=1.0.0")
        
        # Enable sensitive data capture for development
        os.environ.setdefault("AGENT_FRAMEWORK_ENABLE_SENSITIVE_DATA", "true")
        
        logger.info("OpenTelemetry tracing configured for Agent Framework SDK")
        logger.info(f"OTLP Endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}")
        return False

def get_trace_url():
    """
    Get the URL for viewing traces in AI Toolkit.
    """
    return "http://localhost:3000/tracing"  # AI Toolkit tracing UI

if __name__ == "__main__":
    setup_agent_tracing()
    print("✅ Tracing setup complete. Open AI Toolkit to view traces.")
    print(f"📊 Trace viewer: {get_trace_url()}")
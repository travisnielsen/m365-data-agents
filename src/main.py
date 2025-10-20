import os
from microsoft_agents.hosting.core import AgentApplication, AgentAuthConfiguration
from microsoft_agents.hosting.aiohttp import (
    start_agent_process,
    jwt_authorization_middleware,
    CloudAdapter,
)
from aiohttp.web import Request, Response, Application, run_app

# Attempt package-relative imports when run as a package; fall back to top-level imports
try:
    # Import handlers to register them with AGENT_APP (module import triggers decorator registration)
    from . import app  # noqa: F401
except Exception:
    # When executed as a script (python src/main.py) the src/ directory is on sys.path
    import app  # noqa: F401

def start_server(agent_application: AgentApplication, auth_configuration: AgentAuthConfiguration):
    async def entry_point(req: Request) -> Response:
        agent: AgentApplication = req.app["agent_app"]
        adapter: CloudAdapter = req.app["adapter"]
        return await start_agent_process(req, agent, adapter)

    APP = Application(middlewares=[jwt_authorization_middleware])
    APP.router.add_post("/api/messages", entry_point)

    # Add /health GET endpoint
    async def health_check(req: Request) -> Response:
        return Response(status=200, text="OK")

    APP.router.add_get("/health", health_check)

    APP["agent_configuration"] = auth_configuration
    APP["agent_app"] = agent_application
    APP["adapter"] = agent_application.adapter

    try:
        run_app(APP, host="0.0.0.0", port=int(os.getenv("PORT", "3978")))
    except Exception as error:
        raise error

# Start the server using the configured AgentApplication and the default auth configuration
if __name__ == "__main__":
    start_server(
        agent_application=app.AGENT_APP,
        auth_configuration=app.CONNECTION_MANAGER.get_default_connection_configuration(),
    )
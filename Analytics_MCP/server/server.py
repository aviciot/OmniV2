# server/server.py
import os
import sys
import signal
import logging
import importlib
import pkgutil
import warnings

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
import uvicorn

from config import config
from mcp_app import mcp

# -----------------------------------------------------------------------------
# 🔧 Logging setup
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
# Reduce noise from dependencies
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger("mcp-server")

# -----------------------------------------------------------------------------
# ⚙️ Environment flags
# -----------------------------------------------------------------------------
AUTO_DISCOVER = os.getenv("AUTO_DISCOVER", "true").lower() in ("1", "true", "yes", "on")

# -----------------------------------------------------------------------------
# 🛑 Graceful shutdown
# -----------------------------------------------------------------------------
def _graceful(*_):
    logger.info("🛑 Received shutdown signal, stopping gracefully...")
    sys.exit(0)

for s in (signal.SIGINT, signal.SIGTERM):
    signal.signal(s, _graceful)

# -----------------------------------------------------------------------------
# 🧠 Module loading helpers
# -----------------------------------------------------------------------------
def import_submodules(pkg_name: str):
    """Auto-import all submodules in a package (tools/resources/prompts)."""
    try:
        pkg = __import__(pkg_name)
        for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            if not ispkg and not modname.startswith('_'):
                full_name = f"{pkg_name}.{modname}"
                importlib.import_module(full_name)
                logger.info(f"✅ Loaded: {full_name}")
    except Exception as e:
        logger.error(f"❌ Failed to load {pkg_name}: {e}")

def safe_import(name: str):
    """Static import (fallback when AUTO_DISCOVER disabled)."""
    try:
        module = __import__(name, fromlist=["*"])
        logger.info(f"✅ Imported: {name}")
        return module
    except Exception as e:
        logger.exception(f"❌ Failed to import: {name}: {e}")
        raise

# -----------------------------------------------------------------------------
# 🚀 Startup banner
# -----------------------------------------------------------------------------
logger.info("=" * 60)
logger.info(f"🚀 Starting MCP Server: {config.server_name}")
logger.info(f"🌐 Port: {config.server_port}")
logger.info("=" * 60)

if AUTO_DISCOVER:
    logger.info("🔍 Auto-loading modules...")
    for pkg in ("tools", "resources", "prompts"):
        import_submodules(pkg)
else:
    logger.info("📦 Using static imports...")
    for pkg in ("tools", "resources", "prompts"):
        safe_import(pkg)

logger.info(f"✅ Server ready at http://localhost:{config.server_port}")
logger.info("=" * 60)





# -----------------------------------------------------------------------------
# 🌐 Build ASGI app
# -----------------------------------------------------------------------------
os.environ["PYTHONUNBUFFERED"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette.applications")

mcp_app = mcp.http_app()
app = Starlette(lifespan=mcp_app.lifespan)

# Modern (non-deprecated) route registration
async def health(request):
    return PlainTextResponse("ok")

async def info(request):
    tools = list(getattr(mcp, "_tools", {}).keys()) if hasattr(mcp, "_tools") else []
    return JSONResponse({"name": config.server_name, "tools": tools})

app.add_route("/healthz", health, methods=["GET"])
app.add_route("/_info", info, methods=["GET"])

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_methods=config.cors_methods,
    allow_headers=config.cors_headers,
)

app.mount("/", mcp_app)

# -----------------------------------------------------------------------------
# ▶️ Run the server
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.server_port,
        reload=True,
        reload_dirs=["server"],
        log_level="info",
    )



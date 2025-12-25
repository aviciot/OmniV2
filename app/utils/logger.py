"""
Structured Logging Configuration

Uses structlog for structured logging with JSON output in production
and pretty console output in development.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger


# ============================================================
# Custom Processors
# ============================================================

def add_app_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to log events."""
    event_dict["app"] = "omni2"
    return event_dict


def censor_sensitive_data(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Censor sensitive data in logs (passwords, API keys, etc.)."""
    sensitive_keys = {
        "password", "api_key", "secret", "token", "authorization",
        "DATABASE_PASSWORD", "ANTHROPIC_API_KEY", "SLACK_BOT_TOKEN"
    }
    
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "***REDACTED***"
    
    return event_dict


# ============================================================
# Logging Setup
# ============================================================

def setup_logging() -> None:
    """
    Configure structured logging for the application.
    
    In development: Pretty console output with colors
    In production: JSON logs to file and stdout
    """
    # Import settings here to avoid circular imports
    from app.config import settings
    
    # Ensure logs directory exists
    log_file = Path(settings.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Determine if we're in development
    is_development = settings.app.environment == "development"
    
    # Configure timestamper
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    # Build processor chain
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_app_context,
        censor_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        timestamper,
    ]
    
    if is_development:
        # Development: Pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.logging.level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.logging.level),
    )
    
    # File handler for production
    if not is_development:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.root.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


# ============================================================
# Logger Instance
# ============================================================

# Get logger instance
logger = structlog.get_logger()


# ============================================================
# Convenience Functions
# ============================================================

def log_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Log an HTTP request."""
    logger.info(
        "HTTP Request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
    )


def log_mcp_call(
    mcp_name: str,
    tool_name: str,
    duration_ms: float,
    success: bool,
    error: str = None,
) -> None:
    """Log an MCP tool invocation."""
    logger.info(
        "MCP Tool Call",
        mcp_name=mcp_name,
        tool_name=tool_name,
        duration_ms=round(duration_ms, 2),
        success=success,
        error=error,
    )


def log_audit(
    user_email: str,
    action: str,
    resource: str,
    success: bool,
    details: dict = None,
) -> None:
    """Log an audit event."""
    logger.info(
        "Audit Event",
        user=user_email,
        action=action,
        resource=resource,
        success=success,
        details=details or {},
    )

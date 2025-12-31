"""
Configuration Management for OMNI2

Loads and validates configuration from:
- YAML files (settings.yaml, mcps.yaml, users.yaml, slack.yaml)
- Environment variables (.env)
- Environment variable substitution in YAML (${VAR_NAME})
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


# ============================================================
# Configuration Models
# ============================================================

class AppConfig(BaseModel):
    """Application settings."""
    name: str = "OMNI2"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    reload: bool = True
    timezone: str = "UTC"


class DatabaseConfig(BaseModel):
    """Database connection settings."""
    host: str
    port: int = 5432
    database: str
    user: str
    password: str
    pool_size: int = 20
    max_overflow: int = 10
    echo: bool = False
    
    @property
    def url(self) -> str:
        """Generate async PostgreSQL URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class LLMConfig(BaseModel):
    """LLM (Anthropic Claude) configuration."""
    api_key: str
    model: str = "claude-sonnet-4-5-20250929"  # Default to Claude 4.5
    max_tokens: int = 4096
    timeout: int = 30
    temperature: float = 0.0
    routing_confidence_threshold: float = 0.7


class MCPRetryConfig(BaseModel):
    """Retry configuration for MCP connections."""
    max_attempts: int = 2  # Total attempts (1 initial + 1 retry)
    delay_seconds: float = 1.0  # Wait between retries
    connection_max_age_seconds: int = 600  # Force refresh after 10 min


class MCPAuthConfig(BaseModel):
    """Authentication config for an MCP server."""
    enabled: bool = False
    type: str = "bearer"  # bearer, basic, api_key
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    header_name: Optional[str] = None
    header_value: Optional[str] = None


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    name: str
    display_name: str
    protocol: str = "http"  # Options: http, stdio, sse
    url: Optional[str] = None  # Required for http/sse, not for stdio
    command: Optional[str] = None  # Required for stdio
    args: List[str] = Field(default_factory=list)  # For stdio
    cwd: Optional[str] = None  # Working directory for stdio
    enabled: bool = True
    timeout_seconds: int = 30
    description: str = ""
    authentication: Optional[MCPAuthConfig] = None
    retry: Optional[MCPRetryConfig] = None  # Per-MCP retry settings (optional)
    
    # Accept tool_policy as flexible dict (can be string or dict with mode)
    tool_policy: Any = "allow_all"
    allowed_tools: List[str] = Field(default_factory=list)
    denied_tools: List[str] = Field(default_factory=list)
    
    # Accept role_restrictions as flexible dict
    role_restrictions: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "allow"}  # Allow extra fields like tags, rate_limit, etc.


class MCPConfig(BaseModel):
    """MCP registry configuration."""
    global_settings: Dict[str, Any] = Field(default_factory=dict)
    mcps: List[MCPServerConfig] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    """Security settings."""
    secret_key: str
    cors_enabled: bool = True
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = True
    rate_limit_default: int = 100


class AuditConfig(BaseModel):
    """Audit logging settings."""
    enabled: bool = True
    log_all_requests: bool = True
    retention_days: int = 90
    watch_users: List[str] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/omni2.log"
    rotation: str = "daily"
    retention_days: int = 30


# ============================================================
# Main Settings Class
# ============================================================

class Settings(BaseSettings):
    """
    Main application settings loaded from environment variables.
    
    This uses pydantic-settings to load from .env file and environment.
    """
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra environment variables
    }
    
    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_RELOAD: bool = True
    
    # Database
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "omni"
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Anthropic
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"  # Default to Claude 4.5
    ANTHROPIC_MAX_TOKENS: int = 4096
    ANTHROPIC_TIMEOUT: int = 30
    
    # Security
    SECRET_KEY: str = "change-this-in-production"
    CORS_ENABLED: bool = True
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # MCP Servers
    MCP_ORACLE_API_KEY: Optional[str] = None


# ============================================================
# Configuration Loader
# ============================================================

class ConfigLoader:
    """Loads and manages all configuration files."""
    
    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir
        self._cache: Dict[str, Any] = {}
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """
        Recursively substitute environment variables in YAML data.
        
        Replaces ${VAR_NAME} with the value of environment variable VAR_NAME.
        """
        if isinstance(data, dict):
            return {k: self._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Find ${VAR_NAME} patterns
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, data)
            
            result = data
            for var_name in matches:
                env_value = os.getenv(var_name, "")
                result = result.replace(f"${{{var_name}}}", env_value)
            
            return result
        else:
            return data
    
    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load and parse a YAML configuration file."""
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Substitute environment variables
        data = self._substitute_env_vars(data)
        
        return data
    
    def load_settings_yaml(self) -> Dict[str, Any]:
        """Load settings.yaml."""
        return self.load_yaml("settings.yaml")
    
    def load_mcps_yaml(self) -> MCPConfig:
        """Load and parse mcps.yaml."""
        data = self.load_yaml("mcps.yaml")
        
        return MCPConfig(
            global_settings=data.get("global", {}),
            mcps=[MCPServerConfig(**mcp) for mcp in data.get("mcps", [])]
        )
    
    def load_users_yaml(self) -> Dict[str, Any]:
        """Load users.yaml."""
        return self.load_yaml("users.yaml")
    
    def load_slack_yaml(self) -> Dict[str, Any]:
        """Load slack.yaml."""
        return self.load_yaml("slack.yaml")


# ============================================================
# Global Configuration Instance
# ============================================================

# Load environment variables
settings_env = Settings()

# Load YAML configurations
config_loader = ConfigLoader()

# Build structured configuration
class GlobalConfig:
    """Global configuration object combining all sources."""
    
    def __init__(self):
        # App config
        self.app = AppConfig(
            environment=settings_env.APP_ENV,
            host=settings_env.APP_HOST,
            port=settings_env.APP_PORT,
            debug=settings_env.APP_DEBUG,
            reload=settings_env.APP_RELOAD,
        )
        
        # Database config
        self.database = DatabaseConfig(
            host=settings_env.DATABASE_HOST,
            port=settings_env.DATABASE_PORT,
            database=settings_env.DATABASE_NAME,
            user=settings_env.DATABASE_USER,
            password=settings_env.DATABASE_PASSWORD,
            pool_size=settings_env.DATABASE_POOL_SIZE,
            max_overflow=settings_env.DATABASE_MAX_OVERFLOW,
        )
        
        # LLM config
        self.llm = LLMConfig(
            api_key=settings_env.ANTHROPIC_API_KEY,
            model=settings_env.ANTHROPIC_MODEL,
            max_tokens=settings_env.ANTHROPIC_MAX_TOKENS,
            timeout=settings_env.ANTHROPIC_TIMEOUT,
        )
        
        # Security config
        self.security = SecurityConfig(
            secret_key=settings_env.SECRET_KEY,
            cors_enabled=settings_env.CORS_ENABLED,
            cors_origins=["http://localhost:3000", "http://localhost:8000"],
        )
        
        # Audit config
        self.audit = AuditConfig()
        
        # Logging config
        self.logging = LoggingConfig(
            level=settings_env.LOG_LEVEL,
            format=settings_env.LOG_FORMAT,
        )
        
        # MCP config
        self.mcps = config_loader.load_mcps_yaml()
        
        # Users config (raw YAML for now)
        self.users_config = config_loader.load_users_yaml()
        
        # Slack config (raw YAML for now)
        self.slack_config = config_loader.load_slack_yaml()


# Global settings instance
settings = GlobalConfig()

# server/config.py
import os
import yaml
import re
from typing import List, Dict, Any

class Config:
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = self._load_config(config_path)
        
    def _resolve_env_vars(self, config: Any) -> Any:
        """Recursively resolve environment variables in config."""
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Match ${VAR:default} or ${VAR} patterns
            pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
            matches = re.findall(pattern, config)
            if matches:
                result = config
                for var_name, default_value in matches:
                    env_value = os.getenv(var_name, default_value)
                    result = result.replace(f"${{{var_name}:{default_value}}}", env_value)
                    result = result.replace(f"${{{var_name}}}", env_value)
                # Try to convert to int if it's a number
                try:
                    return int(result)
                except ValueError:
                    return result
            return config
        return config
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            with open(config_path, 'r') as f:
                raw_config = yaml.safe_load(f) or {}
                return self._resolve_env_vars(raw_config)
        except FileNotFoundError:
            return {
                "server": {
                    "name": os.getenv("MCP_SERVER_NAME", "ModularMCPServer"),
                    "port": int(os.getenv("MCP_PORT", 9009)),
                    "url": os.getenv("MCP_SERVER_URL", "http://localhost:9009/mcp/"),
                },
                "cors": {
                    "origins": os.getenv("CORS_ORIGINS", "*").split(","),
                    "methods": ["GET", "POST", "OPTIONS", "DELETE"],
                    "headers": ["*"],
                },
                "groq": {
                    "api_key": os.getenv("GROQ_API_KEY", ""),
                    "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                },
                "remote_servers": {
                    "enabled": os.getenv("REMOTE_SERVERS_ENABLED", "false").lower() == "true",
                    "servers": [
                        {
                            "name": os.getenv("REMOTE_SERVER_NAME", "remote"),
                            "url": os.getenv("REMOTE_SERVER_URL", ""),
                            "prefix": os.getenv("REMOTE_SERVER_PREFIX", "remote"),
                            "type": os.getenv("REMOTE_SERVER_TYPE", "mount")  # 'mount' or 'proxy'
                        }
                    ]
                }
            }
    
    @property
    def server_name(self) -> str:
        return self.config["server"]["name"]
    
    @property
    def server_port(self) -> int:
        return self.config["server"]["port"]
    
    @property
    def server_url(self) -> str:
        return self.config["server"]["url"]
    
    @property
    def cors_origins(self) -> List[str]:
        return self.config["cors"]["origins"]
    
    @property
    def cors_methods(self) -> List[str]:
        return self.config["cors"]["methods"]
    
    @property
    def cors_headers(self) -> List[str]:
        return self.config["cors"]["headers"]
    
    @property
    def groq_api_key(self) -> str:
        return self.config["groq"]["api_key"]
    
    @property
    def groq_model(self) -> str:
        return self.config["groq"]["model"]
    
    @property
    def remote_servers_enabled(self) -> bool:
        return self.config["remote_servers"]["enabled"]
    
    @property
    def remote_servers(self) -> List[Dict[str, str]]:
        return self.config["remote_servers"]["servers"]

config = Config()

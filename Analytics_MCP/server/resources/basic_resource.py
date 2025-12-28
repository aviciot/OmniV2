# resources/basic_resource.py
"""Simple example resource demonstrating MCP resource functionality."""

from datetime import datetime
from mcp_app import mcp
from config import config


@mcp.resource("server://info/status")
def get_server_status() -> dict:
    """
    Provides current server status and configuration.
    
    This demonstrates how resources work in MCP - they provide
    dynamic data that can be accessed via URI patterns.
    
    Returns:
        Dictionary containing server status information
    """
    return {
        "server_name": config.server_name,
        "server_port": config.server_port,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "tools": "enabled",
            "resources": "enabled", 
            "prompts": "enabled"
        },
        "endpoints": {
            "health": "/healthz",
            "info": "/_info",
            "mcp": "/"
        }
    }


@mcp.resource("data://examples/{category}")
def get_example_data(category: str) -> str:
    """
    Provides example data based on category.
    
    This shows how to use URI parameters in resources.
    
    Args:
        category: The category of examples to retrieve
        
    Returns:
        Example data as a formatted string
    """
    examples = {
        "tools": """
# Tool Examples

1. greet_user - Simple greeting function
2. add_numbers - Basic arithmetic
3. calculate_percentage - Percentage calculations

Tools are functions that can be called by AI agents to perform actions.
""",
        "prompts": """
# Prompt Examples

1. code_review_checklist - Structured code review
2. debug_strategy - Systematic debugging approach
3. explain_concept - Technical concept explanation

Prompts provide structured templates for AI interactions.
""",
        "resources": """
# Resource Examples

1. server://info/status - Server status information
2. data://examples/{category} - Dynamic example data

Resources provide data that can be accessed via URI patterns.
They're like RESTful endpoints but for AI agents.
"""
    }
    
    return examples.get(
        category.lower(),
        f"No examples found for category: {category}\n\nAvailable categories: tools, prompts, resources"
    )

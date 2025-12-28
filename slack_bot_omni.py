"""
Slack Bot for OMNI2 Bridge
Routes natural language queries from Slack to OMNI2 for intelligent MCP orchestration
"""
import os
import re
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import json
import yaml
from typing import Optional
from pathlib import Path

# Import ThreadManager from same directory
from thread_manager import ThreadManager

# ============================================================================
# CONFIGURATION
# ============================================================================
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
OMNI2_URL = os.environ.get("OMNI2_URL", "http://localhost:8000")

# Load Slack configuration (optional - use defaults if not found)
CONFIG_DIR = Path("config")
SLACK_CONFIG = {}
USER_INFO_CONFIG = {}

try:
    config_file = CONFIG_DIR / "slack.yaml"
    if config_file.exists():
        with open(config_file, "r") as f:
            SLACK_CONFIG = yaml.safe_load(f)
        USER_INFO_CONFIG = SLACK_CONFIG.get("user_info_display", {})
        print(f"✅ Loaded Slack config from {config_file}")
    else:
        print(f"⚠️  Config file not found: {config_file}, using defaults")
        # Default configuration
        USER_INFO_CONFIG = {
            "enabled": True,
            "format": "standard",
            "show_in_dm": True,
            "show_in_channels": False,
            "show_in_threads": True,
            "elements": {
                "show_name": True,
                "show_role": True,
                "show_mcp_count": True,
                "show_mcp_names": False
            },
            "role_emojis": {
                "admin": "👑",
                "dba": "🔧",
                "power_user": "⚡",
                "qa_tester": "🧪",
                "read_only": "👁️",
                "default": "👤"
            }
        }
except Exception as e:
    print(f"⚠️  Failed to load config: {e}, using defaults")
    USER_INFO_CONFIG = {
        "enabled": True,
        "format": "standard",
        "show_in_dm": True,
        "show_in_channels": False,
        "show_in_threads": True,
        "elements": {
            "show_name": True,
            "show_role": True,
            "show_mcp_count": True
        },
        "role_emojis": {"admin": "👑", "dba": "🔧", "power_user": "⚡", "default": "👤"}
    }

# Default user if Slack Progressive loading  doesn't return email
DEFAULT_USER = os.environ.get("DEFAULT_USER_EMAIL", "default@company.com")

# Initialize Slack app
app = App(token=SLACK_BOT_TOKEN)

# ============================================================================
# THREAD MANAGER
# ============================================================================
# Load threading configuration
THREADING_CONFIG = {}
try:
    threading_config_file = CONFIG_DIR / "threading.yaml"
    if threading_config_file.exists():
        with open(threading_config_file, "r") as f:
            THREADING_CONFIG = yaml.safe_load(f)
        print(f"✅ Loaded threading config from {threading_config_file}")
    else:
        print(f"⚠️  Threading config not found: {threading_config_file}, using defaults")
        THREADING_CONFIG = {
            "threading": {"enabled": True, "behavior": {"always_use_threads": True}},
            "context": {"enabled": True, "max_messages": 3}
        }
except Exception as e:
    print(f"⚠️  Failed to load threading config: {e}, using defaults")
    THREADING_CONFIG = {
        "threading": {"enabled": True, "behavior": {"always_use_threads": True}},
        "context": {"enabled": True, "max_messages": 3}
    }

# Initialize ThreadManager with config
thread_manager = ThreadManager(THREADING_CONFIG)
print(f"✅ ThreadManager initialized (threading {'enabled' if THREADING_CONFIG.get('threading', {}).get('enabled') else 'disabled'})")

# ============================================================================
# OMNI2 CLIENT
# ============================================================================
class OMNI2Client:
    """Client to interact with OMNI2 Bridge"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
    
    def ask(self, user_email: str, message: str, slack_context: dict = None, conversation_context: str = None) -> dict:
        """
        Send natural language query to OMNI2
        
        Args:
            user_email: User's email (for permissions)
            message: Natural language question
            slack_context: Slack metadata (user_id, channel, message_ts, thread_ts)
            conversation_context: Previous conversation history for context
            
        Returns:
            Response from OMNI2 with answer and metadata
        """
        # Prepend conversation context if provided
        if conversation_context:
            message = f"{conversation_context}\n\nCurrent Question: {message}"
        
        payload = {
            "user_id": user_email,
            "message": message,
            "slack_context": slack_context  # Include Slack metadata
        }
        
        # Add custom header to identify Slack bot
        headers = self.headers.copy()
        headers["X-Source"] = "slack-bot"
        
        # Add custom header to identify Slack bot
        headers = self.headers.copy()
        headers["X-Source"] = "slack-bot"
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/ask",
                headers=headers,
                json=payload,
                timeout=60  # Longer timeout for complex queries
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out after 60 seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def health_check(self) -> dict:
        """Check OMNI2 health"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Ensure it's always a dict
                if isinstance(data, str):
                    return {"status": data}
                return data
            return {"status": "unhealthy"}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}
    
    def get_user_info(self, user_email: str) -> dict:
        """
        Fetch user information from OMNI2
        
        Args:
            user_email: User's email address
            
        Returns:
            Dict with user info: role, allowed_mcps, permissions, etc.
        """
        try:
            response = requests.get(
                f"{self.base_url}/users/{user_email}",
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback - extract from config or return default
                return {
                    "email": user_email,
                    "role": "unknown",
                    "allowed_mcps": [],
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "email": user_email,
                "role": "unknown",
                "allowed_mcps": [],
                "error": str(e)
            }
            return {"status": "unreachable", "error": str(e)}
    
    def get_mcp_tools(self, user_email: str, mcp_name: str) -> dict:
        """
        Get tools available for a specific MCP and user
        
        Args:
            user_email: User's email address
            mcp_name: Name of the MCP server
            
        Returns:
            Dict with tools list and MCP info
        """
        try:
            response = requests.get(
                f"{self.base_url}/mcp/tools/mcps/{mcp_name}/tools",
                headers=self.headers,
                params={"user_email": user_email},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "mcp_name": mcp_name,
                    "tools": [],
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "mcp_name": mcp_name,
                "tools": [],
                "error": str(e)
            }

# Initialize OMNI2 client
omni = OMNI2Client(OMNI2_URL)

# ============================================================================
# USER INFO FORMATTING
# ============================================================================

def format_user_info_header(user_email: str, user_info: dict, channel_type: str = "dm") -> Optional[str]:
    """
    Format user info header based on configuration
    
    Args:
        user_email: User's email
        user_info: User info dict from OMNI2
        channel_type: Type of channel (dm, channel, thread)
        
    Returns:
        Formatted header string or None if disabled
    """
    if not USER_INFO_CONFIG.get("enabled", False):
        return None
    
    # Check if we should show in this context
    if channel_type == "dm" and not USER_INFO_CONFIG.get("show_in_dm", True):
        return None
    if channel_type == "channel" and not USER_INFO_CONFIG.get("show_in_channels", False):
        return None
    if channel_type == "thread" and not USER_INFO_CONFIG.get("show_in_threads", True):
        return None
    
    format_type = USER_INFO_CONFIG.get("format", "standard")
    elements = USER_INFO_CONFIG.get("elements", {})
    role_emojis = USER_INFO_CONFIG.get("role_emojis", {})
    
    # Extract user data
    role = user_info.get("role", "unknown")
    name = user_info.get("name", user_email.split("@")[0])
    allowed_mcps = user_info.get("allowed_mcps", [])
    mcp_count = len(allowed_mcps) if isinstance(allowed_mcps, list) else 0
    if allowed_mcps == "*":
        mcp_count = "all"
    
    # Get role emoji
    role_emoji = role_emojis.get(role, role_emojis.get("default", "👤"))
    
    # Format based on config
    if format_type == "minimal":
        # Just emoji + role
        return f"{role_emoji} {role.replace('_', ' ').title()}"
    
    elif format_type == "standard":
        # Name + role in parentheses
        parts = []
        if elements.get("show_name", True):
            parts.append(f"👤 {name}")
        if elements.get("show_role", True):
            parts.append(f"({role_emoji} {role.replace('_', ' ').title()})")
        return " ".join(parts) if parts else None
    
    elif format_type == "detailed":
        # Full details with MCPs
        parts = []
        if elements.get("show_name", True):
            parts.append(f"👤 {name}")
        if elements.get("show_role", True):
            parts.append(f"Role: {role_emoji} {role.replace('_', ' ').title()}")
        if elements.get("show_mcp_count", True):
            if mcp_count == "all":
                parts.append(f"MCPs: All Available")
            else:
                parts.append(f"MCPs: {mcp_count} available")
        if elements.get("show_mcp_names", False) and isinstance(allowed_mcps, list):
            mcp_names = ", ".join(allowed_mcps[:3])
            if len(allowed_mcps) > 3:
                mcp_names += f" +{len(allowed_mcps) - 3} more"
            parts.append(f"({mcp_names})")
        
        return " | ".join(parts) if parts else None
    
    return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_email(slack_user_id: str, client=None) -> tuple[str, dict]:
    """
    Get user email from Slack API
    
    Args:
        slack_user_id: Slack user ID (U1234567890)
        client: Slack client to fetch user info
        
    Returns:
        Tuple of (email, user_info_dict)
    """
    user_info = {
        "slack_user_id": slack_user_id,
        "slack_email": None,
        "slack_real_name": None,
        "source": None,
        "warning": None
    }
    
    # Fetch from Slack API
    if client:
        try:
            response = client.users_info(user=slack_user_id)
            if response["ok"]:
                user_data = response["user"]
                slack_email = user_data.get("profile", {}).get("email")
                real_name = user_data.get("real_name", "Unknown")
                
                user_info["slack_email"] = slack_email
                user_info["slack_real_name"] = real_name
                
                if slack_email:
                    user_info["source"] = "slack_api"
                    print(f"✅ User identified via Slack API: {real_name} ({slack_user_id}) → {slack_email}")
                    return slack_email, user_info
                else:
                    user_info["warning"] = "No email in Slack profile"
                    print(f"⚠️  User {real_name} ({slack_user_id}) has no email in Slack profile")
        except Exception as e:
            user_info["warning"] = f"Slack API error: {str(e)}"
            print(f"⚠️  Failed to fetch Slack user info for {slack_user_id}: {e}")
    
    # Fallback to default
    user_info["source"] = "default_fallback"
    user_info["warning"] = f"Slack API didn't return email for {slack_user_id}"
    print(f"⚠️  Using default user: {DEFAULT_USER}")
    print(f"💡 Ensure bot has 'users:read' and 'users:read.email' OAuth scopes")
    
    return DEFAULT_USER, user_info


def format_response(result: dict, user_email: str = None, channel_type: str = "dm", include_feedback: bool = False) -> dict:
    """
    Format OMNI2 response into Slack blocks
    
    Args:
        result: OMNI2 response dictionary
        user_email: User's email (for fetching user info)
        channel_type: Type of channel (dm, channel, thread)
        include_feedback: Whether to include feedback buttons
        
    Returns:
        Slack blocks for rich formatting
    """
    blocks = []
    
    # Add user info header if enabled
    if user_email and USER_INFO_CONFIG.get("enabled", False):
        try:
            user_info = omni.get_user_info(user_email)
            user_header = format_user_info_header(user_email, user_info, channel_type)
            
            if user_header:
                # Add user info as a context block
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": user_header}]
                })
                # Add a subtle divider
                blocks.append({"type": "divider"})
        except Exception as e:
            print(f"⚠️  Failed to fetch user info for header: {e}")
    
    if result.get("success"):
        # Success response
        answer = result.get("answer", "No response")
        tool_calls = result.get("tool_calls", 0)
        tools_used = result.get("tools_used", [])
        iterations = result.get("iterations", 1)
        warning = result.get("warning")
        
        # Main answer
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": answer
            }
        })
        
        # Diagnostic info (if enabled in config)
        diagnostic_config = SLACK_CONFIG.get("diagnostic_info", {})
        if diagnostic_config.get("enabled", False):
            # Show diagnostic information
            diagnostic_text = "🔧 *Behind the scenes:*\n"
            
            if diagnostic_config.get("show_iterations", True):
                diagnostic_text += f"• Iterations: {iterations}\n"
            
            if diagnostic_config.get("show_tool_calls", True):
                diagnostic_text += f"• Tool calls: {tool_calls}\n"
            
            if diagnostic_config.get("show_mcp_choices", True) and tools_used:
                tools_list = ", ".join([f"`{t}`" for t in tools_used[:5]])
                diagnostic_text += f"• Tools used: {tools_list}\n"
            
            # Check if we should show diagnostics in this context
            show_diagnostic = False
            if channel_type == "dm" and diagnostic_config.get("show_in_dm", True):
                show_diagnostic = True
            elif channel_type == "channel" and diagnostic_config.get("show_in_channels", False):
                show_diagnostic = True
            
            if show_diagnostic:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": diagnostic_text}]
                })
        else:
            # Standard metadata (always shown if diagnostic mode is off)
            metadata_text = f"🔧 *Tools used:* {tool_calls} | 🔄 *Iterations:* {iterations}"
            if tools_used:
                tools_list = ", ".join([f"`{t}`" for t in tools_used[:5]])
                metadata_text += f"\n📦 {tools_list}"
            
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": metadata_text}]
            })
        
        # Warning if any
        if warning:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *Warning:* {warning}"
                }
            })
        
        # Add feedback buttons if enabled
        if include_feedback:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "👍",
                            "emoji": True
                        },
                        "value": "positive",
                        "action_id": "feedback_positive"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "👎",
                            "emoji": True
                        },
                        "value": "negative",
                        "action_id": "feedback_negative"
                    }
                ]
            })
    else:
        # Error response
        error_msg = result.get("error", "Unknown error")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *Error:*\n```{error_msg}```"
            }
        })
    
    return {"blocks": blocks}


# ============================================================================
# SLASH COMMANDS
# ============================================================================

@app.command("/omni")
def handle_omni_command(ack, command, respond, client):
    """
    Main OMNI2 slash command
    Usage: /omni <natural language question>
    
    Examples:
    - /omni Show database health for transformer_master
    - /omni What are the top 10 slowest queries?
    - /omni Search GitHub for FastMCP repositories
    - /omni Show me cost summary for today (admin only)
    """
    ack()
    
    try:
        message = command['text'].strip()
        slack_user_id = command['user_id']
        slack_channel = command.get('channel_id')
        
        # Enhanced user identification with detailed logging
        user_email, user_info = get_user_email(slack_user_id, client)
        
        # Log user identification details
        print(f"\n{'='*60}")
        print(f"👤 USER IDENTIFICATION")
        print(f"{'='*60}")
        print(f"Slack User ID: {user_info['slack_user_id']}")
        print(f"Real Name:     {user_info.get('slack_real_name', 'N/A')}")
        print(f"Slack Email:   {user_info.get('slack_email', 'N/A')}")
        print(f"Mapped Email:  {user_info.get('mapped_email', 'N/A')}")
        print(f"Final Email:   {user_email}")
        print(f"Source:        {user_info['source']}")
        if user_info.get('warning'):
            print(f"⚠️  Warning:      {user_info['warning']}")
        print(f"{'='*60}\n")
        
        # Build Slack context
        slack_context = {
            "slack_user_id": slack_user_id,
            "slack_channel": slack_channel,
            "slack_real_name": user_info.get('slack_real_name'),
            "command": "/omni"
        }
        
        print(f"📨 Received /omni command from {user_email}: {message[:50]}...")
        
        if not message:
            respond({
                "text": "❓ Please provide a question after `/omni`\n\n*Examples:*\n"
                        "• `/omni Show database health for transformer_master`\n"
                        "• `/omni What are the top 10 slowest queries?`\n"
                        "• `/omni Search GitHub for Python MCP servers`"
            })
            return
        
        # Show user mapping warning if using default
        warning_msg = ""
        if user_info['source'] == 'default_fallback' and user_info.get('warning'):
            warning_msg = (
                f"\n\n⚠️ *Note:* Could not fetch your email from Slack. "
                f"Using default user permissions.\n"
                f"Contact admin to verify bot has 'users:read.email' scope."
            )
        
        # Progressive Loading: Post initial message and get timestamp
        initial_response = respond(f"🔄 Processing your question...\n> {message}{warning_msg}")
        
        # Extract message timestamp for updates (use response metadata if available)
        # Slack's respond() may return the message, or we need to track it differently
        # For slash commands, we'll use a different approach with chat.postMessage
        try:
            # Post a message to the channel to get message_ts
            initial_msg = client.chat_postMessage(
                channel=slack_channel,
                text=f"🔄 Processing your question...\n> {message}{warning_msg}"
            )
            message_ts = initial_msg["ts"]
            
            # Progressive Loading: Update to "Querying" state
            client.chat_update(
                channel=slack_channel,
                ts=message_ts,
                text=f"⚙️ Querying OMNI2...\n> {message}{warning_msg}"
            )
            
        except Exception as e:
            print(f"⚠️ Progressive loading failed: {e}, falling back to standard response")
            message_ts = None
        
        # Query OMNI2 with Slack context
        print(f"🔄 Calling OMNI2: {OMNI2_URL}/chat/ask")
        result = omni.ask(user_email, message, slack_context)
        print(f"✅ Got response from OMNI2: {result.get('success', False)}")
        
        # Determine channel type
        channel_type = "dm" if slack_channel.startswith("D") else "channel"
        
        # Format response with user info and feedback buttons
        formatted = format_response(
            result, 
            user_email=user_email, 
            channel_type=channel_type,
            include_feedback=True  # Enable feedback buttons
        )
        
        # Progressive Loading: Update with final result
        if message_ts:
            try:
                client.chat_update(
                    channel=slack_channel,
                    ts=message_ts,
                    **formatted
                )
            except Exception as e:
                print(f"⚠️ Failed to update message: {e}, posting new response")
                respond(**formatted)
        else:
            # Fallback: post new message
            respond(**formatted)
        
    except Exception as e:
        print(f"❌ Error in /omni command: {str(e)}")
        respond(f"❌ Unexpected error: {str(e)}")


@app.command("/omni-help")
def handle_help(ack, respond, command, client):
    """Show OMNI2 bot help - interactive with role-based access"""
    ack()
    
    # Get user email from Slack
    user_id = command.get("user_id")
    try:
        user_info_response = client.users_info(user=user_id)
        user_email = user_info_response["user"]["profile"].get("email", "unknown@example.com")
    except Exception as e:
        print(f"⚠️  Could not get user email: {e}")
        user_email = "unknown@example.com"
    
    print(f"📧 /omni-help called by: {user_email}")
    
    # Get user permissions from OMNI2
    user_perms = omni.get_user_info(user_email)
    role = user_perms.get("role", "read_only")
    allowed_mcps = user_perms.get("allowed_mcps", [])
    
    print(f"👤 User: {user_email}, Role: {role}, Allowed MCPs: {allowed_mcps}")
    
    # Handle dict format (new granular permissions)
    if isinstance(allowed_mcps, dict):
        # Extract MCP names from dict keys
        allowed_mcps = list(allowed_mcps.keys())
        print(f"🔧 Converted dict to list: {allowed_mcps}")
    
    # Handle "all" permissions
    if allowed_mcps == "*" or (isinstance(allowed_mcps, list) and "all" in allowed_mcps):
        print("🌟 User has 'all' permissions, fetching MCP list from health check...")
        # Get all MCPs from health check
        health = omni.health_check()
        if isinstance(health, dict) and health.get("status") == "healthy":
            # Check if mcps is a dict with servers key (new format)
            mcps_data = health.get("mcps", {})
            if isinstance(mcps_data, dict) and "servers" in mcps_data:
                servers_list = mcps_data.get("servers", [])
                if isinstance(servers_list, list):
                    # Filter for enabled and healthy MCPs
                    allowed_mcps = [
                        server.get("name") 
                        for server in servers_list 
                        if isinstance(server, dict) 
                        and server.get("enabled", False)
                        and server.get("status") == "healthy"
                    ]
                    print(f"✅ Fetched {len(allowed_mcps)} MCPs from health check: {allowed_mcps}")
                else:
                    allowed_mcps = []
                    print("⚠️  Servers list is not a list")
            # Fallback: old format where mcps is a direct list
            elif isinstance(mcps_data, list):
                allowed_mcps = [mcp.get("name") for mcp in mcps_data if isinstance(mcp, dict)]
                print(f"✅ Fetched {len(allowed_mcps)} MCPs (old format): {allowed_mcps}")
            else:
                allowed_mcps = []
                print(f"⚠️  Unexpected mcps format: {type(mcps_data)}")
        else:
            allowed_mcps = []
            print(f"⚠️  Health check failed or returned unexpected format: {health}")
    
    # Ensure allowed_mcps is a list
    if not isinstance(allowed_mcps, list):
        print(f"⚠️  allowed_mcps is not a list ({type(allowed_mcps)}), converting to empty list")
        allowed_mcps = []
    
    print(f"✅ Final MCP list for help: {allowed_mcps}")

    
    # Build help message
    help_text = f"""*🤖 OMNI2 Bot - Your Intelligent Assistant*

*Your Role:* `{role}`
*Access Level:* {len(allowed_mcps)} MCP server(s) available

*Main Command:*
`/omni <your question in natural language>`

*Quick Examples:*
• Database: `/omni Show top 10 slowest queries`
• GitHub: `/omni Search for FastMCP repositories`
• Analytics: `/omni Show cost summary for today` (admin only)

*Features:*
✅ Natural language queries
✅ Intelligent routing across multiple tools
✅ Role-based access control
✅ Full audit logging

*Your Available MCPs:*
"""
    
    # Build interactive buttons for each MCP
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": help_text}}
    ]
    
    if allowed_mcps:
        # Add buttons for each MCP
        button_elements = []
        for mcp_name in allowed_mcps[:5]:  # Limit to 5 buttons
            button_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": f"🔍 {mcp_name}"},
                "action_id": f"explore_mcp_{mcp_name}",
                "value": mcp_name
            })
        
        if button_elements:
            blocks.append({
                "type": "actions",
                "elements": button_elements
            })
        
        # If more than 5 MCPs, show remaining as text
        if len(allowed_mcps) > 5:
            remaining = allowed_mcps[5:]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_Also available: {', '.join(f'`{m}`' for m in remaining)}_"
                }
            })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚠️ _No MCPs available. Contact your administrator for access._"
            }
        })
    
    # Add footer
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "💡 _Click an MCP button above to see its available tools_"
        }]
    })
    
    respond(blocks=blocks)


@app.command("/omni-status")
def handle_status(ack, respond):
    """Check OMNI2 health and available MCPs"""
    ack()
    
    try:
        health = omni.health_check()
        
        if health.get("status") == "healthy":
            mcps_text = "No MCPs connected"
            
            # Handle new format: mcps is a dict with servers key
            mcps_data = health.get("mcps", {})
            if isinstance(mcps_data, dict) and "servers" in mcps_data:
                servers_list = mcps_data.get("servers", [])
                if isinstance(servers_list, list) and servers_list:
                    mcp_list = []
                    for mcp in servers_list:
                        if isinstance(mcp, dict):
                            status_emoji = "✅" if mcp.get("status") == "healthy" else "❌"
                            enabled_text = "" if mcp.get("enabled", False) else " (disabled)"
                            mcp_list.append(f"{status_emoji} `{mcp.get('name', 'unknown')}` ({mcp.get('tools', 0)} tools){enabled_text}")
                    if mcp_list:
                        mcps_text = "\n".join(mcp_list)
            # Fallback: old format where mcps is a direct list
            elif isinstance(mcps_data, list):
                mcp_list = []
                for mcp in mcps_data:
                    if isinstance(mcp, dict):
                        status_emoji = "✅" if mcp.get("status") == "healthy" else "❌"
                        mcp_list.append(f"{status_emoji} `{mcp.get('name', 'unknown')}` ({mcp.get('tools', 0)} tools)")
                    else:
                        mcp_list.append(f"• `{mcp}`")
                if mcp_list:
                    mcps_text = "\n".join(mcp_list)
            
            respond({
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ OMNI2 Status: Healthy"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Connected MCPs:*\n{mcps_text}"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f"URL: {OMNI2_URL}"}
                        ]
                    }
                ]
            })
        else:
            respond(f"❌ OMNI2 is {health.get('status', 'unknown')}\nURL: {OMNI2_URL}")
    
    except Exception as e:
        respond(f"❌ Error checking status: {str(e)}")


# ============================================================================
# APP MENTIONS & DMs
# ============================================================================

@app.event("app_mention")
def handle_mention(event, say, client):
    """
    Handle @bot mentions for natural language queries
    Example: @OMNI2Bot show me database health
    """
    try:
        # Remove bot mention from text
        text = event['text']
        # Remove <@BOTID> pattern
        import re
        text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        if not text:
            say("👋 Hi! Ask me anything using `/omni <your question>`")
            return
        
        slack_user_id = event['user']
        slack_channel = event.get('channel')
        message_ts = event.get('ts')
        thread_ts = event.get('thread_ts')  # Get existing thread if any
        
        # Enhanced user identification
        user_email, user_info = get_user_email(slack_user_id, client)
        
        # Log user identification
        print(f"\n{'='*60}")
        print(f"👤 APP MENTION - USER IDENTIFICATION")
        print(f"{'='*60}")
        print(f"Slack User ID: {user_info['slack_user_id']}")
        print(f"Real Name:     {user_info.get('slack_real_name', 'N/A')}")
        print(f"Final Email:   {user_email}")
        print(f"Source:        {user_info['source']}")
        print(f"{'='*60}\n")
        
        # Determine if we should use threading
        channel_type = "channel"  # app_mention is always in a channel
        use_thread = thread_manager.should_use_thread(channel_type, thread_ts)
        
        # Get or create thread for context
        if use_thread:
            thread_ts = thread_manager.get_or_create_thread(
                thread_ts or message_ts,  # Use existing thread or start new
                slack_user_id,
                slack_channel,
                channel_type
            )
            
            # Add user message to thread history
            thread_manager.add_user_message(thread_ts, text, slack_user_id)
            
            # Get conversation context
            conversation_context = thread_manager.get_context_for_message(
                text, thread_ts, slack_user_id, slack_channel, channel_type
            )
        else:
            conversation_context = None
        
        # Build Slack context
        slack_context = {
            "slack_user_id": slack_user_id,
            "slack_channel": slack_channel,
            "slack_message_ts": message_ts,
            "slack_thread_ts": thread_ts,
            "event_type": "app_mention"
        }
        
        # Query OMNI2 with Slack context and conversation history
        result = omni.ask(user_email, text, slack_context, conversation_context)
        
        # Add assistant response to thread history
        if use_thread:
            assistant_message = result.get('answer', 'Error processing request')
            thread_manager.add_assistant_message(thread_ts, assistant_message)
        
        # Format and send response in thread
        formatted = format_response(result)
        say(
            **formatted,
            thread_ts=thread_ts  # Reply in thread
        )
    
    except Exception as e:
        say(f"❌ Error: {str(e)}", thread_ts=event.get('thread_ts', event.get('ts')))


@app.event("message")
def handle_dm(event, say, client):
    """
    Handle direct messages to the bot
    """
    # Only handle DMs (channel_type == "im")
    if event.get('channel_type') == 'im' and 'bot_id' not in event:
        try:
            text = event['text'].strip()
            
            if not text:
                return
            
            # Special commands
            if text.lower() in ['help', 'hi', 'hello']:
                say("👋 Hi! Send me any question and I'll route it to OMNI2.\n\nTry: `Show database health for transformer_master`")
                return
            
            slack_user_id = event['user']
            slack_channel = event.get('channel')
            message_ts = event.get('ts')
            thread_ts = event.get('thread_ts')  # DMs can have threads too
            
            # Enhanced user identification
            user_email, user_info = get_user_email(slack_user_id, client)
            
            # Log user identification
            print(f"\n{'='*60}")
            print(f"👤 DM - USER IDENTIFICATION")
            print(f"{'='*60}")
            print(f"Slack User ID: {user_info['slack_user_id']}")
            print(f"Real Name:     {user_info.get('slack_real_name', 'N/A')}")
            print(f"Final Email:   {user_email}")
            print(f"Source:        {user_info['source']}")
            print(f"{'='*60}\n")
            
            # Determine if we should use threading (DMs typically don't, but can be configured)
            channel_type = "dm"
            use_thread = thread_manager.should_use_thread(channel_type, thread_ts)
            
            # Get conversation context for DMs (even without threads, we track context)
            conversation_context = thread_manager.get_context_for_message(
                text, thread_ts, slack_user_id, slack_channel, channel_type
            )
            
            # Add user message to history
            if use_thread and thread_ts:
                thread_manager.add_user_message(thread_ts, text, slack_user_id)
            
            # Build Slack context
            slack_context = {
                "slack_user_id": slack_user_id,
                "slack_channel": slack_channel,
                "slack_message_ts": message_ts,
                "slack_thread_ts": thread_ts,
                "event_type": "direct_message"
            }
            
            # Query OMNI2 with Slack context and conversation history
            result = omni.ask(user_email, text, slack_context, conversation_context)
            
            # Add assistant response to history
            if use_thread and thread_ts:
                assistant_message = result.get('answer', 'Error processing request')
                thread_manager.add_assistant_message(thread_ts, assistant_message)
            
            # Format and send response
            formatted = format_response(result)
            response_kwargs = formatted
            if thread_ts:
                response_kwargs['thread_ts'] = thread_ts
            say(**response_kwargs)
        
        except Exception as e:
            say(f"❌ Error: {str(e)}")


# ============================================================================
# FEEDBACK BUTTON HANDLERS
# ============================================================================

@app.action("feedback_positive")
def handle_positive_feedback(ack, body, client):
    """Handle thumbs up feedback"""
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        
        # Log feedback
        print(f"👍 Positive feedback from {user_id} on message {message_ts}")
        
        # Update the button to show feedback received
        # Get current blocks and replace the action block
        original_blocks = body["message"]["blocks"]
        updated_blocks = []
        
        for block in original_blocks:
            if block.get("type") == "actions":
                # Replace with confirmation message
                updated_blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": "✅ *Thanks for your feedback!* Your input helps improve OMNI2."
                    }]
                })
            else:
                updated_blocks.append(block)
        
        # Update the message
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=updated_blocks
        )
        
        # TODO: Store feedback in analytics database
        # This can be implemented later to track response quality
        
    except Exception as e:
        print(f"❌ Error handling positive feedback: {e}")


@app.action("feedback_negative")
def handle_negative_feedback(ack, body, client):
    """Handle thumbs down feedback"""
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        
        # Log feedback
        print(f"👎 Negative feedback from {user_id} on message {message_ts}")
        
        # Update the button to show feedback received
        original_blocks = body["message"]["blocks"]
        updated_blocks = []
        
        for block in original_blocks:
            if block.get("type") == "actions":
                # Replace with confirmation and ask for details
                updated_blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": "📝 *Thanks for your feedback!* We'll work on improving this response."
                    }]
                })
            else:
                updated_blocks.append(block)
        
        # Update the message
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=updated_blocks
        )
        
        # TODO: Store feedback in analytics database
        # Consider asking user for optional details via modal
        
    except Exception as e:
        print(f"❌ Error handling negative feedback: {e}")



# ============================================================================
# MCP EXPLORATION HANDLERS (Interactive Help)
# ============================================================================

@app.action(re.compile("explore_mcp_.*"))
def handle_explore_mcp(ack, body, respond, client):
    """Handle MCP exploration button clicks from /omni-help"""
    ack()
    
    # Extract MCP name from action_id (format: "explore_mcp_<mcp_name>")
    action_id = body["actions"][0]["action_id"]
    mcp_name = action_id.replace("explore_mcp_", "")
    
    print(f"🔍 Button clicked for MCP: {mcp_name}")
    print(f"📦 Body keys: {body.keys()}")
    
    # Get user email
    user_id = body["user"]["id"]
    try:
        user_info_response = client.users_info(user=user_id)
        user_email = user_info_response["user"]["profile"].get("email", "unknown@example.com")
    except Exception as e:
        print(f"⚠️  Could not get user email: {e}")
        user_email = "unknown@example.com"
    
    # Get tools for this MCP
    mcp_tools = omni.get_mcp_tools(user_email, mcp_name)
    
    if "error" in mcp_tools:
        # Show error message
        response_text = f"*🔍 {mcp_name}*\n\n⚠️ Could not load tools: {mcp_tools['error']}"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": response_text}}
        ]
    else:
        tools = mcp_tools.get("tools", [])
        
        if not tools:
            response_text = f"*🔍 {mcp_name}*\n\n_No tools available for your role._"
            blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": response_text}}
            ]
        else:
            # Build tool list
            description = mcp_tools.get("description", f"Tools available in {mcp_name}")
            response_text = f"*🔍 {mcp_name}*\n_{description}_\n\n*Your Available Tools ({len(tools)}):*\n"
            
            # Group tools or show all if < 10
            if len(tools) <= 10:
                for tool in tools:
                    tool_name = tool.get("name", "unknown")
                    tool_desc = tool.get("description", "No description")
                    # Truncate description to keep it concise
                    if len(tool_desc) > 100:
                        tool_desc = tool_desc[:97] + "..."
                    response_text += f"\n• `{tool_name}`\n  _{tool_desc}_"
            else:
                # Show first 8 and summarize rest
                for tool in tools[:8]:
                    tool_name = tool.get("name", "unknown")
                    tool_desc = tool.get("description", "No description")
                    if len(tool_desc) > 80:
                        tool_desc = tool_desc[:77] + "..."
                    response_text += f"\n• `{tool_name}` - {tool_desc}"
                
                remaining_count = len(tools) - 8
                response_text += f"\n\n_...and {remaining_count} more tools_"
            
            # Add example usage
            if tools:
                example_tool = tools[0].get("name", "tool_name")
                response_text += f"\n\n*Example:*\n`/omni Use {mcp_name} to {example_tool}...`"
            
            blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": response_text}}
            ]
    
    # Send response as NEW message (don't replace original help menu)
    try:
        # Try using respond() with replace_original=False to keep the help menu visible
        print(f"� Sending tool list as new message...")
        respond(
            text=response_text,
            blocks=blocks,
            replace_original=False,
            response_type="ephemeral"
        )
        print(f"✅ Posted tools for {mcp_name}")
    except Exception as e:
        print(f"❌ Failed to post MCP tools: {e}")
        print(f"🔍 Error details: {type(e).__name__}: {str(e)}")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 OMNI2 Slack Bot Starting...")
    print(f"📍 OMNI2 URL: {OMNI2_URL}")
    print(f"👤 Default User: {DEFAULT_USER}")
    print(f"� Auth: Slack API (users:read.email)")
    print("=" * 60)
    
    # Test OMNI2 connection
    health = omni.health_check()
    if health.get("status") == "healthy":
        print("✅ OMNI2 is healthy")
        if "mcps" in health:
            mcps = health['mcps']
            print(f"📦 Connected MCPs: {len(mcps) if isinstance(mcps, list) else 0}")
            if isinstance(mcps, list):
                for mcp in mcps:
                    if isinstance(mcp, dict):
                        print(f"   • {mcp.get('name', 'unknown')}: {mcp.get('tools', 0)} tools")
                    else:
                        print(f"   • {mcp}")
    else:
        print(f"⚠️  OMNI2 status: {health.get('status', 'unknown')}")
    
    print("=" * 60)
    
    # Start the bot
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    print("⚡ Slack bot is running! Press Ctrl+C to stop.")
    handler.start()

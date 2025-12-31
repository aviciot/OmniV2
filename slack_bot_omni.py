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
import traceback
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


# ============================================================================
# FILE HANDLING
# ============================================================================

def download_slack_file(file_info: dict, client) -> Optional[dict]:
    """
    Download a file from Slack using the Slack SDK
    Supports ZIP file extraction
    
    Args:
        file_info: File info dict from Slack event
        client: Slack WebClient instance
        
    Returns:
        Dict with file_name and file_content, or None if failed
        For ZIP files, returns list of extracted files
    """
    import time
    import zipfile
    import io
    
    try:
        file_id = file_info.get('id')
        file_name = file_info.get('name', 'unknown.csv')
        is_zip = file_name.lower().endswith('.zip')
        
        print(f"📥 Downloading file: {file_name}")
        print(f"   File ID: {file_id}")
        
        # Try to get download URL (with fallback for missing files:read scope)
        url_private = None
        
        try:
            # Try files.info API (requires files:read scope)
            file_info_response = client.files_info(file=file_id)
            
            if file_info_response.get('ok'):
                file_data = file_info_response.get('file', {})
                url_private = file_data.get('url_private_download')
                print(f"   ✅ Got URL from files.info API")
            else:
                error = file_info_response.get('error', 'unknown')
                if error == 'missing_scope':
                    print(f"   ⚠️  Missing files:read scope - falling back to event URL")
                else:
                    print(f"   ⚠️  files.info failed ({error}) - falling back to event URL")
        except Exception as e:
            print(f"   ⚠️  files.info error: {str(e)[:100]} - falling back to event URL")
        
        # Fallback: Use URL from event (available without files:read scope)
        if not url_private:
            url_private = file_info.get('url_private_download') or file_info.get('url_private')
            if url_private:
                print(f"   Using URL from event")
            else:
                print(f"❌ No download URL available")
                return None
        
        # Download using requests with bot token
        # Note: Slack requires the token in Authorization header
        headers = {
            "Authorization": f"Bearer {client.token}"
        }
        
        print(f"   Downloading from: {url_private[:80]}...")
        response = requests.get(url_private, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Validate content
            content = response.content
            
            # Check if it's HTML (authentication failed)
            if content.startswith(b'<!DOCTYPE html>') or content.startswith(b'<html'):
                print(f"❌ Received HTML instead of file (auth may have failed)")
                print(f"   Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                return None
            
            # Handle ZIP files - extract and return CSV files
            if is_zip:
                print(f"📦 ZIP file detected, extracting...")
                try:
                    with zipfile.ZipFile(io.BytesIO(content)) as zip_ref:
                        csv_files_in_zip = [f for f in zip_ref.namelist() if f.lower().endswith('.csv')]
                        
                        if not csv_files_in_zip:
                            print(f"⚠️  No CSV files found in ZIP")
                            return None
                        
                        if len(csv_files_in_zip) > 2:
                            print(f"⚠️  ZIP contains {len(csv_files_in_zip)} CSV files, using first 2")
                            csv_files_in_zip = csv_files_in_zip[:2]
                        
                        extracted_files = []
                        for csv_file_name in csv_files_in_zip:
                            csv_content = zip_ref.read(csv_file_name)
                            try:
                                decoded_content = csv_content.decode('utf-8')
                            except UnicodeDecodeError:
                                decoded_content = csv_content.decode('latin-1')
                            
                            extracted_files.append({
                                "file_name": os.path.basename(csv_file_name),
                                "file_content": decoded_content,
                                "file_size": len(csv_content)
                            })
                            print(f"   ✅ Extracted: {os.path.basename(csv_file_name)} ({len(csv_content)} bytes)")
                        
                        # Return special marker for ZIP with extracted files
                        return {
                            "is_zip": True,
                            "zip_name": file_name,
                            "extracted_files": extracted_files
                        }
                        
                except zipfile.BadZipFile:
                    print(f"❌ Invalid ZIP file")
                    return None
            
            # Decode regular CSV content
            try:
                decoded_content = content.decode('utf-8')
            except UnicodeDecodeError:
                # Try other encodings
                try:
                    decoded_content = content.decode('latin-1')
                    print(f"⚠️  File decoded using latin-1 encoding")
                except:
                    print(f"❌ Failed to decode file content")
                    return None
            
            print(f"✅ Downloaded file: {file_name} ({len(content)} bytes)")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            return {
                "file_name": file_name,
                "file_content": decoded_content,
                "file_size": len(content)
            }
        else:
            print(f"❌ Download failed: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        import traceback
        traceback.print_exc()
        return None
        traceback.print_exc()
        return None


def detect_csv_files(event: dict) -> list:
    """
    Detect CSV and ZIP files attached to a Slack message
    
    Args:
        event: Slack event dict
        
    Returns:
        List of CSV/ZIP file info dicts
    """
    files = event.get('files', [])
    csv_files = []
    
    for file_info in files:
        file_name = file_info.get('name', '').lower()
        mimetype = file_info.get('mimetype', '')
        
        # Check if it's a CSV or ZIP file
        if file_name.endswith('.csv') or 'csv' in mimetype or file_name.endswith('.zip') or 'zip' in mimetype:
            csv_files.append(file_info)
    
    return csv_files


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
    
    # Add text fallback for accessibility
    answer_text = result.get("answer", "") if result.get("success") else result.get("error", "Error")
    return {"blocks": blocks, "text": answer_text[:3000]}  # Slack text limit


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
        if isinstance(health, dict) and health.get("status") in ["healthy", "degraded"]:
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
        
        # Detect files for comparison (CSV, PDF, etc.)
        comparison_files = detect_csv_files(event)  # TODO: Rename function to detect_comparison_files
        comparison_keywords = ['csv', 'compare', 'comparison', 'file', 'diff', 'difference']
        is_file_comparison_request = any(keyword in text.lower() for keyword in comparison_keywords)
        
        # Handle file comparison requests (CSV, PDF, etc.)
        if comparison_files and is_file_comparison_request:
            print(f"📎 Detected {len(comparison_files)} file(s) in message")
            
            # Validation 1: Must have exactly 2 files
            if len(comparison_files) < 2:
                say(
                    text="📊 *CSV Comparison - Upload 2 Files*\n\n❌ I found only **1 CSV file**.\n\n*To compare CSV files:*\n1. Upload **2 different CSV files** in one message\n2. Mention me with: `@omni_bot compare these files`\n\n💡 Both files must be attached to the same message!",
                    thread_ts=thread_ts or message_ts
                )
                return
            
            if len(comparison_files) > 2:
                say(
                    text=f"📊 *File Comparison - Multiple Files Detected*\n\n⚠️ I found **{len(comparison_files)} files**.\n\nI'll compare the first 2:\n• `{comparison_files[0]['name']}`\n• `{comparison_files[1]['name']}`\n\n💡 *Tip:* Upload only 2 files for clearer results.",
                    thread_ts=thread_ts or message_ts
                )
            
            # Download the first 2 CSV files (or ZIP)
            say(text="⏳ Downloading files...", thread_ts=thread_ts or message_ts)
            
            import time
            
            # Download files (handles ZIP extraction)
            downloaded_files = []
            
            file1 = download_slack_file(comparison_files[0], client)
            if file1:
                # Check if it's a ZIP with extracted files
                if file1.get('is_zip'):
                    say(text=f"📦 Extracted {len(file1['extracted_files'])} CSV files from {file1['zip_name']}", thread_ts=thread_ts or message_ts)
                    downloaded_files.extend(file1['extracted_files'])
                else:
                    downloaded_files.append(file1)
                time.sleep(0.5)
            
            # Only download second file if we don't have 2 files yet
            if len(downloaded_files) < 2 and len(comparison_files) > 1:
                file2 = download_slack_file(comparison_files[1], client)
                if file2:
                    if file2.get('is_zip'):
                        say(text=f"📦 Extracted {len(file2['extracted_files'])} CSV files from {file2['zip_name']}", thread_ts=thread_ts or message_ts)
                        downloaded_files.extend(file2['extracted_files'])
                    else:
                        downloaded_files.append(file2)
            
            # Validation: Need exactly 2 CSV files
            if len(downloaded_files) < 2:
                say(
                    text=f"❌ *Not enough CSV files*\n\nFound {len(downloaded_files)} CSV file(s), need 2.\n\n*Solution:* Upload 2 CSV files or a ZIP containing 2 CSV files.",
                    thread_ts=thread_ts or message_ts
                )
                return
            
            if len(downloaded_files) > 2:
                say(
                    text=f"⚠️ Found {len(downloaded_files)} CSV files, comparing first 2:\n• `{downloaded_files[0]['file_name']}`\n• `{downloaded_files[1]['file_name']}`",
                    thread_ts=thread_ts or message_ts
                )
            
            # Use first 2 files
            file1 = downloaded_files[0]
            file2 = downloaded_files[1]
            
            # Create snapshot folder with test ID
            import os
            from pathlib import Path
            from datetime import datetime
            import json
            
            # Generate test ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_id = f"SMOKE_{timestamp}"
            
            # Create snapshot directory structure (maps to QA_MCP/data/snapshots)
            snapshots_base = Path("/app/data/snapshots")
            test_folder = snapshots_base / test_id
            test_folder.mkdir(parents=True, exist_ok=True)
            
            # Save files with descriptive names (preserve original extension)
            file1_ext = Path(file1['file_name']).suffix
            file2_ext = Path(file2['file_name']).suffix
            
            file1_name = f"file1{file1_ext}"
            file2_name = f"file2{file2_ext}"
            
            path1 = test_folder / file1_name
            path2 = test_folder / file2_name
            
            # Write CSV files to snapshot folder
            with open(path1, 'w', encoding='utf-8') as f:
                f.write(file1['file_content'])
            with open(path2, 'w', encoding='utf-8') as f:
                f.write(file2['file_content'])
            
            # Create metadata file
            metadata = {
                "test_id": test_id,
                "timestamp": datetime.now().isoformat(),
                "user": user_email,
                "slack_user": user_info.get('slack_real_name', 'Unknown'),
                "file1_original": file1['file_name'],
                "file2_original": file2['file_name'],
                "file1_size": file1['file_size'],
                "file2_size": file2['file_size'],
                "comparison_type": "smoke_test",
                "slack_channel": slack_channel,
                "slack_thread": thread_ts or message_ts
            }
            
            metadata_path = test_folder / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # For QA_MCP, use paths from its perspective (/app/data/snapshots/<test_id>/)
            qa_mcp_path1 = f"/app/data/snapshots/{test_id}/{file1_name}"
            qa_mcp_path2 = f"/app/data/snapshots/{test_id}/{file2_name}"
            
            # Enhance user message with test ID and file info (keep it concise for DB audit log)
            enhanced_text = f"Compare CSV files from test {test_id}: {qa_mcp_path1} vs {qa_mcp_path2}"
            
            print(f"📊 Test ID: {test_id}")
            print(f"📊 Comparing: {file1['file_name']} vs {file2['file_name']}")
            print(f"📁 Snapshot folder: {test_folder}")
            print(f"📝 Metadata saved: {metadata_path}")
            print(f"📝 QA_MCP paths: {qa_mcp_path1} and {qa_mcp_path2}")
            print(f"📝 Enhanced query: {enhanced_text}")
        else:
            enhanced_text = text
        
        # Determine if we should use threading
        channel_type = "channel"  # app_mention is always in a channel
        use_thread = thread_manager.should_use_thread(channel_type, thread_ts)
        
        print(f"🧵 Threading Decision: use_thread={use_thread}, channel_type={channel_type}, existing_thread_ts={thread_ts}")
        
        # Get or create thread for context
        if use_thread:
            # Ensure thread_ts is set (use message_ts if starting new thread)
            if not thread_ts:
                thread_ts = message_ts
            
            # Create thread context in manager
            thread_manager.get_or_create_thread(
                thread_ts,
                slack_channel,
                slack_user_id
            )
            
            print(f"🧵 Thread TS: {thread_ts}")
            
            # Add user message to thread history (use original text, not enhanced)
            thread_manager.add_user_message(thread_ts, slack_channel, slack_user_id, text, message_ts)
            
            # Get conversation context
            conversation_context = thread_manager.get_context_for_message(
                text, thread_ts, slack_user_id, slack_channel, channel_type
            )
            
            # Count messages in thread
            thread = thread_manager._threads.get(thread_ts)
            msg_count = len(thread.messages) if thread else 0
            print(f"🧵 Context: {len(conversation_context) if conversation_context else 0} chars, {msg_count} messages in thread")
        else:
            conversation_context = None
            print(f"🧵 Threading disabled, no context")
        
        # Build Slack context
        slack_context = {
            "slack_user_id": slack_user_id,
            "slack_channel": slack_channel,
            "slack_message_ts": message_ts,
            "slack_thread_ts": thread_ts,
            "event_type": "app_mention"
        }
        
        # Query OMNI2 with Slack context and conversation history (use enhanced_text for CSV files)
        result = omni.ask(user_email, enhanced_text, slack_context, conversation_context)
        
        # Cleanup: Remove snapshot folder after processing (optional - keep for historical analysis)
        # Note: We're keeping snapshots for now to enable historical analysis
        # Auto-cleanup will be handled by a separate background job based on retention policy
        if comparison_files and is_file_comparison_request and 'test_id' in locals():
            print(f"📦 Snapshot preserved: {test_id} (for historical analysis)")
            # Uncomment below to enable immediate cleanup:
            # try:
            #     import shutil
            #     if test_folder.exists():
            #         shutil.rmtree(test_folder)
            #     print(f"🧹 Cleaned up snapshot folder: {test_id}")
            # except Exception as cleanup_error:
            #     print(f"⚠️  Failed to cleanup snapshot folder: {cleanup_error}")
        
        print(f"🧵 OMNI2 Response received, success={result.get('success', False)}")
        
        # Format and send response in thread
        formatted = format_response(result)
        response = say(
            **formatted,
            thread_ts=thread_ts  # Reply in thread
        )
        
        # Upload detailed report file if available (for file comparisons)
        if result.get('success') and comparison_files and is_file_comparison_request:
            print(f"🔍 Checking for report file...")
            print(f"   Result keys: {result.keys()}")
            
            # Check if there's a report_path in the tool results
            tool_results = result.get('tool_results', [])
            print(f"   Tool results count: {len(tool_results)}")
            
            for tool_result in tool_results:
                print(f"   Tool: {tool_result.get('tool')}")
                
                # Get the actual result data from the tool
                result_data = tool_result.get('result', {})
                print(f"   Result data keys: {result_data.keys() if isinstance(result_data, dict) else type(result_data)}")
                
                if isinstance(result_data, dict) and 'report_path' in result_data:
                    report_path = result_data['report_path']
                    print(f"   Found report_path: {report_path}")
                    if os.path.exists(report_path):
                        try:
                            # Upload the report file to Slack
                            client.files_upload_v2(
                                channel=slack_channel,
                                file=report_path,
                                title="CSV Comparison Detailed Report",
                                initial_comment="📊 Detailed comparison report attached",
                                thread_ts=thread_ts
                            )
                            print(f"📤 Uploaded detailed report: {report_path}")
                        except Exception as upload_error:
                            print(f"⚠️  Failed to upload report file: {upload_error}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"⚠️  Report file not found: {report_path}")
                    break
        
        # Add assistant response to thread history
        if use_thread and response:
            assistant_message = result.get('answer', 'Error processing request')
            response_ts = response.get('ts', response.get('message', {}).get('ts'))
            thread_manager.add_assistant_message(thread_ts, slack_channel, slack_user_id, assistant_message, response_ts)
            print(f"🧵 Added assistant response to thread history")
    
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
                thread_manager.add_user_message(thread_ts, slack_channel, slack_user_id, text, message_ts)
            
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
            
            # Format and send response
            formatted = format_response(result)
            response_kwargs = formatted
            if thread_ts:
                response_kwargs['thread_ts'] = thread_ts
            response = say(**response_kwargs)
            
            # Add assistant response to history
            if use_thread and thread_ts and response:
                assistant_message = result.get('answer', 'Error processing request')
                response_ts = response.get('ts', response.get('message', {}).get('ts'))
                thread_manager.add_assistant_message(thread_ts, slack_channel, slack_user_id, assistant_message, response_ts)
        
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"❌ ERROR in app_mention handler:\n{error_details}")
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

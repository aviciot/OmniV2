"""
Slack Bot for OMNI2 Bridge
Routes natural language queries from Slack to OMNI2 for intelligent MCP orchestration
"""
import os
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import json
from typing import Optional

# ============================================================================
# CONFIGURATION
# ============================================================================
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
OMNI2_URL = os.environ.get("OMNI2_URL", "http://localhost:8000")

# Slack User ID → Email mapping (configure based on your Slack workspace)
USER_MAPPING = {
    "U1234567890": "avicoiot@gmail.com",  # Example: replace with real Slack user IDs
    "U0987654321": "alonab@shift4.com",
    # Add more mappings as needed
}

# Default user if mapping not found
DEFAULT_USER = os.environ.get("DEFAULT_USER_EMAIL", "default@company.com")

# Initialize Slack app
app = App(token=SLACK_BOT_TOKEN)

# ============================================================================
# OMNI2 CLIENT
# ============================================================================
class OMNI2Client:
    """Client to interact with OMNI2 Bridge"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
    
    def ask(self, user_email: str, message: str) -> dict:
        """
        Send natural language query to OMNI2
        
        Args:
            user_email: User's email (for permissions)
            message: Natural language question
            
        Returns:
            Response from OMNI2 with answer and metadata
        """
        payload = {
            "user_id": user_email,
            "message": message
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/ask",
                headers=self.headers,
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
            return response.json() if response.status_code == 200 else {"status": "unhealthy"}
        except:
            return {"status": "unreachable"}

# Initialize OMNI2 client
omni = OMNI2Client(OMNI2_URL)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_email(slack_user_id: str) -> str:
    """
    Map Slack user ID to email address
    
    Args:
        slack_user_id: Slack user ID (U1234567890)
        
    Returns:
        User email address
    """
    return USER_MAPPING.get(slack_user_id, DEFAULT_USER)


def format_response(result: dict) -> dict:
    """
    Format OMNI2 response into Slack blocks
    
    Args:
        result: OMNI2 response dictionary
        
    Returns:
        Slack blocks for rich formatting
    """
    blocks = []
    
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
        
        # Metadata
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
def handle_omni_command(ack, command, respond):
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
        user_email = get_user_email(slack_user_id)
        
        if not message:
            respond({
                "text": "❓ Please provide a question after `/omni`\n\n*Examples:*\n"
                        "• `/omni Show database health for transformer_master`\n"
                        "• `/omni What are the top 10 slowest queries?`\n"
                        "• `/omni Search GitHub for Python MCP servers`"
            })
            return
        
        # Show thinking message
        respond(f"🤔 Processing your question...\n> {message}")
        
        # Query OMNI2
        result = omni.ask(user_email, message)
        
        # Format and send response
        formatted = format_response(result)
        respond(**formatted)
        
    except Exception as e:
        respond(f"❌ Unexpected error: {str(e)}")


@app.command("/omni-help")
def handle_help(ack, respond):
    """Show OMNI2 bot help"""
    ack()
    
    help_text = """*🤖 OMNI2 Bot - Your Intelligent Assistant*

*Main Command:*
`/omni <your question in natural language>`

*Database Queries:*
• `/omni Show database health for transformer_master`
• `/omni What are the top 10 slowest queries?`
• `/omni Show active sessions on way4_docker7`
• `/omni Analyze this query: SELECT * FROM users WHERE status = 'active'`

*GitHub Queries:*
• `/omni Search GitHub for FastMCP repositories`
• `/omni Find Python projects about AI agents`
• `/omni Show me the README of aviciot/MetaQuery-MCP`

*Analytics (Admin Only):*
• `/omni Show me cost summary for today`
• `/omni What are the most expensive queries this week?`
• `/omni Who are the most active users?`

*Features:*
✅ Natural language - ask like you would to a person
✅ Intelligent routing - OMNI2 picks the right tools automatically
✅ Multi-tool orchestration - can use multiple tools in one query
✅ Permission-aware - you only see tools you have access to

*Commands:*
• `/omni <question>` - Ask OMNI2 anything
• `/omni-help` - Show this help
• `/omni-status` - Check OMNI2 health

*Tips:*
💡 Be specific with database names, GitHub repos, etc.
💡 You can ask follow-up questions naturally
💡 OMNI2 logs all queries for audit and analytics
"""
    
    respond(help_text)


@app.command("/omni-status")
def handle_status(ack, respond):
    """Check OMNI2 health and available MCPs"""
    ack()
    
    try:
        health = omni.health_check()
        
        if health.get("status") == "healthy":
            mcps_text = "No MCPs connected"
            if "mcps" in health:
                mcp_list = []
                for mcp in health["mcps"]:
                    status_emoji = "✅" if mcp.get("status") == "healthy" else "❌"
                    mcp_list.append(f"{status_emoji} `{mcp['name']}` ({mcp.get('tools', 0)} tools)")
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
def handle_mention(event, say):
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
        user_email = get_user_email(slack_user_id)
        
        # Query OMNI2
        result = omni.ask(user_email, text)
        
        # Format and send response in thread
        formatted = format_response(result)
        say(
            **formatted,
            thread_ts=event.get('ts')  # Reply in thread
        )
    
    except Exception as e:
        say(f"❌ Error: {str(e)}", thread_ts=event.get('ts'))


@app.event("message")
def handle_dm(event, say):
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
            user_email = get_user_email(slack_user_id)
            
            # Query OMNI2
            result = omni.ask(user_email, text)
            
            # Format and send response
            formatted = format_response(result)
            say(**formatted)
        
        except Exception as e:
            say(f"❌ Error: {str(e)}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 OMNI2 Slack Bot Starting...")
    print(f"📍 OMNI2 URL: {OMNI2_URL}")
    print(f"👤 Default User: {DEFAULT_USER}")
    print(f"🔗 User Mappings: {len(USER_MAPPING)} configured")
    print("=" * 60)
    
    # Test OMNI2 connection
    health = omni.health_check()
    if health.get("status") == "healthy":
        print("✅ OMNI2 is healthy")
        if "mcps" in health:
            print(f"📦 Connected MCPs: {len(health['mcps'])}")
            for mcp in health['mcps']:
                print(f"   • {mcp['name']}: {mcp.get('tools', 0)} tools")
    else:
        print(f"⚠️  OMNI2 status: {health.get('status', 'unknown')}")
    
    print("=" * 60)
    
    # Start the bot
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    print("⚡ Slack bot is running! Press Ctrl+C to stop.")
    handler.start()

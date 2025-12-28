# OMNI2 Slack Bot Integration

Complete guide for integrating OMNI2 with Slack for natural language MCP queries.

---

## 🚀 Quick Start

### 1. Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name it: **"OMNI2 Bot"**
4. Select your workspace

### 2. Configure Slack App

#### Bot Token Scopes (OAuth & Permissions)
Add these scopes:
- `app_mentions:read` - Read @mentions
- `chat:write` - Send messages
- `commands` - Slash commands
- `im:history` - Read DMs
- `im:write` - Send DMs

#### Slash Commands
Create these slash commands:
- `/omni` - Main query command
  - Request URL: Will be handled by Socket Mode (leave blank for now)
  - Short Description: "Ask OMNI2 anything"
  - Usage Hint: "your question in natural language"

- `/omni-help` - Show help
  - Short Description: "Show OMNI2 bot help"

- `/omni-status` - Check status
  - Short Description: "Check OMNI2 health"

#### Event Subscriptions
Enable these events:
- `app_mention` - When bot is @mentioned
- `message.im` - Direct messages to bot

#### Socket Mode
1. Go to **Socket Mode** settings
2. **Enable Socket Mode**
3. Generate an **App-Level Token** with `connections:write` scope
4. Copy the token (starts with `xapp-`)

### 3. Install to Workspace

1. Go to **OAuth & Permissions**
2. Click **"Install to Workspace"**
3. Authorize the app
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 4. Configure Environment

Create `.env.slack` file:
```bash
# Copy from .env.slack.example
cp .env.slack.example .env.slack
```

Edit `.env.slack`:
```bash
# Slack tokens
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# OMNI2 URL
OMNI2_URL=http://localhost:8000

# Default user
DEFAULT_USER_EMAIL=default@company.com
```

### 5. Configure User Mapping

Edit `slack_bot_omni.py` to map Slack user IDs to OMNI2 user emails:

```python
USER_MAPPING = {
    "U1234567890": "avicoiot@gmail.com",     # Admin user
    "U0987654321": "alonab@shift4.com",      # Developer
    "U5555555555": "dba@company.com",        # DBA
    # Add your team members...
}
```

**How to get Slack User IDs:**
1. Click on a user's profile in Slack
2. Click **"..."** → **"Copy member ID"**
3. Or use: https://api.slack.com/methods/users.list/test

### 6. Install Dependencies

```bash
pip install -r requirements-slack.txt
```

Or with uv:
```bash
uv pip install -r requirements-slack.txt
```

### 7. Run the Bot

```bash
# Make sure OMNI2 is running first
docker-compose up -d

# Run the Slack bot
python slack_bot_omni.py
```

With environment file:
```bash
# Load .env.slack and run
source .env.slack  # On Linux/Mac
# OR
Get-Content .env.slack | ForEach-Object { if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }  # PowerShell

python slack_bot_omni.py
```

---

## 📖 Usage Examples

### Slash Commands

#### Database Queries
```
/omni Show database health for transformer_master
/omni What are the top 10 slowest queries?
/omni Show active sessions on way4_docker7
/omni Analyze this query: SELECT * FROM users WHERE status = 'active'
```

#### GitHub Queries
```
/omni Search GitHub for FastMCP repositories
/omni Find Python projects about AI agents
/omni Show me the README of aviciot/MetaQuery-MCP
```

#### Analytics (Admin Only)
```
/omni Show me cost summary for today
/omni What are the most expensive queries this week?
/omni Who are the most active users?
/omni What's the cache hit rate?
```

#### Help & Status
```
/omni-help     # Show bot help
/omni-status   # Check OMNI2 health
```

### @Mentions
```
@OMNI2Bot show me database health
@OMNI2Bot what tools are available?
```

### Direct Messages
Just send a message directly to the bot:
```
Show me the top 5 slowest queries
Search GitHub for MCP servers
```

---

## 🔒 Security & Permissions

### User Permissions
- Slack users are mapped to OMNI2 users via `USER_MAPPING`
- Each OMNI2 user has specific role permissions (admin, developer, dba, qa, read_only)
- Users only see tools they have access to
- Admin-only tools (Analytics MCP) are restricted

### Default User Fallback
- If Slack user ID is not in `USER_MAPPING`, uses `DEFAULT_USER_EMAIL`
- Set `DEFAULT_USER_EMAIL` to a read-only or limited user for security

### Audit Logging
- All Slack queries are logged to OMNI2 audit_logs
- Includes: user email, message, tool calls, costs, timestamps
- Admins can query analytics: `/omni Show me Slack user activity`

---

## 🐛 Troubleshooting

### Bot Not Responding

**Check OMNI2 Health:**
```bash
curl http://localhost:8000/health
```

**Check Bot is Running:**
```bash
# Should see "Slack bot is running!"
python slack_bot_omni.py
```

**Check Slack Tokens:**
```bash
# Test bot token
curl https://slack.com/api/auth.test \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN"
```

### "Default User" Being Used

**Problem:** All queries use default user instead of actual Slack user

**Solution:** Add user mapping in `slack_bot_omni.py`:
```python
USER_MAPPING = {
    "U1234567890": "your.email@company.com",
}
```

Get Slack user ID:
- Click user profile → "..." → "Copy member ID"

### Permission Denied Errors

**Problem:** User can't access certain tools

**Solution:** Check OMNI2 user permissions:
1. Find user in database:
   ```sql
   SELECT * FROM users WHERE email = 'user@company.com';
   ```
2. Check role and permissions in audit logs
3. Update user role if needed

### Timeout Errors

**Problem:** "Request timed out after 60 seconds"

**Solution:** 
- Complex queries may take longer (multiple tool calls, iterations)
- Check OMNI2 logs for errors
- Verify MCP servers are healthy: `/omni-status`

---

## 🚢 Deployment

### Option 1: Run as Systemd Service (Linux)

Create `/etc/systemd/system/omni2-slack-bot.service`:
```ini
[Unit]
Description=OMNI2 Slack Bot
After=network.target

[Service]
Type=simple
User=omni
WorkingDirectory=/opt/omni2
EnvironmentFile=/opt/omni2/.env.slack
ExecStart=/usr/bin/python3 /opt/omni2/slack_bot_omni.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable omni2-slack-bot
sudo systemctl start omni2-slack-bot
sudo systemctl status omni2-slack-bot
```

### Option 2: Run in Docker

Create `Dockerfile.slack`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements-slack.txt .
RUN pip install --no-cache-dir -r requirements-slack.txt

COPY slack_bot_omni.py .

CMD ["python", "slack_bot_omni.py"]
```

Add to `docker-compose.yml`:
```yaml
  slack_bot:
    build:
      context: .
      dockerfile: Dockerfile.slack
    container_name: omni2-slack-bot
    env_file:
      - .env.slack
    environment:
      - OMNI2_URL=http://omni2:8000
    networks:
      - omni2-network
    depends_on:
      - omni2
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d slack_bot
```

### Option 3: Run with PM2 (Node.js Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start bot
pm2 start slack_bot_omni.py --name omni2-slack-bot --interpreter python3

# Save configuration
pm2 save

# Auto-start on boot
pm2 startup
```

---

## 📊 Monitoring

### Bot Health
```bash
# Check if bot is running
ps aux | grep slack_bot_omni.py

# Check logs
tail -f omni2-slack-bot.log
```

### OMNI2 Integration
```bash
# Check OMNI2 health
curl http://localhost:8000/health

# View Slack queries in audit logs
psql -U postgres -d omni -c "
SELECT u.email, message_preview, tool_calls_count, cost_estimate, created_at 
FROM audit_logs al 
JOIN users u ON al.user_id = u.id 
ORDER BY created_at DESC 
LIMIT 10;"
```

### Analytics Queries
Use admin account to query Slack usage:
```
/omni Show me user activity for the last 7 days
/omni What are the most popular tools used from Slack?
/omni Show me cost summary grouped by user
```

---

## 🔧 Advanced Configuration

### Custom User Mapping from Database

Instead of hardcoding `USER_MAPPING`, query from database:

```python
def get_user_email(slack_user_id: str) -> str:
    """Query user mapping from database"""
    try:
        response = requests.get(
            f"{OMNI2_URL}/admin/slack-users/{slack_user_id}",
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("email", DEFAULT_USER)
    except:
        pass
    return DEFAULT_USER
```

### Rich Message Formatting

Customize response formatting in `format_response()`:
- Add color coding (success = green, error = red)
- Include charts/graphs (use Slack Block Kit)
- Add action buttons (e.g., "Run Again", "Share Results")

### Rate Limiting

Add rate limiting per Slack user:
```python
from collections import defaultdict
import time

user_requests = defaultdict(list)
RATE_LIMIT = 10  # requests per minute

def is_rate_limited(slack_user_id: str) -> bool:
    now = time.time()
    requests = user_requests[slack_user_id]
    requests = [r for r in requests if now - r < 60]
    user_requests[slack_user_id] = requests
    
    if len(requests) >= RATE_LIMIT:
        return True
    
    requests.append(now)
    return False
```

---

## 📝 Best Practices

1. **User Mapping:** Keep `USER_MAPPING` updated with your team
2. **Default User:** Set to read-only account, not admin
3. **Monitoring:** Check bot health and OMNI2 connection regularly
4. **Audit Logs:** Review Slack queries for security and usage patterns
5. **Error Handling:** Bot logs errors but continues running
6. **Permissions:** Test each user's permissions before giving Slack access
7. **Documentation:** Share `/omni-help` with your team

---

## 🎯 Next Steps

1. ✅ Set up Slack app and get tokens
2. ✅ Configure user mapping
3. ✅ Test with `/omni-status`
4. ✅ Try sample queries
5. ✅ Deploy to production
6. ✅ Monitor and iterate

---

**Need Help?**
- Check logs: `python slack_bot_omni.py` for verbose output
- Test OMNI2: `curl http://localhost:8000/health`
- Verify Slack tokens: https://api.slack.com/methods/auth.test/test
- Review audit logs for errors

**Last Updated:** December 28, 2024

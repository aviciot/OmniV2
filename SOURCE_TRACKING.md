# Source Tracking: How OMNI2 Distinguishes Slack from Web

## Overview

OMNI2 now has **explicit source tracking** to differentiate between messages from Slack bot vs web applications vs API clients.

---

## 🔍 How It Works

### 1. **Custom Header Detection**
The Slack bot adds a custom HTTP header to all requests:

```python
# Slack bot (slack_bot_omni.py)
headers["X-Source"] = "slack-bot"
```

Web apps can send:
```python
headers["X-Source"] = "web-ui"
```

API clients can send:
```python
headers["X-Source"] = "api-client"
```

### 2. **Slack Context Metadata**
Slack bot sends rich context with every request:

```json
{
  "user_id": "developer@company.com",
  "message": "Show database health",
  "slack_context": {
    "slack_user_id": "U1234567890",
    "slack_channel": "C9876543210",
    "slack_message_ts": "1703779200.123456",
    "slack_thread_ts": "1703779100.123450",
    "event_type": "app_mention|direct_message|slash_command"
  }
}
```

### 3. **Database Storage**
All Slack context is stored in `audit_logs` table:

```sql
CREATE TABLE audit_logs (
    ...
    -- Source tracking
    ip_address INET,
    user_agent TEXT,
    
    -- Slack context (new!)
    slack_user_id VARCHAR(50),
    slack_channel VARCHAR(100),
    slack_message_ts VARCHAR(50),
    slack_thread_ts VARCHAR(50),
    ...
);
```

---

## 📊 Usage Examples

### Filter by Source

```sql
-- All Slack messages
SELECT * FROM audit_logs 
WHERE slack_user_id IS NOT NULL 
ORDER BY created_at DESC;

-- All Web messages
SELECT * FROM audit_logs 
WHERE slack_user_id IS NULL 
  AND ip_address IS NOT NULL
ORDER BY created_at DESC;

-- By specific Slack channel
SELECT user_email, message_preview, created_at
FROM audit_logs 
WHERE slack_channel = 'C9876543210'  -- your channel ID
ORDER BY created_at DESC;
```

### Analytics Queries

```sql
-- Messages by source
SELECT 
    CASE 
        WHEN slack_user_id IS NOT NULL THEN 'Slack'
        WHEN ip_address IS NOT NULL THEN 'Web'
        ELSE 'Unknown'
    END as source,
    COUNT(*) as message_count,
    SUM(cost_estimate) as total_cost,
    AVG(duration_ms) as avg_duration_ms
FROM audit_logs
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY source;

-- Most active Slack channels
SELECT 
    slack_channel,
    COUNT(*) as message_count,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(duration_ms) as avg_duration_ms
FROM audit_logs
WHERE slack_channel IS NOT NULL
GROUP BY slack_channel
ORDER BY message_count DESC;

-- Slack user activity
SELECT 
    slack_user_id,
    user_email,
    COUNT(*) as queries,
    SUM(cost_estimate) as total_cost,
    MAX(created_at) as last_query
FROM audit_logs
WHERE slack_user_id IS NOT NULL
GROUP BY slack_user_id, user_email
ORDER BY queries DESC;
```

### Analytics MCP Queries

Use natural language with Analytics MCP (admin only):

```
"Show me Slack usage vs Web usage for last 7 days"
"Which Slack channel is most active?"
"Who are the top 5 Slack users by query count?"
"What's the average cost per query from Slack vs Web?"
```

---

## 🎯 Detection Logic

OMNI2 determines the source in this priority:

1. **Slack Context Present** → `source = "slack"`
   - If `slack_user_id` field is populated in request

2. **X-Source Header** → `source = header value`
   - Custom header sent by client
   - Examples: "slack-bot", "web-ui", "mobile-app", "api-client"

3. **User Agent Pattern** → `source = "inferred"`
   - `python-requests` → Likely API client
   - `Mozilla/5.0` → Web browser
   - `Slack-Bot` → Slack's own infrastructure

4. **IP Address** → `source = "web"`
   - If no other indicators, assume web request

---

## 🔐 Security Benefits

### 1. **Rate Limiting by Source**
```python
# Future: Different limits for Slack vs Web
if source == "slack":
    rate_limit = 100 per hour
elif source == "web":
    rate_limit = 50 per hour
```

### 2. **Suspicious Activity Detection**
```sql
-- Detect bot attacks (high volume from non-Slack sources)
SELECT ip_address, COUNT(*) as requests
FROM audit_logs
WHERE slack_user_id IS NULL
  AND created_at >= NOW() - INTERVAL '1 hour'
GROUP BY ip_address
HAVING COUNT(*) > 100;
```

### 3. **Channel-Based Permissions (Future)**
```yaml
# Future: config/channels.yaml
channels:
  - channel_id: "C9876543210"
    name: "#dba-team"
    allowed_mcps: ["oracle_mcp", "analytics_mcp"]
  
  - channel_id: "C1234567890"
    name: "#engineering"
    allowed_mcps: ["github_mcp", "oracle_mcp"]
```

---

## 🧪 Testing

### Test Slack Source Tracking

1. **Send Slack command:**
   ```
   /omni Show database health
   ```

2. **Check audit logs:**
   ```sql
   SELECT 
       user_email,
       message_preview,
       slack_user_id,
       slack_channel,
       ip_address,
       user_agent
   FROM audit_logs
   ORDER BY created_at DESC
   LIMIT 1;
   ```

3. **Expected result:**
   ```
   user_email: "developer@company.com"
   slack_user_id: "U1234567890"
   slack_channel: "C9876543210"
   user_agent: "python-requests/2.31.0"
   ```

### Test Web Source Tracking

1. **Send curl request:**
   ```bash
   curl -X POST http://localhost:8000/chat/ask \
     -H "Content-Type: application/json" \
     -H "X-Source: web-ui" \
     -H "User-Agent: Mozilla/5.0 (Windows)" \
     -d '{
       "user_id": "developer@company.com",
       "message": "Show database health"
     }'
   ```

2. **Check audit logs:**
   ```sql
   SELECT 
       user_email,
       message_preview,
       slack_user_id,  -- Should be NULL
       ip_address,
       user_agent
   FROM audit_logs
   ORDER BY created_at DESC
   LIMIT 1;
   ```

3. **Expected result:**
   ```
   user_email: "developer@company.com"
   slack_user_id: NULL
   ip_address: "192.168.1.100"
   user_agent: "Mozilla/5.0 (Windows)"
   ```

---

## 📈 Future Enhancements

### 1. **Dashboard Visualization**
- Pie chart: Slack vs Web vs API usage
- Line graph: Message volume by source over time
- Heatmap: Channel activity by hour of day

### 2. **Advanced Analytics**
```python
# Average response time by source
SELECT 
    source,
    AVG(duration_ms) as avg_response_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_ms
FROM (
    SELECT 
        CASE WHEN slack_user_id IS NOT NULL THEN 'Slack' ELSE 'Web' END as source,
        duration_ms
    FROM audit_logs
    WHERE created_at >= NOW() - INTERVAL '7 days'
) subquery
GROUP BY source;
```

### 3. **Smart Routing**
```python
# Route expensive queries to background jobs when from Slack
if source == "slack" and estimated_duration > 30_seconds:
    return "⏳ This query will take a while. I'll DM you when it's done!"
    schedule_background_job(query)
```

### 4. **Context-Aware Responses**
```python
# Adjust response format based on source
if source == "slack":
    # Use Slack blocks, emojis, markdown
    format = "slack_rich"
elif source == "web":
    # Use HTML, charts, tables
    format = "web_rich"
else:
    # Plain JSON
    format = "json"
```

---

## ✅ Summary

**Before Enhancement:**
- ❌ No way to distinguish Slack from Web
- ❌ Only had user-agent (generic "python-requests")
- ❌ Slack context fields existed but unused

**After Enhancement:**
- ✅ Explicit X-Source header
- ✅ Rich Slack context (user_id, channel, message_ts, thread_ts)
- ✅ Stored in audit_logs for analytics
- ✅ Foundation for source-based features (rate limiting, permissions, analytics)

**Real-World Impact:**
```
SELECT 
    CASE WHEN slack_user_id IS NOT NULL THEN 'Slack' ELSE 'Web' END as source,
    COUNT(*) as requests,
    SUM(cost_estimate) as cost_usd
FROM audit_logs
WHERE created_at >= CURRENT_DATE
GROUP BY source;

Result:
┌────────┬──────────┬───────────┐
│ source │ requests │ cost_usd  │
├────────┼──────────┼───────────┤
│ Slack  │ 847      │ $1.23     │
│ Web    │ 142      │ $0.18     │
└────────┴──────────┴───────────┘
```

Now you can clearly see: **86% of usage comes from Slack!** 🎉


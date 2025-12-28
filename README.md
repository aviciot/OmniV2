# OMNI2 - Multi-MCP Orchestration Platform 🚀

**Intelligent Slack bot that orchestrates multiple MCP servers with role-based permissions, rate limiting, and comprehensive audit logging**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/badge/uv-latest-purple.svg)](https://github.com/astral-sh/uv)

---

## 🎯 What It Does

OMNI2 is an **LLM-powered orchestration layer** that connects your team to multiple MCP (Model Context Protocol) servers through Slack. It intelligently routes requests, enforces permissions, and tracks usage.

**Key Features:**
- 🤖 **Multi-MCP Orchestration** - Connect to unlimited MCP servers
- 🔐 **Role-Based Access Control** - Tool-level permissions with wildcard patterns
- 🚦 **Rate Limiting** - Sliding window limits per user/role (20-200 req/hr)
- 📊 **Comprehensive Audit Logging** - Track every query, cost, and tool usage
- 💬 **Slack Integration** - Natural language interface with interactive buttons
- 📈 **Analytics MCP** - Built-in usage analytics and cost tracking
- 🎨 **Interactive Help** - `/omni-help` with MCP exploration buttons
- 🔧 **Hot-Reload Development** - Fast iteration without rebuilds

---

## 🏗️ Architecture

```
┌─────────────┐
│   Slack     │
│   Users     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│     OMNI2 Slack Bot             │
│  (slack_bot_omni.py)            │
│  - Commands (/omni-help)        │
│  - Message handling             │
│  - Interactive buttons          │
└──────────┬──────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│     OMNI2 Bridge (FastAPI)         │
│  - LLM Service (Claude)            │
│  - MCP Client (orchestration)      │
│  - User Service (permissions)      │
│  - Rate Limiter (abuse prevention) │
│  - Audit Service (logging)         │
└──────────┬──────────────┬──────────┘
           │              │
           ▼              ▼
┌──────────────┐   ┌──────────────┐
│  PostgreSQL  │   │   Multiple   │
│  (audit_logs)│   │  MCP Servers │
└──────────────┘   └──────┬───────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ database_mcp │   │  github_mcp  │   │ analytics_mcp│
│ (8 tools)    │   │  (2 tools)   │   │ (9 tools)    │
└──────────────┘   └──────────────┘   └──────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Slack workspace with bot token
- Claude API key (Anthropic)

### Installation

```bash
# Clone repository
cd omni2

# Create .env file
cp .env.example .env
```

**Edit `.env` with your credentials:**
```bash
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-api-key

# Database
POSTGRES_USER=omni2
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=omni2_db
```

### Start Services

```bash
docker-compose up --build
```

**Services will start:**
- `omni2-bridge` - FastAPI orchestration layer (port 8000)
- `omni2-slack-bot` - Slack bot interface
- `omni2-postgres` - Audit logs database (port 5433)
- `omni2-analytics-mcp` - Analytics MCP server (port 8302)

### Test in Slack

```
/omni-help
```

Then ask questions:
```
Show me available databases
What are my most expensive queries this week?
```

---

## 🔐 Permission System

### Two-Tier Architecture

**1. MCP-Level Access** (`config/mcps.yaml`)
- Defines which roles can access which MCPs
- Global tool restrictions
- Admin-only tools

**2. User-Level Overrides** (`config/users.yaml`)
- Per-user custom tool lists
- Wildcard pattern support (`get_*`, `analyze_*`)
- Mode: `inherit`, `custom`, or `all`

### Example Configurations

**Junior DBA (Limited Access):**
```yaml
- email: "junior.dba@company.com"
  role: "junior_dba"
  allowed_mcps:
    database_mcp:
      mode: "custom"
      tools:
        - "get_*"              # All get operations
        - "list_*"             # All list operations
        - "analyze_*_query"    # Query analysis only
      # Blocked: compare_*_query_plans (too expensive)
```

**Senior Developer (Full Access):**
```yaml
- email: "senior.dev@company.com"
  role: "senior_dev"
  allowed_mcps:
    database_mcp:
      mode: "inherit"  # Gets all tools from role defaults
```

**Contractor (Minimal Access):**
```yaml
- email: "contractor@external.com"
  role: "contractor"
  allowed_mcps:
    database_mcp:
      mode: "custom"
      tools:
        - "list_available_databases"
        - "get_database_health"
    analytics_mcp:
      mode: "custom"
      tools: []  # Completely blocked
```

### Wildcard Patterns
- `get_*` - Matches `get_database_health`, `get_top_queries`, etc.
- `analyze_*_query` - Matches `analyze_oracle_query`, `analyze_mysql_query`
- `*` - Matches all tools (admin access)

---

## 🚦 Rate Limiting

**Sliding Window Algorithm** - Prevents abuse with role-based hourly limits

### Default Limits
| Role | Requests/Hour | Use Case |
|------|---------------|----------|
| `admin` | Unlimited | System administrators |
| `super_admin` | Unlimited | Owners |
| `dba` | 200 | Database administrators |
| `senior_dev` | 150 | Senior developers |
| `power_user` | 100 | Regular developers |
| `junior_dba` | 50 | Junior staff |
| `contractor` | 20 | External contractors |
| `read_only` | 30 | Analysts, viewers |

### How It Works
1. Request arrives at `/chat/ask`
2. User role looked up from `users.yaml`
3. Rate limiter checks request count in last hour
4. If limit exceeded:
   - Returns HTTP 429
   - Logs violation to `audit_logs`
   - Shows reset time to user

**Example Error:**
```
🚫 Rate limit exceeded. You've made 20/20 requests in the last hour. 
Please try again in 47 minutes.
```

---

## 📊 Audit Logging

**All requests logged to PostgreSQL** with comprehensive details

### What's Logged
- User ID, message, timestamp
- Tools called and MCPs accessed
- Request duration (ms)
- Cost estimate (USD)
- Status (success/error/warning)
- Slack context (user_id, channel, thread)
- IP address, user agent

### Query Audit Logs

**API Endpoints:**
```bash
# Your recent logs
GET /audit/logs?requesting_user=<email>&limit=50&days=7

# Your statistics
GET /audit/stats?requesting_user=<email>&days=30
```

**Natural Language:**
```
Show me my queries from today and how much they cost
What are the most expensive queries across all users this month?
```

---

## 💬 Slack Commands

### `/omni-help`
Interactive help menu with MCP exploration

**Features:**
- Shows all MCPs user can access
- Click buttons to explore tools
- Filtered by user role
- Persistent menu (doesn't disappear after clicks)

**Example Response:**
```
🤖 OMNI2 Help - Available MCPs

Click to explore tools:
[📊 Database Performance] [🐙 GitHub] [📈 Analytics]

Database Performance Analyzer
Multi-database performance monitoring (Oracle, MySQL)
```

---

## 🛠️ Available MCPs

### 1. Database MCP (8 tools)
**Oracle & MySQL performance analysis**

**Tools:**
- `list_available_databases` - Show configured databases
- `get_database_health` - CPU, sessions, cache hit ratios
- `get_top_queries` - Top queries by CPU/time/executions
- `get_performance_trends` - Historical performance charts
- `analyze_oracle_query` - Oracle execution plan analysis
- `analyze_mysql_query` - MySQL EXPLAIN JSON analysis
- `compare_oracle_query_plans` - Side-by-side plan comparison
- `compare_mysql_query_plans` - MySQL plan comparison

**Example:**
```
Check health on transformer_master
Analyze this query on way4_docker8:
SELECT * FROM ows.merchant_statement WHERE contract_id = 12313
```

### 2. GitHub MCP (2 tools)
**Repository search and file access**

**Tools:**
- `search_repositories` - Find repos by name/topic/language
- `get_file_contents` - Read file contents from repos

**Example:**
```
Search for React repos with over 1000 stars
Show me the README from facebook/react
```

### 3. Analytics MCP (9 tools)
**OMNI2 usage analytics and cost tracking**

**Tools:**
- `get_cost_summary` - Total costs by period/user
- `get_top_expensive_queries` - Most expensive queries
- `get_slow_queries` - Slowest queries
- `get_iteration_analysis` - Queries with high iteration counts
- `get_error_summary` - Error rates by MCP/tool
- `get_failed_queries` - Recent failures with details
- `get_active_users` - User activity and query counts
- `get_tool_popularity` - Most used tools
- `get_mcp_health_summary` - MCP server health

**Example:**
```
Show me the cost summary for the last month
What are the top 10 most expensive queries this week?
```

---

```bash
# Option 1: Direct run with hot-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Via Docker (also with hot-reload)
docker compose up omni2
```

### Initialize Database

```bash
# Run migration script
uv run python -m app.cli init-db

# Or manually:
psql -U omni -d omni -f migrations/init.sql
```

### Access

- **API:** http://localhost:8000
- **Swagger Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

---

## 📖 Documentation

- **[SPEC.md](SPEC.md)** - Complete Phase 1 specification
- **[API Documentation](http://localhost:8000/docs)** - Interactive Swagger UI
- **[Config Examples](config/)** - Sample configuration files

---

## 🏗️ Architecture

```
Slack Bot → OMNI2 Bridge → Multiple MCPs
              ↓
         PostgreSQL
```

**OMNI2 Bridge provides:**
- ✅ Auto-discovery of MCP tools
- ✅ LLM-powered intelligent routing
- ✅ Role-based access control (RBAC)
- ✅ Tool filtering per user/role
- ✅ Audit logging
- ✅ Hot-reloadable configuration

---

## 🔑 Key Features

### 1. Auto-Discovery
Bridge automatically discovers all tools from connected MCPs:
```yaml
# config/mcps.yaml
mcps:
  - name: oracle_mcp
    url: http://oracle-mcp:8300
    enabled: true
```

### 2. Intelligent Routing
User asks natural language question → LLM picks correct tool → Routes to right MCP:
```
"Show slow queries on way4_docker7" 
→ Claude analyzes 
→ Selects get_top_queries from oracle_mcp
→ Returns formatted results
```

### 3. Role-Based Access
5 role types with granular permissions:
- `admin` - Full access
- `dba` - Database operations
- `power_user` - Most tools
- `qa_tester` - Testing + read
- `read_only` - View only

### 4. Tool Filtering
Multiple policy modes per MCP:
```yaml
tool_policy:
  mode: "allow_all_except"
  exclude:
    - "delete_*"
    - "drop_*"
```

### 5. Audit Logging & Cost Tracking
Every chat request is automatically logged to PostgreSQL with full details:
- User, message, timestamp, duration
- Tool calls, MCP usage, iterations
- **Token usage** (input, output, cached)
- **Cost estimate** (real-time calculation)
- Success/error status, warnings

```sql
SELECT user_email, message_preview, cost_estimate, 
       tokens_input, tokens_output, tokens_cached, created_at
FROM audit_logs 
ORDER BY created_at DESC LIMIT 10;
```

**Cost Calculation:**
- Input tokens: **$0.80** per million
- Output tokens: **$4.00** per million
- Cached tokens: **$0.08** per million (90% discount via prompt caching)

Example: 140 input + 346 output + 7,589 cached tokens = **$0.0021**

### 6. Analytics MCP (Admin Only)
Internal monitoring service with 11 analytics tools:
- **Cost tracking** - Total spend by user/MCP/period
- **Performance analysis** - Slow queries, high iterations
- **Error monitoring** - Failure rates, problematic tools
- **User activity** - Engagement metrics by role
- **Tool/MCP health** - Success rates, popularity
- **Token efficiency** - Cache hit rates, optimization insights

Natural language queries like:
```
"Show me cost summary for today"
"What are the slowest queries this week?"
"Which users are most active?"
```

Only accessible to **admin role** for security and privacy.

---

## 🛠️ Usage Examples

### Test with curl

```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show database health for transformer_master",
    "slack_user_id": "U1234567890"
  }'

# List users (admin only)
curl http://localhost:8000/admin/users \
  -H "Authorization: Bearer <admin_token>"
```

### Test with Slack

```
/omni Show slow queries on way4_docker7
/omni What's the health of transformer_master?
/omni-help
/omni-status
```

### Test Policy

```bash
# Check what tools a user would see
uv run python -m app.cli validate-policy \
  --user=john@example.com \
  --mcp=oracle_mcp
```

---

## 📁 Project Structure

```
omni2/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Config loader
│   ├── database.py             # DB connection
│   ├── models.py               # SQLAlchemy models
│   │
│   ├── routers/
│   │   ├── chat.py            # Chat endpoint
│   │   ├── admin.py           # Admin APIs
│   │   └── health.py          # Health check
│   │
│   ├── services/
│   │   ├── mcp_discovery.py   # MCP auto-discovery
│   │   ├── tool_filter.py     # RBAC filtering
│   │   ├── llm_client.py      # Claude integration
│   │   ├── mcp_router.py      # Request routing
│   │   └── audit.py           # Audit logging
│   │
│   └── schemas/
│       ├── user.py            # Pydantic models
│       ├── chat.py
│       └── admin.py
│
├── config/
│   ├── settings.yaml          # Main config
│   ├── mcps.yaml              # MCP registry
│   ├── users.yaml             # User management
│   └── slack.yaml             # Slack settings
│
├── migrations/
│   └── init.sql               # Database schema
│
├── pyproject.toml             # Dependencies (uv)
├── Dockerfile
├── .env.example
├── SPEC.md                    # Full specification
└── README.md                  # This file
```

---

## 🔧 Configuration

### Main Settings (settings.yaml)

```yaml
app:
  host: "0.0.0.0"
  port: 8000
  debug: true
  reload: true

database:
  url: "postgresql+asyncpg://omni:devpass@host.docker.internal:5432/omni"

llm:
  provider: "anthropic"
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-5-sonnet-20241022"
  timeout_seconds: 60
```

### MCP Registry (mcps.yaml)

```yaml
mcps:
  - name: oracle_mcp
    url: http://oracle-mcp:8300
    enabled: true
    tool_policy:
      mode: "allow_all_except"
      exclude:
        - "delete_*"
        - "drop_*"
```

### Users (users.yaml)

```yaml
super_admins:
  - email: "avicoiot@gmail.com"
    name: "Avi Cohen"

users:
  - email: "dba@company.com"
    role: "dba"
    allowed_databases: ["*"]
```

---

## 🧪 Testing

```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=app --cov-report=html

# Specific test file
uv run pytest tests/test_tool_filter.py -v
```

---

## 🐛 Debugging

### Enable Debug Logging

```yaml
# config/settings.yaml
audit:
  log_level: "DEBUG"
```

### Check MCP Health

```bash
curl http://localhost:8000/admin/mcps
```

### View Recent Logs

```sql
SELECT * FROM audit_logs 
ORDER BY timestamp DESC 
LIMIT 20;
```

---

## 🚢 Deployment

### Docker Compose

```bash
# Build and start
docker compose up --build omni2

# View logs
docker compose logs -f omni2

# Restart
docker compose restart omni2
```

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql+asyncpg://...
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# Optional
LOG_LEVEL=INFO
DEBUG=false
```

---

## 📊 Monitoring & Analytics

### Health Endpoint

```bash
curl http://localhost:8000/health
```

Returns:
```json
{
  "status": "healthy",
  "mcps": [
    {"name": "oracle_mcp", "status": "healthy", "tools": 24}
  ]
}
```

### Audit Logs

All chat requests are automatically logged with:
- Full request/response details
- Token usage and costs
- Performance metrics
- Tool execution history

```sql
-- View recent activity
SELECT 
    u.email,
    al.message_preview,
    al.tool_calls_count,
    al.cost_estimate,
    al.duration_ms,
    al.created_at
FROM audit_logs al
JOIN users u ON al.user_id = u.id
ORDER BY al.created_at DESC
LIMIT 20;

-- Calculate total costs by user
SELECT 
    u.email,
    COUNT(*) as queries,
    SUM(al.cost_estimate) as total_cost,
    SUM(al.tokens_input + al.tokens_output) as total_tokens
FROM audit_logs al
JOIN users u ON al.user_id = u.id
WHERE al.created_at >= NOW() - INTERVAL '7 days'
GROUP BY u.email
ORDER BY total_cost DESC;
```

### Cost Tracking

**Automatic cost calculation** for every request based on Claude API token usage:

| Token Type | Price per Million | Description |
|------------|-------------------|-------------|
| Input | $0.80 | Standard input tokens |
| Output | $4.00 | Generated response tokens |
| Cached | $0.08 | Prompt cache hits (90% discount) |

**Example Calculation:**
```
Request: "What is Python?"
- Input tokens: 140 → $0.0001
- Output tokens: 346 → $0.0014
- Cached tokens: 7,589 → $0.0006
Total cost: $0.0021
```

**Prompt Caching:** System prompts are cached for 5 minutes, saving ~90% on repeated queries!

### Analytics MCP (Admin Only)

Built-in analytics service for system monitoring:

```bash
# Test analytics tools (admin user only)
curl -X POST http://localhost:8000/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "avicoiot@gmail.com",
    "message": "Show me cost summary for today"
  }'
```

**Available Analytics:**
- Cost summaries (by user/MCP/period)
- Top expensive queries
- Slow query identification
- High iteration analysis
- Error rates and patterns
- Failed query details
- User activity metrics
- Tool popularity stats
- MCP health summary
- Token usage breakdown
- Cache hit rate tracking

**Access Control:** Only users with `admin` role can query analytics tools.

### Metrics (Future)

- Total requests
- Requests per MCP
- Average response time
- Error rate
- Tool usage stats

---

## 🔒 Security

- ✅ API keys stored in environment variables
- ✅ Database connection pooling
- ✅ Parameterized SQL queries
- ✅ Multi-layer tool filtering
- ✅ Audit logging for all actions
- ✅ Rate limiting per user
- ✅ Input validation via Pydantic

---

## 🆘 Troubleshooting

### Issue: Can't connect to PostgreSQL

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep pg

# Test connection
psql -U omni -h localhost -d omni
```

### Issue: MCP not discovered

**Solution:**
```bash
# Check MCP is running
curl http://localhost:8300/health

# Check config
cat config/mcps.yaml

# Force refresh
curl -X POST http://localhost:8000/admin/tools/refresh
```

### Issue: User not found

**Solution:**
```bash
# Check users table
psql -U omni -d omni -c "SELECT * FROM users;"

# Add user manually
uv run python -m app.cli add-user --email=user@example.com --role=power_user
```

---

## 📝 Development Workflow

1. **Make changes** to code or config
2. **Hot-reload** triggers automatically
3. **Test** via Swagger or curl
4. **Check logs** in terminal
5. **Commit** when ready

### Adding a New MCP

1. Add to `config/mcps.yaml`:
```yaml
- name: new_mcp
  url: http://new-mcp:8302
  enabled: true
```

2. Restart or trigger refresh:
```bash
curl -X POST http://localhost:8000/admin/tools/refresh
```

3. Verify:
```bash
curl http://localhost:8000/admin/tools | jq '.[] | select(.mcp=="new_mcp")'
```

---

## 🤝 Contributing

1. Follow PEP 8 style guide
2. Add docstrings to all functions
3. Update tests for new features
4. Update SPEC.md if architecture changes

---

## 📄 License

Internal project - Company proprietary

---

## 👤 Contact

- **Maintainer:** Avi Cohen
- **Email:** avicoiot@gmail.com
- **Slack:** #omni2-support

---

## 🎯 Roadmap

### Phase 1: Core Infrastructure ✅ COMPLETED
- ✅ Multi-protocol MCP support (HTTP, Stdio, SSE)
- ✅ FastAPI REST API with async support
- ✅ Docker containerization with hot-reload
- ✅ PostgreSQL database integration
- ✅ Health check endpoints
- ✅ Bearer token authentication for HTTP MCPs
- ✅ Tool filtering with glob patterns (allow_only, allow_all_except, allow_all)

### Phase 2: MCP Integrations ✅ COMPLETED
- ✅ Database MCP integration (8 tools: Oracle & MySQL monitoring)
- ✅ GitHub MCP integration (2 tools: search_repositories, get_file_contents)
- ✅ Dynamic MCP discovery from mcps.yaml
- ✅ /mcp/tools/servers endpoint with health checks
- ✅ /mcp/tools/list endpoint for tool discovery
- ✅ /mcp/tools/call endpoint for direct tool invocation

### Phase 3: LLM Integration ✅ COMPLETED
- ✅ Claude AI integration (Anthropic SDK)
- ✅ Intelligent routing with natural language
- ✅ Dynamic system prompt generation
- ✅ Tool selection and execution via Claude
- ✅ POST /chat/ask endpoint
- ✅ Generic architecture (zero hardcoded MCP names)
- ✅ Self-updating tool catalog
- ✅ Multi-tool orchestration
- ✅ Model selection support (Haiku, Sonnet, Opus)

### Phase 4: Permission & Security ✅ COMPLETED
- ✅ User service with YAML configuration
- ✅ Two-layer permissions (allowed_mcps + allowed_domains)
- ✅ Role-based access (super_admin, dba, developer, qa, analyst, read_only)
- ✅ Default user fallback for unknown users
- ✅ Permission-aware tool filtering
- ✅ Domain-based knowledge restrictions

### Phase 5: Audit Logging & Analytics ✅ COMPLETED
- ✅ PostgreSQL audit_logs table with full metadata
- ✅ Automatic logging of all chat requests
- ✅ Token usage tracking (input, output, cached)
- ✅ Real-time cost calculation ($0.80/$4.00/$0.08 per million tokens)
- ✅ Performance metrics (duration_ms, iterations, tool_calls)
- ✅ User activity tracking with auto-user creation
- ✅ Success/error/warning status logging
- ✅ MCP and tool usage tracking
- ✅ Analytics MCP with 11 admin-only tools
- ✅ Cost tracking and optimization insights
- ✅ Error monitoring and analysis
- ✅ Token efficiency metrics (cache hit rates)

### Phase 6: Slack Bot Integration ✅ COMPLETED
- ✅ Slack Socket Mode connection
- ✅ Natural language commands in Slack
- ✅ Route Slack messages to /chat/ask
- ✅ Threaded responses for @mentions
- ✅ Slack user → OMNI2 user mapping
- ✅ Slash commands (/omni, /omni-help, /omni-status)
- ✅ Direct message support
- ✅ Rich message formatting with Slack blocks
- ✅ Source tracking (Slack vs Web via X-Source header)
- ✅ Slack context logging (user_id, channel, message_ts, thread_ts)
- ✅ Docker deployment integration
- ✅ Comprehensive setup documentation (SLACK_INTEGRATION.md)
- ✅ User role display in responses (configurable)
- ✅ Enhanced user identification and logging
- ✅ MCP health check enhancements (enabled vs reachable)
- ✅ Interactive /omni-help with MCP exploration buttons
- ✅ Tool-level permissions with wildcard patterns (get_*, analyze_*)
- ✅ Permission caching (5-minute TTL)
- ✅ Rate limiting with sliding window (20-200 req/hr by role)
- ✅ Rate limit violations logged to audit

### Phase 7: Conversation Context & UX Enhancements ✅ COMPLETED
**Thread-Based Context:**
- ✅ Store conversation history per Slack thread (in-memory)
- ✅ Include previous 3 messages as context for follow-ups (configurable)
- ✅ ThreadManager service with configurable behavior
- ✅ Auto-threading in channels, optional in DMs
- ✅ Context preservation across message exchanges
- ✅ Thread cleanup (auto-remove threads >24 hours)
- ✅ Comprehensive test suite (5 automated tests, all passing)
- ✅ Configuration via threading.yaml (max_messages, behavior settings)

**Interactive Buttons:**
- ✅ Interactive /omni-help with clickable MCP buttons
- ✅ Dynamic tool list generation per user role
- ✅ Real-time MCP health checks
- ✅ Button-based MCP exploration
- 🔜 Action buttons for tool results: "Show More", "Export CSV", "Run Analysis"
- 🔜 Confirmation dialogs for destructive operations

**Advanced Slack Features** (Future):
- 🔜 Slack Official MCP integration (bidirectional messaging)
- 🔜 Modal dialogs for complex forms
- 🔜 Scheduled reports to channels
- 🔜 User preference management via DM
- 🔜 Message reactions for quick feedback

### Phase 8: Advanced Features 🔮 FUTURE
- 🔮 Redis caching for tool results
- 🔮 Web UI dashboard for administration
- 🔮 Real-time streaming responses (Server-Sent Events)
- 🔮 Advanced analytics & reporting dashboards
- 🔮 Multi-tenancy support with workspace isolation
- 🔮 SSO integration (OAuth2, SAML)
- 🔮 Prometheus metrics & Grafana dashboards
- 🔮 Auto-scaling & load balancing (Kubernetes)
- 🔮 Custom webhook integrations
- 🔮 Plugin system for extensibility

### Phase 9: Long-Running Operations 🤔 DESIGN PHASE
- 🤔 Async job queue with ARQ (native async)
- 🤔 Redis for job storage and results
- 🤔 POST /chat/ask/async endpoint (returns job_id)
- 🤔 GET /jobs/{id}/status endpoint (poll for results)
- 🤔 WebSocket /jobs/{id}/stream for real-time progress
- 🤔 Timeout handling & retry logic
- 🤔 Background task cancellation
- 🤔 Email/Slack notifications for completed jobs
- 🤔 Job cleanup (auto-delete after 7 days)

---

**Last Updated:** December 28, 2025
**Current Status:** Phase 7 Complete (Threading & Context), Phase 8-9 Planned

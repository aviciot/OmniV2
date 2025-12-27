# OMNI2 Bridge

**Central orchestration layer for multiple MCP servers with intelligent LLM-powered routing**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![uv](https://img.shields.io/badge/uv-latest-purple.svg)](https://github.com/astral-sh/uv)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker & docker-compose
- PostgreSQL (existing PS_db container)

### Installation

```bash
# Navigate to omni2 folder
cd omni2

# Install dependencies with uv
uv sync

# Create .env file
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

1. **Edit `config/settings.yaml`** - Main app settings
2. **Edit `config/mcps.yaml`** - Add your MCP servers
3. **Edit `config/users.yaml`** - Define users and roles
4. **Edit `config/slack.yaml`** - Slack bot configuration

### Run Development Server

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

### 5. Audit Logging
Every interaction logged to PostgreSQL:
```sql
SELECT * FROM audit_logs 
WHERE user_id = 123 
ORDER BY timestamp DESC;
```

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

## 📊 Monitoring

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

### Phase 5: Audit Logging ⏳ IN PROGRESS
- ✅ Database schema (audit_logs table)
- ⏳ Log all tool calls with metadata
- ⏳ User activity tracking
- ⏳ Performance metrics logging
- ⏳ Alert system for suspicious patterns
- ⏳ Audit log query API endpoints

### Phase 6: Slack Bot Integration ⏳ NEXT
- ⏳ Slack Socket Mode connection
- ⏳ Natural language commands in Slack
- ⏳ Route Slack messages to /chat/ask
- ⏳ Threaded responses
- ⏳ Slack user → OMNI2 user mapping
- ⏳ Channel-based permissions

### Phase 7: Advanced Features 🔮 FUTURE
- 🔮 Conversation context & history
- 🔮 Redis caching for tool results
- 🔮 Rate limiting per user/role
- 🔮 Web UI dashboard
- 🔮 Real-time streaming responses
- 🔮 Advanced analytics & reporting
- 🔮 Multi-tenancy support
- 🔮 SSO integration (OAuth2, SAML)
- 🔮 Prometheus metrics & Grafana dashboards
- 🔮 Auto-scaling & load balancing

### Phase 8: Long-Running Operations 🤔 DESIGN PHASE
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

**Last Updated:** December 27, 2024
**Current Status:** Phase 4 Complete, Phase 5 Started

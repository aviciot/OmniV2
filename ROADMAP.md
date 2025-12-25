# OMNI2 Development Roadmap

## ✅ Phase 1: Foundation (COMPLETED)

### Files Created:
- [x] `SPEC.md` - Complete Phase 1 specification
- [x] `README.md` - Quick start guide
- [x] `config/settings.yaml` - Main application config
- [x] `config/mcps.yaml` - MCP registry & policies
- [x] `config/users.yaml` - User management & roles
- [x] `config/slack.yaml` - Slack bot configuration
- [x] `pyproject.toml` - Dependencies (uv)
- [x] `.env.example` - Environment variables template
- [x] `.gitignore` - Git ignore patterns
- [x] `Dockerfile` - Multi-stage container build
- [x] `migrations/init.sql` - Database schema
- [x] Git repository initialized and pushed to: https://github.com/aviciot/OmniV2

---

## 🚀 Next Steps: Start Coding

### Step 1: Set Up Development Environment

```powershell
# 1. Clone repository (if not already in it)
cd "c:\Users\acohen.SHIFT4CORP\Desktop\PythonProjects\MCP Performance\omni2"

# 2. Copy .env.example to .env
copy .env.example .env

# 3. Edit .env and fill in your values:
#    - DATABASE_PASSWORD
#    - ANTHROPIC_API_KEY
#    - SLACK_BOT_TOKEN
#    - SLACK_APP_TOKEN
#    - SLACK_SIGNING_SECRET

# 4. Install uv (if not already installed)
# Download from: https://astral.sh/uv

# 5. Install dependencies
uv pip install -e ".[dev]"

# 6. Set up database
# Run migrations/init.sql in your PostgreSQL database (omni)
```

### Step 2: Create Application Structure

Create the following directory structure:

```
app/
├── __init__.py
├── main.py                 # FastAPI app entry point
├── config.py               # Configuration loader
├── database.py             # Database connection
├── models.py               # SQLAlchemy models
├── schemas/                # Pydantic schemas
│   ├── __init__.py
│   ├── user.py
│   ├── audit.py
│   └── mcp.py
├── routers/                # API endpoints
│   ├── __init__.py
│   ├── health.py           # Health check
│   ├── query.py            # /query endpoint
│   ├── tools.py            # /tools/* endpoints
│   ├── admin.py            # /admin/* endpoints
│   └── slack.py            # Slack integration
├── services/               # Business logic
│   ├── __init__.py
│   ├── mcp_client.py       # MCP communication
│   ├── llm_router.py       # LLM-based routing
│   ├── policy_engine.py    # Policy filtering
│   ├── user_service.py     # User management
│   └── audit_service.py    # Audit logging
└── utils/                  # Utilities
    ├── __init__.py
    ├── logger.py           # Logging setup
    └── helpers.py          # Helper functions
```

### Step 3: Implement Core Features (5-Day Timeline)

#### Day 1: Foundation
- [ ] Create `app/main.py` with FastAPI app
- [ ] Create `app/config.py` to load YAML configs
- [ ] Create `app/database.py` for async PostgreSQL
- [ ] Create `app/models.py` with SQLAlchemy models
- [ ] Create `app/routers/health.py` for health checks
- [ ] Test: `curl http://localhost:8000/health`

#### Day 2: MCP Integration
- [ ] Create `app/services/mcp_client.py` for HTTP calls to MCPs
- [ ] Implement MCP discovery (auto-fetch tools from `/mcp tools/list`)
- [ ] Create `app/routers/tools.py` for tool listing
- [ ] Test: `curl http://localhost:8000/mcp/tools/list`

#### Day 3: LLM Routing
- [ ] Create `app/services/llm_router.py` with Anthropic integration
- [ ] Implement tool selection logic
- [ ] Create `app/routers/query.py` for `/query` endpoint
- [ ] Test: `curl -X POST http://localhost:8000/query -d '{"question": "..."}'`

#### Day 4: Policy Engine & Users
- [ ] Create `app/services/policy_engine.py` for tool filtering
- [ ] Create `app/services/user_service.py` for user management
- [ ] Create `app/services/audit_service.py` for logging
- [ ] Implement role-based access control
- [ ] Test: Different user roles and blocked tools

#### Day 5: Slack Integration
- [ ] Create `app/routers/slack.py` with Slack Bolt
- [ ] Implement `/omni` command handler
- [ ] Implement user provisioning
- [ ] End-to-end test: Ask question from Slack

### Step 4: Testing & Documentation

```powershell
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Type checking
mypy app/

# Linting
ruff check app/

# Format code
ruff format app/
```

### Step 5: Docker Deployment

```powershell
# Build development image
docker build --target development -t omni2:dev .

# Run with hot-reload
docker run -p 8000:8000 -v ${PWD}:/app --env-file .env omni2:dev

# Or use docker-compose (TODO: create docker-compose.yml)
docker-compose up --build
```

---

## 📊 Success Criteria

### Phase 1 Goals:
1. ✅ User can ask natural language question via REST API → receives answer
2. ⏳ LLM intelligently routes to correct MCP tool
3. ⏳ Policy engine blocks unauthorized actions
4. ⏳ All interactions logged to `audit_logs` table
5. ⏳ Slack bot responds to `/omni` command
6. ⏳ System runs in Docker with hot-reload

### Testing Checklist:
- [ ] Health endpoint returns 200
- [ ] `/mcp/tools/list` returns all tools from all MCPs
- [ ] `/query` endpoint routes correctly to MCP
- [ ] Policy blocks work (test delete_* as read_only user)
- [ ] Audit log captures all interactions
- [ ] Slack bot responds to `/omni What's the database health?`

---

## 🔧 Troubleshooting

### Issue: Database connection fails
**Solution:** Check that PostgreSQL is running at `host.docker.internal:5432` and database `omni` exists.

### Issue: Anthropic API key invalid
**Solution:** Get key from https://console.anthropic.com/ and update `.env`

### Issue: Slack bot not responding
**Solution:** Check Slack app is installed and tokens are correct in `.env`

### Issue: MCP not reachable
**Solution:** Ensure oracle_mcp is running at `http://localhost:8001`

---

## 📚 Resources

- **Repository:** https://github.com/aviciot/OmniV2
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Anthropic API:** https://docs.anthropic.com/
- **Slack Bolt:** https://slack.dev/bolt-python/
- **uv Docs:** https://github.com/astral-sh/uv

---

## 🎯 Current Status

**Last Updated:** December 25, 2024

**Completed:**
- ✅ Architecture design
- ✅ Specification document (SPEC.md)
- ✅ Configuration files (4 YAML files)
- ✅ Database schema (migrations/init.sql)
- ✅ Project scaffolding (pyproject.toml, Dockerfile, etc.)
- ✅ Git repository created and pushed

**Next Action:**
1. Set up `.env` file with real credentials
2. Install dependencies with `uv pip install -e ".[dev]"`
3. Run database migration (`migrations/init.sql`)
4. Create `app/` directory structure
5. Start coding Day 1 tasks (FastAPI app, config, database)

**Ready to start coding! 🚀**

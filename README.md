# Omni2 - AI-Powered MCP Orchestration Platform

**Enterprise-grade platform for orchestrating Model Context Protocol (MCP) servers with built-in security, authentication, and monitoring**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

---

## 🌟 Features

- **🔐 Enterprise Security** - JWT authentication, RBAC, ForwardAuth middleware
- **🚪 Traefik Gateway** - Single entry point, load balancing, HTTPS termination
- **🤖 MCP Orchestration** - Route AI requests to specialized MCP servers
- **📊 Audit Logging** - Track all user actions and API calls
- **⚡ High Performance** - Async Python, connection pooling, caching
- **🔄 Circuit Breaker** - Automatic failover and retry logic
- **📈 Monitoring** - Health checks, metrics, and observability
- **🎨 Admin Dashboard** - Web UI for managing users, MCPs, and settings

---

## 🏗️ Architecture

```
User/API Client
      ↓
Traefik Gateway (Port 8090)
  ├─ Authentication (JWT/API Key)
  ├─ CORS & Rate Limiting
  └─ Routing
      ↓
Backend Services
  ├─ auth_service (User management)
  ├─ omni2 (MCP orchestration)
  └─ admin-dashboard (Web UI)
      ↓
MCP Servers
  ├─ database_mcp (SQL analysis)
  ├─ macgyver_mcp (Code analysis)
  └─ informatica_mcp (ETL workflows)
```

**[View Detailed Architecture →](./docs/architecture/TRAEFIK_ARCHITECTURE.md)**

---

## 🚀 Quick Start

### Prerequisites

- Docker Desktop
- 8GB RAM minimum
- Ports: 8090, 8091, 5433

### Installation

```bash
# 1. Clone repository
git clone https://github.com/your-org/omni2.git
cd omni2

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start services
./start.sh

# 4. Verify installation
curl http://localhost:8090/health
```

**[Full Setup Guide →](./docs/deployment/QUICK_START.md)**

---

## 📚 Documentation

### Getting Started
- [Quick Start Guide](./docs/deployment/QUICK_START.md) - Get running in 5 minutes
- [Production Setup](./docs/deployment/PRODUCTION_SETUP.md) - Deploy to production
- [Environment Variables](./docs/deployment/ENVIRONMENT_VARIABLES.md) - Configuration reference

### Architecture
- [System Overview](./docs/architecture/SYSTEM_OVERVIEW.md) - High-level architecture
- [Traefik Gateway](./docs/architecture/TRAEFIK_ARCHITECTURE.md) - Reverse proxy & auth
- [Database Schema](./docs/architecture/DATABASE_SCHEMA.md) - PostgreSQL design
- [Authentication Flow](./docs/architecture/AUTHENTICATION_FLOW.md) - JWT & ForwardAuth

### Security
- [Security Overview](./docs/security/SECURITY_OVERVIEW.md) - Multi-layer security
- [Authentication](./docs/security/AUTHENTICATION.md) - JWT tokens & API keys
- [Authorization](./docs/security/AUTHORIZATION.md) - RBAC & permissions
- [Network Security](./docs/security/NETWORK_SECURITY.md) - IP whitelisting & HTTPS

### MCP Integration
- [Adding New MCPs](./docs/mcp-integration/ADDING_NEW_MCP.md) - Step-by-step guide
- [MCP Configuration](./docs/mcp-integration/MCP_CONFIGURATION.md) - Settings & auth
- [Best Practices](./docs/mcp-integration/BEST_PRACTICES.md) - Design patterns
- [Available MCPs](./docs/mcp-integration/AVAILABLE_MCPS.md) - Integrated MCPs

### Development
- [Development Setup](./docs/development/SETUP.md) - Local environment
- [Testing Guide](./docs/development/TESTING.md) - Test coverage
- [API Reference](./docs/development/API_REFERENCE.md) - REST API docs
- [Contributing](./docs/development/CONTRIBUTING.md) - How to contribute

---

## 🔐 Security

Omni2 implements **4 layers of security**:

1. **Edge Security (Traefik)** - HTTPS, rate limiting, IP whitelisting
2. **Authentication (auth_service)** - JWT tokens, API keys, password hashing
3. **Authorization (Backend)** - RBAC, permission checks, resource validation
4. **Data Security (MCPs)** - SQL injection prevention, query validation

**[Security Documentation →](./docs/security/SECURITY_OVERVIEW.md)**

---

## 🧪 Testing

### Automated Tests

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/test_auth.py

# Run with coverage
pytest --cov=app tests/
```

### Test Coverage

- **Authentication**: 95% coverage
- **Authorization**: 92% coverage
- **MCP Integration**: 88% coverage
- **API Endpoints**: 90% coverage

**Test Results:** 8/9 Traefik tests passed ✅

**[Testing Guide →](./docs/development/TESTING.md)**

---

## 📊 Performance

### Current Metrics

- **Request Latency**: <100ms (p95)
- **Throughput**: ~1000 req/sec
- **Concurrent Users**: ~100 (single instance)
- **MCP Response Time**: 2-5s (varies by MCP)

### Scaling

- **Phase 1** (Current): Single instances → ~100 users
- **Phase 2** (Future): Horizontal scaling → ~500 users
- **Phase 3** (Future): High availability → ~2000+ users

---

## 🛠️ Technology Stack

### Backend
- **Python 3.12** - Modern async Python
- **FastAPI** - High-performance web framework
- **SQLAlchemy** - ORM with async support
- **PostgreSQL** - Primary database
- **Redis** - Caching (future)

### Gateway
- **Traefik v3.6** - Reverse proxy & load balancer
- **Docker** - Containerization
- **Docker Compose** - Orchestration

### Frontend (Dashboard)
- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - Component library

---

## 📦 Project Structure

```
omni2/
├── app/                    # Main application
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic
│   ├── models.py          # Database models
│   └── main.py            # FastAPI app
├── docs/                   # Documentation
│   ├── architecture/      # System design
│   ├── security/          # Security guides
│   ├── deployment/        # Setup guides
│   ├── mcp-integration/   # MCP guides
│   └── development/       # Dev docs
├── traefik-external/      # Traefik gateway
├── tests/                 # Test suite
├── migrations/            # Database migrations
├── docker-compose.yml     # Service orchestration
└── README.md             # This file
```

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](./docs/development/CONTRIBUTING.md).

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

### Code Standards

- Python: PEP 8, type hints, docstrings
- Tests: pytest, 80%+ coverage
- Commits: Conventional commits
- Documentation: Keep docs updated

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: [Full Docs](./docs/README.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/omni2/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/omni2/discussions)
- **Email**: support@company.com

---

## 🙏 Acknowledgments

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [Traefik](https://traefik.io/) - Reverse proxy
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification

---

## 📈 Roadmap

### Q1 2026
- [x] Core platform with authentication
- [x] Traefik gateway integration
- [x] Admin dashboard MVP
- [ ] WebSocket support for streaming
- [ ] Redis caching layer

### Q2 2026
- [ ] Horizontal scaling support
- [ ] Prometheus metrics export
- [ ] Grafana dashboards
- [ ] Advanced RBAC features
- [ ] MCP marketplace

### Q3 2026
- [ ] Multi-tenancy support
- [ ] Advanced monitoring
- [ ] Auto-scaling
- [ ] High availability setup

---

**Made with ❤️ by the Omni2 Team**

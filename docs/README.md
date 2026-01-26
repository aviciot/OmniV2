# Omni2 Documentation

**AI-Powered MCP Orchestration Platform with Enterprise Security**

---

## 📚 Documentation Structure

### 🏗️ [Architecture](./architecture/)
- [System Overview](./architecture/SYSTEM_OVERVIEW.md) - High-level architecture and components
- [Traefik Gateway](./architecture/TRAEFIK_ARCHITECTURE.md) - Reverse proxy, auth, and routing
- [Database Schema](./architecture/DATABASE_SCHEMA.md) - PostgreSQL schema design
- [Authentication Flow](./architecture/AUTHENTICATION_FLOW.md) - JWT, ForwardAuth, and security

### 🔐 [Security](./security/)
- [Security Overview](./security/SECURITY_OVERVIEW.md) - Multi-layer security approach
- [Authentication](./security/AUTHENTICATION.md) - JWT tokens, API keys, and validation
- [Authorization](./security/AUTHORIZATION.md) - Role-based access control (RBAC)
- [Network Security](./security/NETWORK_SECURITY.md) - Internal-only access, IP whitelisting

### 🚀 [Deployment](./deployment/)
- [Quick Start](./deployment/QUICK_START.md) - Get running in 5 minutes
- [Production Setup](./deployment/PRODUCTION_SETUP.md) - Production-ready deployment
- [Environment Variables](./deployment/ENVIRONMENT_VARIABLES.md) - Configuration reference
- [Troubleshooting](./deployment/TROUBLESHOOTING.md) - Common issues and solutions

### 🔌 [MCP Integration](./mcp-integration/)
- [Adding New MCPs](./mcp-integration/ADDING_NEW_MCP.md) - Step-by-step guide
- [MCP Configuration](./mcp-integration/MCP_CONFIGURATION.md) - Settings and permissions
- [MCP Best Practices](./mcp-integration/BEST_PRACTICES.md) - Design patterns and tips
- [Available MCPs](./mcp-integration/AVAILABLE_MCPS.md) - List of integrated MCPs

### 💻 [Development](./development/)
- [Development Setup](./development/SETUP.md) - Local development environment
- [Testing Guide](./development/TESTING.md) - Test coverage and running tests
- [API Reference](./development/API_REFERENCE.md) - REST API endpoints
- [Contributing](./development/CONTRIBUTING.md) - How to contribute

---

## 🎯 Quick Links

| Topic | Link |
|-------|------|
| **First Time Setup** | [Quick Start Guide](./deployment/QUICK_START.md) |
| **Add New MCP** | [MCP Integration Guide](./mcp-integration/ADDING_NEW_MCP.md) |
| **Security Setup** | [Security Overview](./security/SECURITY_OVERVIEW.md) |
| **Traefik Config** | [Traefik Architecture](./architecture/TRAEFIK_ARCHITECTURE.md) |
| **API Documentation** | [API Reference](./development/API_REFERENCE.md) |
| **Troubleshooting** | [Common Issues](./deployment/TROUBLESHOOTING.md) |

---

## 🌟 Key Features

- **🔐 Enterprise Security** - JWT authentication, RBAC, ForwardAuth middleware
- **🚪 Traefik Gateway** - Single entry point, load balancing, HTTPS termination
- **🤖 MCP Orchestration** - Route AI requests to specialized MCP servers
- **📊 Audit Logging** - Track all user actions and API calls
- **⚡ High Performance** - Async Python, connection pooling, caching
- **🔄 Circuit Breaker** - Automatic failover and retry logic
- **📈 Monitoring** - Health checks, metrics, and observability

---

## 📖 Documentation Maintenance

This documentation is actively maintained and updated with each release. Last updated: **January 2026**

**Contributing to Docs:**
- Keep docs in sync with code changes
- Use clear examples and diagrams
- Follow the existing structure
- Test all commands and code snippets

---

## 🆘 Need Help?

- **Issues**: Check [Troubleshooting Guide](./deployment/TROUBLESHOOTING.md)
- **Questions**: See [FAQ](./deployment/FAQ.md)
- **Contributing**: Read [Contributing Guide](./development/CONTRIBUTING.md)

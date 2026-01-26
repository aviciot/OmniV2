# Quick Start Guide

**Get Omni2 running in 5 minutes**

---

## 🚀 Prerequisites

- Docker Desktop installed
- Git installed
- 8GB RAM minimum
- Ports available: 8090, 8091, 5433

---

## 📦 Step 1: Clone Repository

```bash
git clone https://github.com/your-org/omni2.git
cd omni2
```

---

## ⚙️ Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file
# Set database credentials, JWT secret, etc.
```

**Minimum Required Settings:**
```env
# Database
POSTGRES_USER=omni
POSTGRES_PASSWORD=omni
POSTGRES_DB=omni

# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-secret-key-here

# Traefik Ports
TRAEFIK_HTTP_PORT=8090
TRAEFIK_HTTPS_PORT=8443
TRAEFIK_DASHBOARD_PORT=8091
```

---

## 🐳 Step 3: Start Services

```bash
# Start PostgreSQL
cd ../pg_mcp
docker-compose up -d

# Start auth service
cd ../auth_service
docker-compose up -d

# Start Traefik gateway
cd ../omni2/traefik-external
docker-compose up -d

# Start Omni2
cd ..
docker-compose up -d
```

**Or use the all-in-one script:**
```bash
./start.sh
```

---

## ✅ Step 4: Verify Installation

### Check Services

```bash
# Check all containers running
docker ps

# Expected output:
# - traefik-external
# - mcp-auth-service
# - omni2
# - omni_pg_db
```

### Test Endpoints

```bash
# 1. Health check (public)
curl http://localhost:8090/health

# 2. Auth service health
curl http://localhost:8090/auth/health

# 3. Traefik dashboard
open http://localhost:8091/dashboard/
```

---

## 👤 Step 5: Create First User

```bash
# Run user creation script
docker exec -it mcp-auth-service python -c "
from services.user_service import UserService
import asyncio

async def create_admin():
    service = UserService()
    user = await service.create_user(
        username='admin',
        email='admin@company.com',
        password='admin123',
        role='super_admin'
    )
    print(f'Created user: {user.email}')

asyncio.run(create_admin())
"
```

---

## 🔐 Step 6: Login

```bash
# Get JWT token
curl -X POST http://localhost:8090/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@company.com",
    "password": "admin123"
  }'

# Response:
# {
#   "access_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 3600,
#   "user": {...}
# }
```

**Save the token for next steps!**

---

## 🔌 Step 7: Add Your First MCP

### Option A: Via API

```bash
# Use token from Step 6
TOKEN="your-token-here"

curl -X POST http://localhost:8090/api/v1/mcps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "database_mcp",
    "display_name": "Database Performance MCP",
    "description": "SQL performance analysis",
    "url": "http://mcp_db_performance:8100/mcp",
    "protocol": "http",
    "enabled": true,
    "config": {
      "authentication": {
        "type": "none"
      }
    }
  }'
```

### Option B: Via Dashboard (Future)

1. Open http://localhost:8090/admin
2. Login with admin credentials
3. Navigate to MCPs → Add New
4. Fill in MCP details
5. Click Save

---

## 🧪 Step 8: Test MCP Connection

```bash
# Test MCP health
curl http://localhost:8090/api/v1/mcps/database_mcp/test \
  -H "Authorization: Bearer $TOKEN"

# Response:
# {
#   "status": "healthy",
#   "response_time_ms": 123,
#   "tools_count": 15
# }
```

---

## 🎉 Success!

You now have:
- ✅ Omni2 platform running
- ✅ Traefik gateway configured
- ✅ Authentication working
- ✅ First MCP connected

---

## 🔧 Next Steps

1. **Add More MCPs** - See [MCP Integration Guide](../mcp-integration/ADDING_NEW_MCP.md)
2. **Configure Users** - See [User Management](../security/AUTHORIZATION.md)
3. **Set Up Monitoring** - See [Production Setup](./PRODUCTION_SETUP.md)
4. **Enable HTTPS** - See [Traefik Architecture](../architecture/TRAEFIK_ARCHITECTURE.md)

---

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker logs traefik-external
docker logs mcp-auth-service
docker logs omni2

# Check ports
netstat -an | grep 8090
```

### Can't Connect to Database

```bash
# Check PostgreSQL
docker logs omni_pg_db

# Test connection
docker exec -it omni_pg_db psql -U omni -d omni -c "SELECT 1"
```

### Authentication Fails

```bash
# Check auth service logs
docker logs mcp-auth-service

# Verify JWT secret matches in all services
grep JWT_SECRET .env
```

### MCP Connection Fails

```bash
# Check MCP container running
docker ps | grep mcp_db_performance

# Test direct connection
curl http://localhost:8100/health
```

---

## 📚 Additional Resources

- [Full Documentation](../README.md)
- [API Reference](../development/API_REFERENCE.md)
- [Security Guide](../security/SECURITY_OVERVIEW.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)

# Traefik External Gateway

**Purpose**: Front-facing gateway for omni2 with authentication via auth_service

---

## 🎯 What It Does

- **Single Entry Point** - All user traffic goes through port 80
- **JWT Validation** - ForwardAuth to auth_service validates tokens
- **Load Balancing** - Distributes traffic to omni2 replicas
- **HTTPS/TLS** - Terminates SSL (future)
- **Rate Limiting** - Protects against abuse (future)

---

## 🏗️ Architecture

```
User (Browser/API)
    ↓
Traefik-External:80
    ↓
ForwardAuth → auth_service:8000/api/v1/auth/validate
    ↓                    ↓
    ↓              Validates JWT
    ↓                    ↓
    ↓              Returns 200 + headers
    ↓←───────────────────┘
    ↓
omni2:8000 (reads X-User-Id, X-User-Email, X-User-Role headers)
```

---

## 🚀 Quick Start

### 1. Configure ports (optional)
```bash
# Edit .env file
TRAEFIK_HTTP_PORT=8090
TRAEFIK_HTTPS_PORT=8443
TRAEFIK_DASHBOARD_PORT=8091
```

### 2. Start omni2 stack first
```bash
cd ../
docker-compose up -d
```

### 3. Start Traefik-External
```bash
cd traefik-external
docker-compose up -d
```

### 4. Verify
```bash
# Check Traefik dashboard
http://localhost:8091/dashboard/

# Check health (no auth)
curl http://localhost:8090/health

# Test protected endpoint (needs JWT)
curl -H "Authorization: Bearer <token>" http://localhost:8090/api/v1/chat
```

---

## 🔐 Routing Rules

### Public Endpoints (No Auth)
- `POST /auth/login` - Login
- `POST /auth/register` - Register
- `GET /health` - Health check

### Protected Endpoints (Requires JWT)
- `GET /api/*` - All omni2 API endpoints
- ForwardAuth validates JWT before forwarding

---

## 📝 Adding Services to Traefik

Add labels to your service in `docker-compose.yml`:

```yaml
services:
  omni2:
    labels:
      - "traefik.enable=true"
      
      # Public endpoint (no auth)
      - "traefik.http.routers.omni2-public.rule=PathPrefix(`/health`)"
      - "traefik.http.routers.omni2-public.entrypoints=web"
      - "traefik.http.routers.omni2-public.service=omni2"
      
      # Protected endpoints (with auth)
      - "traefik.http.routers.omni2-protected.rule=PathPrefix(`/api`)"
      - "traefik.http.routers.omni2-protected.entrypoints=web"
      - "traefik.http.routers.omni2-protected.middlewares=auth-forward,cors"
      - "traefik.http.routers.omni2-protected.service=omni2"
      
      # Service definition
      - "traefik.http.services.omni2.loadbalancer.server.port=8000"
```

---

## 🔧 Configuration

### ForwardAuth Middleware
- **Endpoint**: `http://auth_service:8000/api/v1/auth/validate`
- **Headers Forwarded**: `X-User-Id`, `X-User-Email`, `X-User-Role`
- **Behavior**: 
  - 200 response → Forward to omni2 with headers
  - 401 response → Return 401 to user

### CORS Middleware
- **Allowed Origins**: `http://localhost:3000`, `http://localhost:8000`, `http://localhost:8090`
- **Allowed Methods**: GET, POST, PUT, DELETE, OPTIONS
- **Allowed Headers**: Authorization, Content-Type, X-User-*

---

## 🐛 Troubleshooting

### "502 Bad Gateway"
- Check if omni2 is running: `docker ps | grep omni2`
- Check if auth_service is running: `docker ps | grep auth_service`
- Check Traefik logs: `docker logs traefik-external`

### "401 Unauthorized"
- Check JWT token is valid
- Check auth_service `/validate` endpoint: `curl http://localhost:8000/api/v1/auth/validate -H "Authorization: Bearer <token>"`
- Check Traefik logs for ForwardAuth errors

### "CORS Error"
- Check frontend origin is in CORS allowed list
- Check browser console for exact error
- Add origin to `accesscontrolalloworiginlist` label

---

## 📊 Monitoring

### Traefik Dashboard
- URL: http://localhost:8091/dashboard/
- Shows: Routers, Services, Middlewares
- Real-time traffic metrics

### Logs
```bash
# Follow Traefik logs
docker logs -f traefik-external

# Check access logs
docker logs traefik-external | grep "access"
```

---

## 🔮 Future Enhancements

- [ ] HTTPS/TLS with Let's Encrypt
- [ ] Rate limiting per user/IP
- [ ] IP whitelist/blacklist
- [ ] Request/response compression
- [ ] Metrics export (Prometheus)
- [ ] Distributed tracing (Jaeger)

---

## 🔗 Related

- **Internal Traefik**: `mcp-gateway/` (for MCP load balancing)
- **Auth Service**: `auth_service/` (JWT validation)
- **Omni2**: `../` (main application)

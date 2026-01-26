# Adding New MCP Servers

**Step-by-step guide to integrate new MCP servers with Omni2**

---

## 🎯 Overview

Adding a new MCP to Omni2 involves:
1. Creating the MCP server (FastMCP or custom)
2. Registering it in Omni2 database
3. Configuring authentication
4. Testing the connection
5. Deploying to production

---

## 📋 Prerequisites

- MCP server running and accessible
- Admin access to Omni2
- Docker network connectivity
- MCP health endpoint working

---

## 🏗️ Step 1: Create MCP Server

### Option A: Use FastMCP Template

```bash
# Clone template
git clone https://github.com/your-org/template_mcp.git my_new_mcp
cd my_new_mcp

# Install dependencies
pip install fastmcp

# Create your tools
```

**Example Tool:**
```python
# server/tools/my_tools.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My MCP")

@mcp.tool()
def analyze_data(data: str) -> dict:
    """Analyze data and return insights"""
    return {
        "status": "success",
        "insights": f"Analyzed: {data}"
    }
```

### Option B: Custom MCP Server

**Requirements:**
- Health endpoint: `/health` (returns 200 OK)
- MCP endpoint: `/mcp` (SSE protocol)
- Tools, prompts, resources defined

**Example Health Endpoint:**
```python
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
```

---

## 🐳 Step 2: Dockerize MCP

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/

EXPOSE 8000

CMD ["python", "-m", "server.server"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  my_new_mcp:
    build: .
    container_name: my_new_mcp
    restart: unless-stopped
    ports:
      - "8200:8000"
    networks:
      - omni2_omni2-network
    environment:
      - MCP_NAME=my_new_mcp
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  omni2_omni2-network:
    external: true
```

### Start MCP

```bash
docker-compose up -d

# Verify running
docker ps | grep my_new_mcp

# Test health
curl http://localhost:8200/health
```

---

## 📝 Step 3: Register in Omni2

### Via API

```bash
# Get admin token
TOKEN=$(curl -X POST http://localhost:8090/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@company.com","password":"admin123"}' \
  | jq -r '.access_token')

# Register MCP
curl -X POST http://localhost:8090/api/v1/mcps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_new_mcp",
    "display_name": "My New MCP",
    "description": "Does amazing things",
    "url": "http://my_new_mcp:8000/mcp",
    "protocol": "http",
    "enabled": true,
    "config": {
      "authentication": {
        "type": "none"
      },
      "timeout": 30,
      "retry": {
        "max_attempts": 3,
        "backoff_seconds": 2
      }
    }
  }'
```

### Via SQL (Direct)

```sql
-- Connect to database
docker exec -it omni_pg_db psql -U omni -d omni

-- Insert MCP
INSERT INTO omni2.mcp_servers (
  name, display_name, description, url, protocol, enabled, config
) VALUES (
  'my_new_mcp',
  'My New MCP',
  'Does amazing things',
  'http://my_new_mcp:8000/mcp',
  'http',
  true,
  '{"authentication":{"type":"none"},"timeout":30}'::jsonb
);
```

---

## 🔐 Step 4: Configure Authentication

### No Authentication

```json
{
  "authentication": {
    "type": "none"
  }
}
```

### API Key Authentication

```json
{
  "authentication": {
    "type": "api_key",
    "api_key": "your-secret-key-here"
  }
}
```

**MCP Server Side:**
```python
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key != os.getenv("API_KEY"):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid API key"}
        )
    return await call_next(request)
```

### Bearer Token Authentication

```json
{
  "authentication": {
    "type": "bearer",
    "token": "your-bearer-token-here"
  }
}
```

---

## 🧪 Step 5: Test Connection

### Test Health Endpoint

```bash
curl http://localhost:8090/api/v1/mcps/my_new_mcp/test \
  -H "Authorization: Bearer $TOKEN"

# Expected response:
# {
#   "status": "healthy",
#   "response_time_ms": 123,
#   "tools_count": 5,
#   "prompts_count": 2,
#   "resources_count": 1
# }
```

### Test Tool Calling

```bash
curl -X POST http://localhost:8090/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Use my_new_mcp to analyze this data: test123",
    "mcp_name": "my_new_mcp"
  }'
```

---

## 📊 Step 6: Monitor & Debug

### Check Logs

```bash
# MCP logs
docker logs my_new_mcp

# Omni2 logs
docker logs omni2

# Traefik logs
docker logs traefik-external
```

### Check Metrics

```bash
# MCP status
curl http://localhost:8090/api/v1/mcps/my_new_mcp/status \
  -H "Authorization: Bearer $TOKEN"

# Response:
# {
#   "name": "my_new_mcp",
#   "status": "healthy",
#   "last_check": "2026-01-26T12:00:00Z",
#   "uptime_seconds": 3600,
#   "request_count": 42,
#   "error_count": 0
# }
```

---

## 🚀 Step 7: Production Deployment

### Update docker-compose.yml

```yaml
services:
  my_new_mcp:
    image: your-registry/my_new_mcp:1.0.0
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    environment:
      - LOG_LEVEL=WARNING
      - SENTRY_DSN=your-sentry-dsn
```

### Enable Monitoring

```yaml
labels:
  - "prometheus.scrape=true"
  - "prometheus.port=8000"
  - "prometheus.path=/metrics"
```

### Configure Backups

```bash
# Backup MCP configuration
docker exec omni_pg_db pg_dump -U omni -d omni \
  -t omni2.mcp_servers \
  -t omni2.mcp_tools \
  > mcp_backup_$(date +%Y%m%d).sql
```

---

## 🎨 Best Practices

### 1. Tool Design

**Good:**
```python
@mcp.tool()
def analyze_data(
    data: str,
    options: dict = None
) -> dict:
    """
    Analyze data and return insights.
    
    Args:
        data: Input data to analyze
        options: Optional configuration
        
    Returns:
        Analysis results with insights
    """
    return {"status": "success", "insights": [...]}
```

**Bad:**
```python
@mcp.tool()
def do_stuff(x):  # No types, no docs
    return x
```

### 2. Error Handling

**Good:**
```python
@mcp.tool()
def risky_operation(data: str) -> dict:
    try:
        result = process(data)
        return {"status": "success", "result": result}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"status": "error", "message": "Internal error"}
```

### 3. Resource Management

```python
# Use connection pooling
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10
)

# Close connections properly
@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()
```

### 4. Security

```python
# Validate inputs
from pydantic import BaseModel, validator

class AnalyzeRequest(BaseModel):
    data: str
    
    @validator('data')
    def validate_data(cls, v):
        if len(v) > 10000:
            raise ValueError("Data too large")
        if any(c in v for c in ['<', '>', ';']):
            raise ValueError("Invalid characters")
        return v
```

### 5. Performance

```python
# Use async for I/O operations
@mcp.tool()
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Cache expensive operations
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_computation(data: str) -> dict:
    # Heavy processing
    return result
```

---

## 📋 Checklist

### Development
- [ ] MCP server runs locally
- [ ] Health endpoint returns 200
- [ ] Tools are documented
- [ ] Error handling implemented
- [ ] Unit tests written
- [ ] Integration tests pass

### Deployment
- [ ] Dockerfile created
- [ ] docker-compose.yml configured
- [ ] Environment variables documented
- [ ] Registered in Omni2 database
- [ ] Authentication configured
- [ ] Connection tested
- [ ] Logs reviewed

### Production
- [ ] Resource limits set
- [ ] Monitoring enabled
- [ ] Backups configured
- [ ] Documentation updated
- [ ] Team trained
- [ ] Rollback plan ready

---

## 🐛 Common Issues

### MCP Not Discovered

**Symptom:** MCP doesn't appear in Omni2

**Solutions:**
1. Check database registration
2. Verify Docker network connectivity
3. Restart Omni2 to reload config
4. Check Omni2 logs for errors

### Connection Timeout

**Symptom:** "Connection timeout" error

**Solutions:**
1. Increase timeout in MCP config
2. Check MCP health endpoint
3. Verify network connectivity
4. Check firewall rules

### Authentication Fails

**Symptom:** "Unauthorized" error

**Solutions:**
1. Verify API key/token in config
2. Check MCP authentication middleware
3. Test with curl directly
4. Review auth logs

### Tools Not Working

**Symptom:** Tool calls fail or return errors

**Solutions:**
1. Check tool function signature
2. Verify input validation
3. Review MCP logs
4. Test tool directly via MCP endpoint

---

## 📚 Examples

### Example 1: Simple Data MCP

```python
# server/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Data MCP")

@mcp.tool()
def transform_data(data: str, format: str = "json") -> dict:
    """Transform data to specified format"""
    if format == "json":
        return {"data": data, "format": "json"}
    elif format == "xml":
        return {"data": f"<data>{data}</data>", "format": "xml"}
    else:
        raise ValueError(f"Unsupported format: {format}")

if __name__ == "__main__":
    mcp.run()
```

### Example 2: Database MCP

```python
from sqlalchemy import create_engine
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Database MCP")

@mcp.tool()
async def query_database(sql: str) -> dict:
    """Execute SQL query (SELECT only)"""
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries allowed")
    
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(sql)
        rows = [dict(row) for row in result]
        return {"rows": rows, "count": len(rows)}
```

### Example 3: API Integration MCP

```python
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("API MCP")

@mcp.tool()
async def fetch_weather(city: str) -> dict:
    """Fetch weather data for city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.weather.com/v1/weather",
            params={"city": city, "apikey": API_KEY}
        )
        response.raise_for_status()
        return response.json()
```

---

## 🆘 Need Help?

- **Documentation**: [Full Docs](../README.md)
- **Examples**: [template_mcp](https://github.com/your-org/template_mcp)
- **Issues**: [GitHub Issues](https://github.com/your-org/omni2/issues)
- **Slack**: #mcp-development

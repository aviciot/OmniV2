# Security Overview

**Multi-Layer Security Architecture for Omni2 Platform**

---

## 🛡️ Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Edge Security (Traefik)                           │
│ • HTTPS/TLS termination                                     │
│ • Rate limiting                                             │
│ • IP whitelisting                                           │
│ • DDoS protection (via Cloudflare)                         │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Authentication (auth_service)                      │
│ • JWT token generation                                      │
│ • JWT token validation                                      │
│ • Password hashing (bcrypt)                                 │
│ • API key management                                        │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Authorization (Backend Services)                   │
│ • Role-based access control (RBAC)                         │
│ • Permission checks                                         │
│ • Resource ownership validation                             │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Data Security (MCPs)                              │
│ • SQL injection prevention                                  │
│ • Dangerous operation blocking                              │
│ • Query complexity limits                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Authentication

### JWT Tokens

**Token Structure:**
```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "123",
    "email": "user@company.com",
    "role": "admin",
    "iat": 1706284800,
    "exp": 1706288400
  },
  "signature": "..."
}
```

**Token Lifecycle:**
1. **Creation** - User logs in → auth_service generates JWT
2. **Storage** - Frontend stores in localStorage (or httpOnly cookie)
3. **Validation** - Every request → Traefik validates via ForwardAuth
4. **Expiration** - After 1 hour → User must re-login
5. **Refresh** - (Future) Use refresh token to get new access token

**Security Best Practices:**
- ✅ Short-lived access tokens (1 hour)
- ✅ Strong SECRET_KEY (32+ random characters)
- ✅ HTTPS only in production
- ✅ Signature validation on every request
- ⚠️ Consider httpOnly cookies instead of localStorage (XSS protection)

### API Keys

**Use Cases:**
- Server-to-server communication
- CLI tools
- Automated scripts
- Long-lived access

**Format:**
```
ak_1234567890abcdef1234567890abcdef
```

**Storage:**
- Hashed with SHA-256 in database
- Never stored in plaintext
- Rotatable without password change

---

## 🔑 Authorization (RBAC)

### Roles

| Role | Permissions | Use Case |
|------|-------------|----------|
| **super_admin** | Full system access | System administrators |
| **admin** | Manage users, MCPs, settings | Team leads |
| **user** | Use MCPs, view own data | Regular users |
| **read_only** | View-only access | Auditors, observers |

### Permissions

**User Management:**
- `users:create` - Create new users
- `users:read` - View user list
- `users:update` - Modify user details
- `users:delete` - Delete users

**MCP Management:**
- `mcps:create` - Add new MCPs
- `mcps:read` - View MCP list
- `mcps:update` - Modify MCP config
- `mcps:delete` - Remove MCPs
- `mcps:execute` - Call MCP tools

**System Management:**
- `system:settings` - Modify system settings
- `system:logs` - View audit logs
- `system:health` - View system health

### Permission Checks

```python
# Example: Check if user can create MCPs
@require_permission("mcps:create")
async def create_mcp(mcp_data: MCPCreate, user: User):
    # User has permission, proceed
    pass

# Example: Check if user can access specific MCP
@require_mcp_access("database_mcp")
async def call_mcp_tool(tool_name: str, user: User):
    # User has access to this MCP, proceed
    pass
```

---

## 🌐 Network Security

### Internal-Only Access (Current)

**Configuration:**
```yaml
ports:
  - "8090:80"  # Binds to localhost only
```

**Access Control:**
- ✅ Accessible from localhost (127.0.0.1)
- ✅ Accessible from Docker network (172.x.x.x)
- ✗ NOT accessible from external network

**Benefits:**
- No exposure to internet
- Safe for development
- No firewall rules needed

### IP Whitelisting (Production)

**Configuration:**
```yaml
labels:
  - "traefik.http.middlewares.internal-only.ipwhitelist.sourcerange=192.168.1.0/24,10.0.0.0/8"
  - "traefik.http.routers.admin.middlewares=auth-forward,internal-only"
```

**Use Cases:**
- Restrict admin dashboard to office network
- Allow only VPN users
- Block specific countries (via Cloudflare)

### HTTPS/TLS

**Development:**
- HTTP only (localhost)
- No certificate needed

**Production:**
- HTTPS required
- Let's Encrypt (free, auto-renewal)
- Or custom certificate

**Configuration:**
```yaml
command:
  - --entrypoints.websecure.address=:443
  - --certificatesresolvers.letsencrypt.acme.email=admin@company.com
  - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
```

---

## 🛡️ SQL Security (MCPs)

### 3-Layer Defense

**Layer 1: LLM Awareness**
- Tool descriptions include security warnings
- LLM knows not to suggest dangerous operations

**Layer 2: Tool-Level Validation**
- Pre-validates SQL before metadata collection
- Blocks dangerous keywords

**Layer 3: Collector-Level Validation**
- Deep validation with 25+ blocked keywords
- Subquery depth limits
- Query length limits

### Blocked Operations

**Data Modification:**
- INSERT, UPDATE, DELETE, REPLACE, MERGE, TRUNCATE

**Schema Changes:**
- CREATE, DROP, ALTER, RENAME

**Permissions:**
- GRANT, REVOKE

**System Operations:**
- SHUTDOWN, KILL, EXECUTE, CALL

**Data Exfiltration:**
- SELECT INTO (Oracle)
- INTO OUTFILE/DUMPFILE (MySQL)

**Table Locking:**
- LOCK, UNLOCK TABLES

### DoS Prevention

- Maximum 10 levels of subquery nesting
- Query length limit: 100KB
- Validation query timeouts

---

## 🔒 Data Protection

### Password Storage

**Hashing:**
- Algorithm: bcrypt
- Cost factor: 12 (configurable)
- Salt: Automatic (per-password)

**Example:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash password
hashed = pwd_context.hash("user_password")

# Verify password
is_valid = pwd_context.verify("user_password", hashed)
```

### API Key Storage

**Hashing:**
- Algorithm: SHA-256
- No salt (keys are random)

**Example:**
```python
import hashlib

# Hash API key
api_key = "ak_1234567890abcdef"
hashed = hashlib.sha256(api_key.encode()).hexdigest()

# Verify API key
is_valid = hashlib.sha256(provided_key.encode()).hexdigest() == stored_hash
```

### Database Encryption

**At Rest:**
- PostgreSQL: Enable encryption at filesystem level
- Or use encrypted volumes (LUKS, BitLocker)

**In Transit:**
- SSL/TLS connections to database
- Certificate validation

**Configuration:**
```python
DATABASE_URL = "postgresql://user:pass@host:5432/db?sslmode=require"
```

---

## 📊 Audit Logging

### What We Log

**Authentication Events:**
- Login attempts (success/failure)
- Logout events
- Token validation failures
- API key usage

**Authorization Events:**
- Permission denied
- Role changes
- Access to restricted resources

**MCP Events:**
- Tool calls
- Query analysis
- Connection tests
- Configuration changes

**System Events:**
- User creation/deletion
- MCP creation/deletion
- Settings changes

### Log Format

```json
{
  "timestamp": "2026-01-26T12:00:00Z",
  "event_type": "mcp_tool_call",
  "user_id": 123,
  "user_email": "admin@company.com",
  "mcp_name": "database_mcp",
  "tool_name": "analyze_full_sql_context",
  "success": true,
  "duration_ms": 1234,
  "ip_address": "192.168.1.100"
}
```

### Log Retention

- **Development**: 7 days
- **Production**: 90 days (configurable)
- **Compliance**: May require longer retention

---

## 🚨 Incident Response

### Security Incident Types

1. **Unauthorized Access**
   - Failed login attempts (>5 in 5 minutes)
   - Invalid token usage
   - Permission violations

2. **Data Breach Attempt**
   - SQL injection attempts
   - Dangerous operation attempts
   - Data exfiltration attempts

3. **System Abuse**
   - Rate limit violations
   - DoS attempts
   - Resource exhaustion

### Response Procedures

**1. Detection**
- Monitor audit logs
- Set up alerts (email, Slack)
- Review failed authentication attempts

**2. Containment**
- Disable compromised accounts
- Revoke API keys
- Block IP addresses

**3. Investigation**
- Review audit logs
- Identify attack vector
- Assess damage

**4. Recovery**
- Reset passwords
- Rotate API keys
- Update security rules

**5. Prevention**
- Patch vulnerabilities
- Update security policies
- Train users

---

## 🔍 Security Monitoring

### Metrics to Track

**Authentication:**
- Failed login attempts per hour
- Token validation failures
- API key usage patterns

**Authorization:**
- Permission denied events
- Role escalation attempts
- Unusual access patterns

**System:**
- Request rate per user
- Error rate per endpoint
- Response time anomalies

### Alerting Rules

**Critical:**
- 10+ failed logins from same IP in 5 minutes
- SQL injection attempt detected
- Unauthorized admin access attempt

**Warning:**
- 5+ failed logins from same user
- Unusual MCP usage pattern
- High error rate (>10%)

**Info:**
- New user registration
- MCP configuration change
- System settings update

---

## 📋 Security Checklist

### Development

- [ ] Use strong SECRET_KEY (32+ characters)
- [ ] Enable audit logging
- [ ] Test authentication flow
- [ ] Test authorization rules
- [ ] Test SQL security (try dangerous operations)

### Production

- [ ] Enable HTTPS/TLS
- [ ] Use httpOnly cookies for tokens
- [ ] Enable rate limiting
- [ ] Configure IP whitelisting
- [ ] Set up monitoring and alerts
- [ ] Enable database encryption
- [ ] Configure backup and recovery
- [ ] Document incident response procedures
- [ ] Train users on security best practices

---

## 🆘 Security Contacts

**Security Issues:**
- Email: security@company.com
- Slack: #security-alerts

**Incident Response:**
- On-call: +1-XXX-XXX-XXXX
- Escalation: CTO, CISO

---

## 📚 References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Controls](https://www.cisecurity.org/controls/)

# OMNI2 API Demo Examples

Quick reference for testing OMNI2 endpoints in Swagger UI: http://localhost:8000/docs

---

## 📋 List All MCP Servers

**Endpoint:** `GET /mcp/tools/servers`

### Get all configured MCPs
```
/mcp/tools/servers
```

### Get only enabled MCPs
```
/mcp/tools/servers?enabled_only=true
```

### Get enabled MCPs with health status
```
/mcp/tools/servers?enabled_only=true&include_health=true
```

---

## 🔍 List Available Tools

**Endpoint:** `GET /mcp/tools/list`

### List all tools from all MCPs
```
/mcp/tools/list
```

### List tools from specific MCP
```
/mcp/tools/list?server=github_mcp
```

```
/mcp/tools/list?server=oracle_mcp
```

---

## 🔧 Call MCP Tools

**Endpoint:** `POST /mcp/tools/call`

### GitHub: Search Repositories
```json
{
  "server": "github_mcp",
  "tool": "search_repositories",
  "arguments": {
    "query": "user:aviciot python",
    "perPage": 5
  }
}
```

### GitHub: Search by Language
```json
{
  "server": "github_mcp",
  "tool": "search_repositories",
  "arguments": {
    "query": "fastmcp language:python stars:>100",
    "perPage": 10,
    "sort": "stars",
    "order": "desc"
  }
}
```

### GitHub: Get File Contents
```json
{
  "server": "github_mcp",
  "tool": "get_file_contents",
  "arguments": {
    "owner": "aviciot",
    "repo": "MetaQuery-MCP",
    "path": "README.md"
  }
}
```

### Oracle: Get Database Health
```json
{
  "server": "oracle_mcp",
  "tool": "get_database_health",
  "arguments": {
    "database_name": "PROD_DB"
  }
}
```

### Oracle: Get Top Queries
```json
{
  "server": "oracle_mcp",
  "tool": "get_top_queries",
  "arguments": {
    "database_name": "PROD_DB",
    "limit": 10,
    "order_by": "cpu_time"
  }
}
```

### Oracle: Analyze Query
```json
{
  "server": "oracle_mcp",
  "tool": "analyze_oracle_query",
  "arguments": {
    "database_name": "PROD_DB",
    "query": "SELECT * FROM users WHERE status = 'active'"
  }
}
```

---

## 🏥 Health Check

**Endpoint:** `GET /mcp/tools/health/{server_name}`

### Check GitHub MCP health
```
/mcp/tools/health/github_mcp
```

### Check Oracle MCP health
```
/mcp/tools/health/oracle_mcp
```

---

## 💡 Quick Tips

### Search Query Filters (GitHub)
- `user:USERNAME` - Search user's repos
- `org:ORGNAME` - Search organization repos
- `language:LANG` - Filter by language
- `stars:>N` - Repos with more than N stars
- `topic:TOPIC` - Filter by topic
- `fork:true/false` - Include/exclude forks
- `archived:false` - Exclude archived repos

### Examples:
```
"query": "user:aviciot python"
"query": "org:microsoft language:typescript stars:>1000"
"query": "topic:mcp language:python"
"query": "fastmcp stars:>100 fork:false archived:false"
```

---

## 🎯 Current MCP Status

- ✅ **GitHub MCP** - 2 tools (search_repositories, get_file_contents)
- ✅ **Oracle MCP** - 8 tools (database monitoring & query analysis)
- ❌ **Filesystem MCP** - Disabled
- ❌ **Smoketest MCP** - Disabled

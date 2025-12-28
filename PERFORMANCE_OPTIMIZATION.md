# ⚡ OMNI2 Performance Optimization Guide

## 📊 Current Performance Analysis

### Timing Breakdown (from logs):
```
13:28:31.690 - Loop iteration 1 starts
13:28:34.978 - Tool execution starts (3.3s for LLM thinking)
13:28:34.979 - Calling database_mcp tool
13:28:41.977 - Tool execution complete (6.9s for database query)
```

**Total time: ~10 seconds**
- **LLM thinking**: 3.3s
- **Database query**: 6.9s
- **Other overhead**: ~0.5s

---

## 🚀 Speed Optimization Options

### Option 1: Progressive Loading (Best UX) ⭐
**Show immediate feedback while processing**

**Implementation:**
```python
# In slack_bot_omni.py - handle_omni_command()

# Step 1: Show immediate ack
respond("🔄 Processing...")

# Step 2: Update with progress
respond("⚙️ Querying database_mcp...")

# Step 3: Show final result
respond(formatted_response)
```

**Benefits:**
- ✅ User sees progress immediately
- ✅ Feels faster even if total time is same
- ✅ Better UX for long queries (>5s)

**Effort:** Medium (2-3 hours)

---

### Option 2: Tool Schema Caching ⭐⭐
**Cache MCP tool schemas instead of refetching**

**Current Problem:**
Every health check (30s) reconnects to MCPs and refetches tools:
```
Fetching tools from database_mcp...
Creating MCP client...
MCP client connected...
Successfully fetched tools: 8
```

**Solution:**
```python
# In mcp_client.py
class MCPClient:
    def __init__(self):
        self._tool_cache = {}  # Cache by mcp_name
        self._cache_ttl = 300  # 5 minutes
    
    async def list_tools(self, mcp_name: str):
        # Check cache first
        if mcp_name in self._tool_cache:
            cached = self._tool_cache[mcp_name]
            if time.time() - cached['timestamp'] < self._cache_ttl:
                return cached['tools']
        
        # Fetch and cache
        tools = await self._fetch_tools(mcp_name)
        self._tool_cache[mcp_name] = {
            'tools': tools,
            'timestamp': time.time()
        }
        return tools
```

**Benefits:**
- ✅ Faster startup (save ~2s)
- ✅ Faster /health checks
- ✅ Reduced MCP load

**Effort:** Low (1 hour)

---

### Option 3: Parallel Tool Execution ⭐⭐⭐
**Run multiple tools concurrently**

**When useful:**
```python
# User asks: "Show health of transformer_master and way4_docker7"
# Current: Sequential (10s + 10s = 20s total)
# With parallel: Concurrent (max(10s, 10s) = 10s total)
```

**Implementation:**
```python
# In llm_service.py - ask() method
if len(tool_uses) > 1:
    # Execute tools in parallel
    results = await asyncio.gather(*[
        self.mcp_client.call_tool(...)
        for tool in tool_uses
    ])
else:
    # Single tool - execute normally
    result = await self.mcp_client.call_tool(...)
```

**Benefits:**
- ✅ Up to 2-5x faster for multi-tool queries
- ✅ Better resource utilization

**Caution:**
- ❌ Only works for INDEPENDENT tools
- ❌ Won't help if tool 2 needs result from tool 1

**Effort:** Medium (2-3 hours)

---

### Option 4: Database Query Optimization 🔧
**Optimize the actual SQL queries in database_mcp**

**Current Slow Query:**
```sql
-- list_available_databases takes ~7 seconds
SELECT DISTINCT name FROM v$database ...
```

**Potential Fixes:**
- Add indexes on frequently queried columns
- Optimize view queries (v$database, v$session, etc.)
- Cache database list (changes rarely)
- Use lighter queries for "list" operations

**Benefits:**
- ✅ 50-80% reduction in database query time
- ✅ Applies to ALL database queries

**Effort:** High (4-6 hours, requires database analysis)

---

### Option 5: Streaming Responses (Advanced) 🚀
**Stream LLM response as it generates**

**How it works:**
```python
# Instead of waiting for full response:
response = client.messages.create(...)  # Wait for all
send_to_slack(response)

# Stream tokens as they arrive:
async for chunk in client.messages.stream(...):
    send_to_slack(chunk)  # Update Slack message incrementally
```

**Benefits:**
- ✅ Feels MUCH faster (see first words in 1-2s)
- ✅ Better for long responses

**Challenges:**
- ❌ Slack API limits (3 updates per second)
- ❌ Complex with tool calls (need to buffer)
- ❌ Anthropic streaming API is more complex

**Effort:** Very High (8-12 hours)

---

## 🎯 Recommended Implementation Order

### Phase 1: Quick Wins (Week 1)
1. **Slack formatting** ✅ DONE
   - Better UX without speed changes
   - Makes responses feel snappier

2. **Tool schema caching** (1 hour)
   - Easy to implement
   - Immediate benefit for all queries

3. **Progressive loading** (2-3 hours)
   - Biggest perceived speed improvement
   - Low risk, high reward

### Phase 2: Performance (Week 2)
4. **Parallel tool execution** (2-3 hours)
   - Helps multi-database queries
   - Good for analytics

5. **Database query optimization** (4-6 hours)
   - Measure before/after with logs
   - Focus on slowest 3 queries

### Phase 3: Advanced (Future)
6. **Streaming responses** (8-12 hours)
   - Only if users still complain
   - Requires significant refactoring

---

## 📊 Expected Speed Improvements

| Optimization | Current | Expected | Improvement |
|-------------|---------|----------|-------------|
| **Baseline** | 10s | - | - |
| + Schema caching | 10s → 8s | 8s | 20% faster |
| + Progressive loading | 8s → 8s | Feels like 2s | 75% perceived |
| + Parallel tools (2 tools) | 20s → 10s | 10s | 50% faster |
| + DB optimization | 8s → 4s | 4s | 50% faster |
| **Combined (1+2+3+4)** | 10s → 4s | 4s | **60% faster** |

---

## 🧪 Testing Performance

### Add timing logs:
```python
# In llm_service.py
import time

async def ask(self, user_id, message):
    start = time.time()
    
    # ... your code ...
    
    llm_time = time.time() - start
    logger.info(f"⏱️ LLM request took {llm_time:.2f}s")
```

### Measure tool execution:
```python
# In mcp_client.py
async def call_tool(self, mcp_name, tool_name, arguments):
    start = time.time()
    result = await self._execute_tool(...)
    duration = time.time() - start
    
    logger.info(
        f"⏱️ Tool execution",
        mcp=mcp_name,
        tool=tool_name,
        duration=f"{duration:.2f}s"
    )
    return result
```

---

## 💬 Slack Formatting (DONE ✅)

**Added to system prompt:**
- Use *bold* not **double**
- Use `code` for technical terms
- Use • for bullets
- Keep sentences short
- Emojis: ✅ ❌ ⚠️ 📊 🚀 only
- Format tables clearly
- Start with TL;DR for long responses
- Use "→" for cause/effect
- NO markdown headers (#)

**Example good format:**
```
*Database Health: transformer_master*

Status: ✅ Healthy
• Uptime: 45 days
• Connections: 142/200 (71%)
• Top wait event: `log file sync` (15%)

*Action Items:*
1. Monitor `log file sync` - nearing threshold
2. Consider connection pooling review
```

---

## 🔍 Next Steps

1. **Test Slack formatting** - Try `/omni show available dbs` in Slack
2. **Implement tool caching** - Quick win (1 hour)
3. **Add progressive loading** - Best UX improvement (2-3 hours)
4. **Measure before/after** - Use timing logs to validate improvements

**Expected result:** 60% faster responses with much better perceived speed.

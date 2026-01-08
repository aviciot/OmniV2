"""
LLM Service

Handles communication with Claude (Anthropic) for intelligent MCP routing.
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
import os
import anthropic
from anthropic.types import Message, ToolUseBlock, TextBlock

from app.config import settings
from app.services.mcp_client import get_mcp_client
from app.services.user_service import get_user_service
from app.utils.logger import logger


class LLMService:
    """Service for LLM-powered MCP routing and question answering."""
    
    # Maximum iterations for agentic loop (prevent infinite loops)
    MAX_ITERATIONS = 10
    
    def __init__(self):
        """Initialize LLM service with Anthropic client."""
        # Use settings object instead of os.getenv for proper config loading
        api_key = settings.llm.api_key
        if not api_key or api_key == "your-anthropic-api-key-here":
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Get one from https://console.anthropic.com/"
            )
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.async_client = None
        if hasattr(anthropic, "AsyncAnthropic"):
            try:
                self.async_client = anthropic.AsyncAnthropic(api_key=api_key)
            except Exception:
                self.async_client = None
        self.model = settings.llm.model  # Use from settings, not os.getenv
        self.max_tokens = settings.llm.max_tokens  # Use from settings
        self.mcp_client = get_mcp_client()
        self.user_service = get_user_service()
        
        # Log the model being used
        logger.info(f"🤖 LLM Service initialized with model: {self.model}")
        
        # Enable prompt caching (Anthropic-specific feature)
        # NOTE: Prompt caching is Anthropic-specific. When adding other LLM providers,
        # make this conditional based on provider type.
        self.use_prompt_caching = True
        
    async def build_system_prompt(self, user_id: str, is_admin_dashboard: bool = False) -> str:
        """
        Build dynamic system prompt based on user's permissions.
        
        Args:
            user_id: User email address
            is_admin_dashboard: Whether request is from admin dashboard (more technical/detailed responses)
            
        Returns:
            System prompt string
        """
        user = await self.user_service.get_user(user_id)
        user_role = user.get("role", "read_only")
        allowed_mcps = await self.user_service.get_allowed_mcps(user_id)
        allowed_domains = await self.user_service.get_allowed_domains(user_id)
        
        # Get available tools for user's allowed MCPs with tool-level filtering
        tools_catalog = []
        
        if allowed_mcps == "*":
            # Admin - get all MCPs and all tools
            all_tools = await self.mcp_client.list_tools()
            for mcp_name, mcp_data in all_tools.get("servers", {}).items():
                if mcp_data.get("status") == "healthy":
                    for tool in mcp_data.get("tools", []):
                        tools_catalog.append({
                            "mcp": mcp_name,
                            "name": tool["name"],
                            "description": tool["description"],
                        })
        else:
            # Regular user - filter by allowed MCPs and tools
            # Handle both old format (list) and new format (dict)
            mcp_list = []
            if isinstance(allowed_mcps, list):
                mcp_list = allowed_mcps
            elif isinstance(allowed_mcps, dict):
                mcp_list = list(allowed_mcps.keys())
            
            for mcp_name in mcp_list:
                try:
                    mcp_tools_response = await self.mcp_client.list_tools(mcp_name)
                    all_tools_in_mcp = mcp_tools_response.get("servers", {}).get(mcp_name, {}).get("tools", [])
                    
                    # Get list of all tool names for permission checking
                    all_tool_names = [t["name"] for t in all_tools_in_mcp]
                    
                    # Apply tool-level permissions
                    allowed_tool_names = await self.user_service.get_user_allowed_tools(
                        user_id, mcp_name, all_tool_names
                    )
                    
                    # Filter tools by user permissions
                    for tool in all_tools_in_mcp:
                        if tool["name"] in allowed_tool_names:
                            tools_catalog.append({
                                "mcp": mcp_name,
                                "name": tool["name"],
                                "description": tool["description"],
                            })
                        else:
                            logger.debug(
                                "Tool filtered for user",
                                user=user_id,
                                role=user_role,
                                mcp=mcp_name,
                                tool=tool["name"]
                            )
                    
                except Exception as e:
                    logger.warning(f"Could not load tools from {mcp_name}", error=str(e))
        
        logger.info(
            "Built tool catalog for user",
            user=user_id,
            role=user_role,
            total_tools=len(tools_catalog),
            mcps_accessed=len(set(t["mcp"] for t in tools_catalog))
        )
        
        # Build prompt - different style for admin dashboard
        if is_admin_dashboard:
            prompt = f"""You are OMNI2, an advanced MCP (Model Context Protocol) orchestration system for administrators.

Administrator User: {user.get('name', user_id)} ({user_role})
Context: Admin Dashboard (Technical/Detailed Mode)

AVAILABLE TOOLS:
You have full access to all MCP tools for system monitoring and management:
"""
            for tool in tools_catalog:
                prompt += f"\n- {tool['mcp']}.{tool['name']}: {tool['description']}"
            
            prompt += """

ADMIN-SPECIFIC BEHAVIOR:
1. **Technical Detail**: Provide detailed technical information, metrics, and logs
2. **Proactive Insights**: Suggest optimizations, potential issues, and best practices
3. **System Context**: Include relevant IDs, timestamps, configuration details
4. **Actionable**: Always provide next steps or recommended actions
5. **Tool Usage**: Use tools liberally to gather comprehensive data
6. **Multi-Tool Queries**: Don't hesitate to call multiple tools in sequence for complete analysis

RESPONSE STYLE:
- Technical but clear (assume admin-level knowledge)
- Include relevant metrics and thresholds
- Provide context for numbers (e.g., "142/200 connections (71% utilization)")
- Highlight anomalies or areas needing attention
- Use structured formatting (tables, lists, sections)
- Include timestamps when relevant

WHEN TO USE TOOLS:
- Status checks → Always use tools (don't rely on cached knowledge)
- Performance queries → Gather metrics from appropriate MCPs
- Troubleshooting → Check logs, health, recent changes
- User info → Query user management tools
- MCP status → Check health endpoints

Example Admin Response Format:
*MCP Server Status*

Healthy Servers: 3/4 (75%)
• informatica_mcp: ✅ Online (uptime: 12h 45m)
• database_mcp: ✅ Online (uptime: 3d 2h)
• qa_mcp: ✅ Online (uptime: 8h 12m)
• analytics_mcp: ❌ Offline (last seen: 2h ago)

*Attention Required:*
⚠️ analytics_mcp connection lost - check Docker container logs
⚠️ informatica_mcp restarted recently - verify data pipeline

*System Health: 85%*
Recommendation: Investigate analytics_mcp failure, review recent deployments
"""
        else:
            # Standard user prompt
            prompt = f"""You are OMNI2, an intelligent MCP (Model Context Protocol) router and assistant.

User: {user.get('name', user_id)} ({user_role})

AVAILABLE TOOLS:
You can call these MCP tools to help the user:
"""
        
            for tool in tools_catalog:
                prompt += f"\n- {tool['mcp']}.{tool['name']}: {tool['description']}"
        
            prompt += f"""

ALLOWED KNOWLEDGE DOMAINS:
"""
        
            if allowed_domains == "*":
                prompt += "- You can answer questions about ANY topic.\n"
            else:
                for domain in allowed_domains:
                    domain_desc = {
                        "general_knowledge": "General questions (TV shows, history, etc.)",
                        "python_help": "Python programming help and code examples",
                        "code_review": "Code review and best practices",
                        "database_help": "Database concepts and SQL help",
                        "sql_help": "SQL query writing and optimization",
                        "testing_help": "Software testing strategies",
                        "data_analysis": "Data analysis and interpretation",
                    }.get(domain, domain)
                    prompt += f"- {domain_desc}\n"
        
            prompt += """
RULES:
1. If the question requires MCP tool → Use function calling to execute the tool
2. If the question is general knowledge (in allowed domains) → Answer directly
3. If the question is outside your scope → Politely explain what you CAN help with
4. Always be helpful, accurate, and concise
5. If a tool fails, explain the error and suggest alternatives
6. When a tool returns pre-formatted output (with boxes, tables, or structured layout), present it exactly as-is using code blocks

SLACK FORMATTING (when user context includes slack_context):
- Use *bold* for emphasis, not **double**
- Use `code` for SQL, numbers, table names
- Use • for bullet points
- Keep sentences short and scannable
- Use emojis sparingly (✅ ❌ ⚠️ 📊 🚀 only)
- Format tables clearly with proper spacing
- Group related info with blank lines
- Start with TL;DR for long responses
- Use "→" for showing cause/effect
- NO markdown headers (#), use *Section Name* instead
- For pre-formatted tool output: Wrap in ```code blocks``` to preserve formatting

Example Good Slack Format:
*Database Health: transformer_master*

Status: ✅ Healthy
• Uptime: 45 days
• Connections: 142/200 (71%)
• Top wait event: `log file sync` (15%)

*Action Items:*
1. Monitor `log file sync` - nearing threshold
2. Consider connection pooling review

Example Bad Format:
## Database Health
The database transformer_master is healthy. It has been up for 45 days...

When calling tools, use the exact tool name and provide all required arguments.
"""
        
        return prompt
    
    async def build_tools_for_claude(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Build Claude function definitions from MCP tools.
        
        Args:
            user_id: User email address
            
        Returns:
            List of tool definitions for Claude
        """
        user = await self.user_service.get_user(user_id)
        user_role = user.get("role", "read_only")
        allowed_mcps = await self.user_service.get_allowed_mcps(user_id)
        claude_tools = []
        
        if allowed_mcps == "*":
            # Admin - all tools
            all_tools = await self.mcp_client.list_tools()
            for mcp_name, mcp_data in all_tools.get("servers", {}).items():
                if mcp_data.get("status") == "healthy":
                    for tool in mcp_data.get("tools", []):
                        claude_tools.append({
                            "name": f"{mcp_name}__{tool['name']}",  # Prefix with MCP name
                            "description": f"[{mcp_name}] {tool['description']}",
                            "input_schema": tool["inputSchema"],
                        })
        else:
            # Regular user - filter by MCP and tool-level permissions
            mcp_list = []
            if isinstance(allowed_mcps, list):
                mcp_list = allowed_mcps
            elif isinstance(allowed_mcps, dict):
                mcp_list = list(allowed_mcps.keys())
            
            for mcp_name in mcp_list:
                try:
                    mcp_tools_response = await self.mcp_client.list_tools(mcp_name)
                    all_tools_in_mcp = mcp_tools_response.get("servers", {}).get(mcp_name, {}).get("tools", [])
                    
                    # Get tool names for permission checking
                    all_tool_names = [t["name"] for t in all_tools_in_mcp]
                    
                    # Apply tool-level permissions
                    allowed_tool_names = await self.user_service.get_user_allowed_tools(
                        user_id, mcp_name, all_tool_names
                    )
                    
                    # Build Claude tools only for allowed tools
                    for tool in all_tools_in_mcp:
                        if tool["name"] in allowed_tool_names:
                            claude_tools.append({
                                "name": f"{mcp_name}__{tool['name']}",
                                "description": f"[{mcp_name}] {tool['description']}",
                                "input_schema": tool["inputSchema"],
                            })
                except Exception as e:
                    logger.warning(f"Could not load tools from {mcp_name}", error=str(e))
        
        logger.info(
            "Built Claude tools",
            user=user_id,
            role=user_role,
            tool_count=len(claude_tools)
        )
        
        return claude_tools
    
    async def ask(self, user_id: str, message: str, is_admin_dashboard: bool = False) -> Dict[str, Any]:
        """
        Process user question with LLM routing using agentic loop.
        
        Implements multi-step tool execution where Claude can call multiple tools
        sequentially based on previous results.
        
        Args:
            user_id: User email address
            message: User's question
            is_admin_dashboard: Whether request is from admin dashboard (affects system prompt)
            
        Returns:
            Response dict with answer and metadata
        """
        logger.info(
            "🤖 Starting LLM request",
            user=user_id,
            message=message[:100] + "..." if len(message) > 100 else message,
            admin_mode=is_admin_dashboard,
        )
        
        # Build system prompt and tools
        system_prompt = await self.build_system_prompt(user_id, is_admin_dashboard=is_admin_dashboard)
        claude_tools = await self.build_tools_for_claude(user_id)
        
        # Initialize conversation with system prompt
        # Use prompt caching for Anthropic to save costs on repeated system prompts
        system_messages = [{"role": "user", "content": message}]
        
        # Track all tool results across iterations
        all_tool_results = []
        
        if self.use_prompt_caching:
            # Anthropic prompt caching: mark system prompt as cacheable
            # This saves ~90% on input tokens for iterations 2+ (cached for 5 min)
            system_config = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        else:
            system_config = system_prompt
        
        # Track metadata
        total_tool_calls = 0
        all_tools_used = []
        iteration_count = 0
        
        # Track token usage across all iterations
        total_input_tokens = 0
        total_output_tokens = 0
        total_cached_tokens = 0
        
        # Agentic loop: Keep calling Claude until it's done (no more tool calls)
        while iteration_count < self.MAX_ITERATIONS:
            iteration_count += 1
            
            logger.info(
                f"🔄 Loop iteration {iteration_count}",
                user=user_id,
                tools_so_far=len(all_tools_used),
            )
            
            try:
                # Call Claude
                logger.info(
                    f"🤖 Sending request to Claude",
                    model=self.model,
                    max_tokens=self.max_tokens,
                    user=user_id,
                    iteration=iteration_count,
                )
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_config,
                    tools=claude_tools if claude_tools else None,
                    messages=system_messages,
                )
                
                # Extract token usage from response
                if hasattr(response, 'usage'):
                    total_input_tokens += response.usage.input_tokens
                    total_output_tokens += response.usage.output_tokens
                    # Cached tokens (prompt caching feature)
                    if hasattr(response.usage, 'cache_read_input_tokens'):
                        total_cached_tokens += response.usage.cache_read_input_tokens
                
                # Check for tool use
                tool_uses = [block for block in response.content if isinstance(block, ToolUseBlock)]
                
                if not tool_uses:
                    # No more tool calls - Claude is done, extract final answer
                    text_blocks = [block for block in response.content if isinstance(block, TextBlock)]
                    final_answer = "\n".join(block.text for block in text_blocks)
                    
                    logger.info(
                        f"✅ LLM request completed",
                        user=user_id,
                        iterations=iteration_count,
                        total_tools=total_tool_calls,
                        tools_used=all_tools_used,
                        tokens_input=total_input_tokens,
                        tokens_output=total_output_tokens,
                        tokens_cached=total_cached_tokens,
                    )
                    
                    return {
                        "answer": final_answer,
                        "tool_calls": total_tool_calls,
                        "tools_used": all_tools_used,
                        "tool_results": all_tool_results,  # Add raw tool results
                        "iterations": iteration_count,
                        "tokens_input": total_input_tokens,
                        "tokens_output": total_output_tokens,
                        "tokens_cached": total_cached_tokens,
                    }
                
                # Execute tools
                logger.info(
                    f"🔧 Executing {len(tool_uses)} tool(s)",
                    user=user_id,
                    tools=[t.name for t in tool_uses],
                )
                
                tool_results = []
                for tool_use in tool_uses:
                    tool_full_name = tool_use.name  # e.g., "github_mcp__search_repositories"
                    mcp_name, tool_name = tool_full_name.split("__", 1)
                    
                    try:
                        # Call the actual MCP tool
                        tool_result = await self.mcp_client.call_tool(
                            server_name=mcp_name,
                            tool_name=tool_name,
                            arguments=tool_use.input,
                        )
                        
                        # Store the actual tool result data
                        all_tool_results.append({
                            "mcp": mcp_name,
                            "tool": tool_name,
                            "arguments": tool_use.input,
                            "result": tool_result,  # Raw result from tool
                        })
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(tool_result),
                        })
                        
                        all_tools_used.append(f"{mcp_name}.{tool_name}")
                        total_tool_calls += 1
                        
                        logger.info(
                            f"✓ Tool executed successfully",
                            mcp=mcp_name,
                            tool=tool_name,
                        )
                        
                    except Exception as e:
                        logger.error(
                            f"✗ Tool execution failed",
                            mcp=mcp_name,
                            tool=tool_name,
                            error=str(e),
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Error: {str(e)}",
                            "is_error": True,
                        })
                
                # Add assistant response and tool results to conversation
                system_messages.append({"role": "assistant", "content": response.content})
                system_messages.append({"role": "user", "content": tool_results})
                
                # Loop back to let Claude continue with tool results
                
            except Exception as e:
                logger.error(
                    "❌ LLM request failed",
                    user=user_id,
                    iteration=iteration_count,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
        
        # Max iterations reached
        logger.warning(
            f"⚠️ Max iterations reached ({self.MAX_ITERATIONS})",
            user=user_id,
            total_tools=total_tool_calls,
            tokens_input=total_input_tokens,
            tokens_output=total_output_tokens,
            tokens_cached=total_cached_tokens,
        )
        
        return {
            "answer": f"Maximum iteration limit ({self.MAX_ITERATIONS}) reached. Partial results returned.",
            "tool_calls": total_tool_calls,
            "tools_used": all_tools_used,
            "iterations": iteration_count,
            "warning": "max_iterations_reached",
            "tokens_input": total_input_tokens,
            "tokens_output": total_output_tokens,
            "tokens_cached": total_cached_tokens,
        }

    async def ask_stream(
        self,
        user_id: str,
        message: str,
        is_admin_dashboard: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a chat response using Anthropic streaming API when available.

        Yields:
            Dict events with type: "token", "done", or "error".
        """
        logger.info(
            "Starting LLM streaming request",
            user=user_id,
            message=message[:100] + "..." if len(message) > 100 else message,
            admin_mode=is_admin_dashboard,
        )

        system_prompt = await self.build_system_prompt(user_id, is_admin_dashboard=is_admin_dashboard)
        system_prompt += (
            "\n\nSTREAMING RULES:\n"
            "- If you need tools, respond ONLY with tool_use blocks and no text.\n"
            "- Only emit user-facing text after all tool calls are complete.\n"
        )
        claude_tools = await self.build_tools_for_claude(user_id)

        system_messages = [{"role": "user", "content": message}]

        if self.use_prompt_caching:
            system_config = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_config = system_prompt

        total_tool_calls = 0
        all_tools_used = []
        iteration_count = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cached_tokens = 0

        while iteration_count < self.MAX_ITERATIONS:
            iteration_count += 1
            final_message = None

            try:
                if self.async_client is not None:
                    async with self.async_client.messages.stream(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=system_config,
                        tools=claude_tools if claude_tools else None,
                        messages=system_messages,
                    ) as stream:
                        async for text in stream.text_stream:
                            if text:
                                yield {"type": "token", "text": text}
                        final_message = await stream.get_final_message()
                else:
                    with self.client.messages.stream(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=system_config,
                        tools=claude_tools if claude_tools else None,
                        messages=system_messages,
                    ) as stream:
                        for text in stream.text_stream:
                            if text:
                                yield {"type": "token", "text": text}
                        final_message = stream.get_final_message()

                if hasattr(final_message, "usage"):
                    total_input_tokens += getattr(final_message.usage, "input_tokens", 0)
                    total_output_tokens += getattr(final_message.usage, "output_tokens", 0)
                    total_cached_tokens += getattr(final_message.usage, "cache_read_input_tokens", 0)

                tool_uses = [
                    block for block in final_message.content
                    if isinstance(block, ToolUseBlock)
                ]

                if not tool_uses:
                    text_blocks = [
                        block for block in final_message.content
                        if isinstance(block, TextBlock)
                    ]
                    final_answer = "\n".join(block.text for block in text_blocks)

                    yield {
                        "type": "done",
                        "result": {
                            "answer": final_answer,
                            "tool_calls": total_tool_calls,
                            "tools_used": all_tools_used,
                            "iterations": iteration_count,
                            "tokens_input": total_input_tokens,
                            "tokens_output": total_output_tokens,
                            "tokens_cached": total_cached_tokens,
                        },
                    }
                    return

                tool_results = []
                for tool_use in tool_uses:
                    tool_full_name = tool_use.name
                    mcp_name, tool_name = tool_full_name.split("__", 1)
                    try:
                        tool_result = await self.mcp_client.call_tool(
                            server_name=mcp_name,
                            tool_name=tool_name,
                            arguments=tool_use.input,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(tool_result),
                        })
                        all_tools_used.append(f"{mcp_name}.{tool_name}")
                        total_tool_calls += 1
                    except Exception as e:
                        logger.error(
                            "Tool execution failed",
                            mcp=mcp_name,
                            tool=tool_name,
                            error=str(e),
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Error: {str(e)}",
                            "is_error": True,
                        })

                system_messages.append({"role": "assistant", "content": final_message.content})
                system_messages.append({"role": "user", "content": tool_results})

            except Exception as e:
                logger.error(
                    "Streaming LLM request failed",
                    user=user_id,
                    iteration=iteration_count,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                yield {"type": "error", "error": str(e)}
                return

        yield {
            "type": "done",
            "result": {
                "answer": f"Maximum iteration limit ({self.MAX_ITERATIONS}) reached. Partial results returned.",
                "tool_calls": total_tool_calls,
                "tools_used": all_tools_used,
                "iterations": iteration_count,
                "warning": "max_iterations_reached",
                "tokens_input": total_input_tokens,
                "tokens_output": total_output_tokens,
                "tokens_cached": total_cached_tokens,
            },
        }

# Global LLM service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get or create the global LLM service instance.
    
    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

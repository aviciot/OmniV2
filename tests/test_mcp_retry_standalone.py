"""
Test MCP Client Retry Logic - Standalone Version

This script tests the retry logic concepts independently without importing the actual app.
Run with: python tests/test_mcp_retry_standalone.py
"""

import asyncio
import sys
import time
from typing import Dict, Any, Tuple
from unittest.mock import MagicMock


# ============================================================
# Extracted retry logic for testing (mirrors mcp_client.py)
# ============================================================

DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_CONNECTION_MAX_AGE = 600


class MockMCPClient:
    """Simplified MCP client for testing retry logic."""
    
    def __init__(self):
        self.servers: Dict[str, Dict] = {}
        self._client_cache: Dict[str, Any] = {}
        self._client_created_at: Dict[str, float] = {}
        self._global_retry = {}
        self._invalidate_count = 0
    
    def _get_retry_config(self, server_name: str) -> Tuple[int, float, int]:
        """Get retry config (MCP-specific or global fallback)."""
        server_config = self.servers.get(server_name, {})
        mcp_retry = server_config.get("retry", {}) or {}
        
        max_attempts = (
            mcp_retry.get("max_attempts") or 
            self._global_retry.get("max_attempts") or 
            DEFAULT_MAX_ATTEMPTS
        )
        delay_seconds = (
            mcp_retry.get("delay_seconds") or 
            self._global_retry.get("delay_seconds") or 
            DEFAULT_DELAY_SECONDS
        )
        connection_max_age = (
            mcp_retry.get("connection_max_age_seconds") or 
            self._global_retry.get("connection_max_age_seconds") or 
            DEFAULT_CONNECTION_MAX_AGE
        )
        
        return max_attempts, delay_seconds, connection_max_age
    
    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error is connection-related (worth retrying)."""
        connection_error_types = (
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
            TimeoutError,
            OSError,
        )
        
        if isinstance(error, connection_error_types):
            return True
        
        error_msg = str(error).lower()
        connection_keywords = [
            "connection refused",
            "connection reset",
            "connection closed",
            "connect timeout",
            "timed out",
            "network unreachable",
            "broken pipe",
            "eof",
            "stream",
            "transport",
        ]
        
        return any(keyword in error_msg for keyword in connection_keywords)
    
    async def _invalidate_client(self, server_name: str):
        """Safely remove a client from cache."""
        self._client_cache.pop(server_name, None)
        self._client_created_at.pop(server_name, None)
        self._invalidate_count += 1
    
    async def call_tool_with_retry(
        self,
        server_name: str,
        tool_func,  # Callable that may fail
    ) -> Dict[str, Any]:
        """
        Call a tool with retry logic on connection failures.
        This mirrors the actual implementation in mcp_client.py.
        """
        server_config = self.servers.get(server_name, {})
        display_name = server_config.get("display_name", server_name)
        max_attempts, delay_seconds, _ = self._get_retry_config(server_name)
        
        last_error = None
        reconnected = False
        
        for attempt in range(1, max_attempts + 1):
            try:
                result = await tool_func()
                
                response = {
                    "result": result,
                    "status": "success",
                    "server": server_name,
                    "attempt": attempt,
                }
                
                if reconnected:
                    response["notice"] = f"⚠️ Reconnected to {display_name}"
                
                return response
                
            except Exception as e:
                last_error = e
                is_conn_error = self._is_connection_error(e)
                
                # Only retry on connection errors
                if not is_conn_error:
                    break
                
                if attempt < max_attempts:
                    await self._invalidate_client(server_name)
                    await asyncio.sleep(delay_seconds)
                    reconnected = True
        
        # All attempts failed
        return {
            "result": None,
            "status": "error",
            "error": f"❌ {display_name} unavailable after {max_attempts} attempts: {last_error}",
            "server": server_name,
        }


# ============================================================
# Tests
# ============================================================

async def test_config_inheritance():
    """Test that MCP-specific config overrides global."""
    print("\n" + "=" * 60)
    print("TEST: Config Inheritance")
    print("=" * 60)
    
    client = MockMCPClient()
    
    # MCP with custom retry
    client.servers = {
        "custom_mcp": {
            "name": "custom_mcp",
            "retry": {
                "max_attempts": 5,
                "delay_seconds": 3,
            }
        },
        "default_mcp": {
            "name": "default_mcp",
            # No retry config - uses global
        }
    }
    client._global_retry = {
        "max_attempts": 2,
        "delay_seconds": 1,
        "connection_max_age_seconds": 300,
    }
    
    # Test custom MCP
    max_attempts, delay, max_age = client._get_retry_config("custom_mcp")
    print(f"  → custom_mcp: max_attempts={max_attempts}, delay={delay}s")
    assert max_attempts == 5, f"Expected 5, got {max_attempts}"
    assert delay == 3, f"Expected 3, got {delay}"
    
    # Test default MCP (should use global)
    max_attempts, delay, max_age = client._get_retry_config("default_mcp")
    print(f"  → default_mcp: max_attempts={max_attempts}, delay={delay}s")
    assert max_attempts == 2, f"Expected 2, got {max_attempts}"
    assert delay == 1, f"Expected 1, got {delay}"
    
    # Test unknown MCP (should use hardcoded defaults)
    max_attempts, delay, max_age = client._get_retry_config("unknown_mcp")
    print(f"  → unknown_mcp: max_attempts={max_attempts}, delay={delay}s")
    assert max_attempts == 2  # DEFAULT_MAX_ATTEMPTS
    
    print("  ✅ PASSED: Config inheritance works correctly\n")


async def test_connection_error_detection():
    """Test that connection errors are correctly identified."""
    print("\n" + "=" * 60)
    print("TEST: Connection Error Detection")
    print("=" * 60)
    
    client = MockMCPClient()
    
    connection_errors = [
        ConnectionError("Connection refused"),
        ConnectionResetError("Connection reset by peer"),
        TimeoutError("Connection timed out"),
        OSError("Network unreachable"),
        Exception("transport closed"),
        Exception("stream error"),
    ]
    
    non_connection_errors = [
        ValueError("Invalid parameter"),
        KeyError("missing_key"),
        Exception("Invalid SQL syntax"),
        Exception("Permission denied"),
    ]
    
    print("  → Testing connection errors (should retry):")
    for err in connection_errors:
        is_conn = client._is_connection_error(err)
        status = "✓" if is_conn else "✗"
        print(f"    {status} {type(err).__name__}: {str(err)[:40]}")
        assert is_conn, f"Expected {err} to be connection error"
    
    print("\n  → Testing non-connection errors (should NOT retry):")
    for err in non_connection_errors:
        is_conn = client._is_connection_error(err)
        status = "✓" if not is_conn else "✗"
        print(f"    {status} {type(err).__name__}: {str(err)[:40]}")
        assert not is_conn, f"Expected {err} to NOT be connection error"
    
    print("\n  ✅ PASSED: Connection error detection works\n")


async def test_retry_on_connection_failure():
    """Test that call_tool retries on connection failure."""
    print("\n" + "=" * 60)
    print("TEST: Retry on Connection Failure")
    print("=" * 60)
    
    client = MockMCPClient()
    client.servers = {
        "test_mcp": {
            "name": "test_mcp",
            "display_name": "Test MCP",
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 0.1,  # Fast for testing
            }
        }
    }
    
    # Create a function that fails first 2 times, succeeds on 3rd
    call_count = 0
    
    async def flaky_tool():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ConnectionError(f"Connection refused (attempt {call_count})")
        return {"success": True}
    
    print(f"  → Calling tool (will fail first 2 attempts)...")
    start = time.time()
    
    result = await client.call_tool_with_retry("test_mcp", flaky_tool)
    
    elapsed = time.time() - start
    
    print(f"  → Result status: {result['status']}")
    print(f"  → Total attempts: {call_count}")
    print(f"  → Invalidation count: {client._invalidate_count}")
    print(f"  → Time elapsed: {elapsed:.2f}s")
    
    assert result["status"] == "success", f"Expected success, got {result['status']}"
    assert call_count == 3, f"Expected 3 attempts, got {call_count}"
    assert client._invalidate_count == 2, f"Expected 2 invalidations, got {client._invalidate_count}"
    
    if "notice" in result:
        print(f"  → User notice: {result['notice']}")
    
    print("  ✅ PASSED: Retry succeeded after reconnection\n")


async def test_max_retries_exceeded():
    """Test that error is returned when all retries fail."""
    print("\n" + "=" * 60)
    print("TEST: Max Retries Exceeded")
    print("=" * 60)
    
    client = MockMCPClient()
    client.servers = {
        "failing_mcp": {
            "name": "failing_mcp",
            "display_name": "Failing MCP",
            "retry": {
                "max_attempts": 2,
                "delay_seconds": 0.1,
            }
        }
    }
    
    call_count = 0
    
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Connection refused")
    
    print(f"  → Calling tool (will always fail)...")
    
    result = await client.call_tool_with_retry("failing_mcp", always_fail)
    
    print(f"  → Result status: {result['status']}")
    print(f"  → Total attempts: {call_count}")
    print(f"  → Error message: {result.get('error', 'N/A')[:60]}...")
    
    assert result["status"] == "error", f"Expected error, got {result['status']}"
    assert call_count == 2, f"Expected 2 attempts, got {call_count}"
    assert "unavailable" in result["error"].lower()
    
    print("  ✅ PASSED: Proper error returned after max retries\n")


async def test_no_retry_on_business_error():
    """Test that business logic errors don't trigger retry."""
    print("\n" + "=" * 60)
    print("TEST: No Retry on Business Logic Error")
    print("=" * 60)
    
    client = MockMCPClient()
    client.servers = {
        "test_mcp": {
            "name": "test_mcp",
            "display_name": "Test MCP",
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 0.1,
            }
        }
    }
    
    call_count = 0
    
    async def business_error():
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid query syntax")  # Not a connection error
    
    print(f"  → Calling tool (raises ValueError)...")
    
    result = await client.call_tool_with_retry("test_mcp", business_error)
    
    print(f"  → Result status: {result['status']}")
    print(f"  → Total attempts: {call_count}")
    print(f"  → Invalidation count: {client._invalidate_count}")
    
    # Should not retry on ValueError - only 1 attempt
    assert result["status"] == "error"
    assert call_count == 1, f"Expected 1 attempt (no retry), got {call_count}"
    assert client._invalidate_count == 0, "Should not invalidate on business error"
    
    print("  ✅ PASSED: No retry on business logic error\n")


async def test_immediate_success():
    """Test that successful calls don't add any overhead."""
    print("\n" + "=" * 60)
    print("TEST: Immediate Success (No Retry Needed)")
    print("=" * 60)
    
    client = MockMCPClient()
    client.servers = {
        "fast_mcp": {
            "name": "fast_mcp",
            "display_name": "Fast MCP",
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 1,
            }
        }
    }
    
    call_count = 0
    
    async def success_tool():
        nonlocal call_count
        call_count += 1
        return {"data": "success"}
    
    print(f"  → Calling tool (will succeed immediately)...")
    start = time.time()
    
    result = await client.call_tool_with_retry("fast_mcp", success_tool)
    
    elapsed = time.time() - start
    
    print(f"  → Result status: {result['status']}")
    print(f"  → Total attempts: {call_count}")
    print(f"  → Time elapsed: {elapsed:.4f}s")
    
    assert result["status"] == "success"
    assert call_count == 1, f"Expected 1 attempt, got {call_count}"
    assert "notice" not in result, "Should not have reconnect notice"
    assert elapsed < 0.1, f"Should be fast, took {elapsed}s"
    
    print("  ✅ PASSED: Immediate success with no overhead\n")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MCP CLIENT RETRY MECHANISM - TEST SUITE")
    print("=" * 60)
    
    try:
        await test_config_inheritance()
        await test_connection_error_detection()
        await test_retry_on_connection_failure()
        await test_max_retries_exceeded()
        await test_no_retry_on_business_error()
        await test_immediate_success()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60 + "\n")
        
        # Summary
        print("Retry mechanism is working correctly:")
        print("  • Config inheritance: MCP-specific → Global → Defaults")
        print("  • Connection errors: Detected and retried")
        print("  • Business errors: Not retried (fail fast)")
        print("  • Max attempts: Respected with proper error message")
        print("  • Success path: No overhead added")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

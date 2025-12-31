"""
Test MCP Client Retry Logic

This script tests the auto-reconnect feature by simulating connection failures.
Run with: python -m pytest tests/test_mcp_retry.py -v

Or run standalone: python tests/test_mcp_retry.py
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock fastmcp before importing mcp_client
sys.modules['fastmcp'] = MagicMock()
sys.modules['fastmcp.client'] = MagicMock()
sys.modules['fastmcp.client.transports'] = MagicMock()

# Mock app.config
mock_settings = MagicMock()
mock_settings.mcps.mcps = []
mock_settings.mcps.global_settings = {}
sys.modules['app'] = MagicMock()
sys.modules['app.config'] = MagicMock()
sys.modules['app.config'].settings = mock_settings
sys.modules['app.utils'] = MagicMock()
sys.modules['app.utils.logger'] = MagicMock()
sys.modules['app.utils.logger'].logger = MagicMock()


class MockClient:
    """Mock FastMCP client for testing."""
    
    def __init__(self, fail_count: int = 0):
        self.fail_count = fail_count
        self.call_count = 0
        self.connected = True
    
    async def list_tools(self):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ConnectionError(f"Connection refused (attempt {self.call_count})")
        
        # Return mock tools
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = MagicMock()
        mock_tool.inputSchema.model_dump = lambda: {"type": "object"}
        
        result = MagicMock()
        result.tools = [mock_tool]
        return result
    
    async def call_tool(self, tool_name: str, arguments: dict):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ConnectionError(f"Connection reset by peer (attempt {self.call_count})")
        
        result = MagicMock()
        result.content = {"success": True, "tool": tool_name}
        return result
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        self.connected = False


async def test_retry_on_connection_failure():
    """Test that call_tool retries on connection failure."""
    print("\n" + "=" * 60)
    print("TEST: Retry on Connection Failure")
    print("=" * 60)
    
    # Import here to avoid import errors during collection
    from app.services.mcp_client import MCPClient
    
    # Create client with mock server config
    client = MCPClient()
    client.servers = {
        "test_mcp": {
            "name": "test_mcp",
            "display_name": "Test MCP",
            "protocol": "http",
            "url": "http://localhost:9999/mcp",
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 0.1,  # Fast for testing
            }
        }
    }
    client._global_retry = {"max_attempts": 2, "delay_seconds": 0.5}
    
    # Create mock that fails first 2 times, succeeds on 3rd
    mock_client = MockClient(fail_count=2)
    
    async def mock_get_client(server_name):
        return mock_client
    
    # Patch _get_client to return our mock
    with patch.object(client, '_get_client', side_effect=mock_get_client):
        with patch.object(client, '_invalidate_client', new_callable=AsyncMock):
            
            print(f"  → Calling tool (mock will fail first 2 attempts)...")
            start = time.time()
            
            result = await client.call_tool(
                server_name="test_mcp",
                tool_name="test_tool",
                arguments={"query": "test"}
            )
            
            elapsed = time.time() - start
            
            print(f"  → Result status: {result['status']}")
            print(f"  → Total attempts: {mock_client.call_count}")
            print(f"  → Time elapsed: {elapsed:.2f}s")
            
            assert result["status"] == "success", f"Expected success, got {result['status']}"
            assert mock_client.call_count == 3, f"Expected 3 attempts, got {mock_client.call_count}"
            
            if "notice" in result:
                print(f"  → User notice: {result['notice']}")
            
            print("  ✅ PASSED: Retry succeeded after reconnection\n")


async def test_max_retries_exceeded():
    """Test that error is returned when all retries fail."""
    print("\n" + "=" * 60)
    print("TEST: Max Retries Exceeded")
    print("=" * 60)
    
    from app.services.mcp_client import MCPClient
    
    client = MCPClient()
    client.servers = {
        "failing_mcp": {
            "name": "failing_mcp",
            "display_name": "Failing MCP",
            "protocol": "http",
            "url": "http://localhost:9999/mcp",
            "retry": {
                "max_attempts": 2,
                "delay_seconds": 0.1,
            }
        }
    }
    client._global_retry = {}
    
    # Create mock that always fails
    mock_client = MockClient(fail_count=999)
    
    async def mock_get_client(server_name):
        return mock_client
    
    with patch.object(client, '_get_client', side_effect=mock_get_client):
        with patch.object(client, '_invalidate_client', new_callable=AsyncMock):
            
            print(f"  → Calling tool (mock will always fail)...")
            
            result = await client.call_tool(
                server_name="failing_mcp",
                tool_name="test_tool",
                arguments={}
            )
            
            print(f"  → Result status: {result['status']}")
            print(f"  → Total attempts: {mock_client.call_count}")
            print(f"  → Error message: {result.get('error', 'N/A')[:80]}...")
            
            assert result["status"] == "error", f"Expected error, got {result['status']}"
            assert mock_client.call_count == 2, f"Expected 2 attempts, got {mock_client.call_count}"
            assert "unavailable" in result["error"].lower()
            
            print("  ✅ PASSED: Proper error returned after max retries\n")


async def test_no_retry_on_business_error():
    """Test that business logic errors don't trigger retry."""
    print("\n" + "=" * 60)
    print("TEST: No Retry on Business Logic Error")
    print("=" * 60)
    
    from app.services.mcp_client import MCPClient
    
    client = MCPClient()
    client.servers = {
        "test_mcp": {
            "name": "test_mcp",
            "display_name": "Test MCP",
            "protocol": "http",
            "url": "http://localhost:9999/mcp",
            "retry": {
                "max_attempts": 3,
                "delay_seconds": 0.1,
            }
        }
    }
    client._global_retry = {}
    
    call_count = 0
    
    async def mock_get_client(server_name):
        nonlocal call_count
        call_count += 1
        # Raise a non-connection error (business logic)
        raise ValueError("Invalid query syntax")
    
    with patch.object(client, '_get_client', side_effect=mock_get_client):
        with patch.object(client, '_invalidate_client', new_callable=AsyncMock):
            
            print(f"  → Calling tool (mock raises ValueError)...")
            
            result = await client.call_tool(
                server_name="test_mcp",
                tool_name="test_tool",
                arguments={}
            )
            
            print(f"  → Result status: {result['status']}")
            print(f"  → Total attempts: {call_count}")
            
            # Should not retry on ValueError - only 1 attempt
            assert result["status"] == "error"
            assert call_count == 1, f"Expected 1 attempt (no retry), got {call_count}"
            
            print("  ✅ PASSED: No retry on business logic error\n")


async def test_config_inheritance():
    """Test that MCP-specific config overrides global."""
    print("\n" + "=" * 60)
    print("TEST: Config Inheritance")
    print("=" * 60)
    
    from app.services.mcp_client import MCPClient
    
    client = MCPClient()
    
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
    
    from app.services.mcp_client import MCPClient
    
    client = MCPClient()
    
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
    
    print("\n  → Testing non-connection errors (should not retry):")
    for err in non_connection_errors:
        is_conn = client._is_connection_error(err)
        status = "✓" if not is_conn else "✗"
        print(f"    {status} {type(err).__name__}: {str(err)[:40]}")
        assert not is_conn, f"Expected {err} to NOT be connection error"
    
    print("\n  ✅ PASSED: Connection error detection works\n")


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
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)
        
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

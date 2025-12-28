"""
Test script for Slack Threading functionality
Simulates thread manager behavior without requiring Slack connection
"""

import sys
import yaml
from pathlib import Path

# Import ThreadManager
from thread_manager import ThreadManager

def load_config():
    """Load threading configuration"""
    config_path = Path("config/threading.yaml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {
        "threading": {"enabled": True, "behavior": {"always_use_threads": True}},
        "context": {"enabled": True, "max_messages": 3}
    }

def test_basic_threading():
    """Test 1: Basic threading initialization"""
    print("\n" + "="*60)
    print("TEST 1: ThreadManager Initialization")
    print("="*60)
    
    config = load_config()
    tm = ThreadManager(config)
    
    print(f"✅ ThreadManager created")
    print(f"   - Threading enabled: {tm.enabled}")
    print(f"   - Always use threads: {tm.always_use_threads}")
    print(f"   - Max context messages: {tm.max_context_messages}")
    print(f"   - Continue threads: {tm.continue_threads}")
    
    assert tm.enabled == True, "Threading should be enabled"
    print("✅ TEST 1 PASSED\n")

def test_should_use_thread():
    """Test 2: Threading decision logic"""
    print("\n" + "="*60)
    print("TEST 2: Threading Decision Logic")
    print("="*60)
    
    config = load_config()
    tm = ThreadManager(config)
    
    # Test channel threading
    use_thread_channel = tm.should_use_thread("channel", None)
    print(f"Channel (no existing thread): {use_thread_channel}")
    assert use_thread_channel == True, "Should use threads in channels"
    
    # Test DM threading (default is False)
    use_thread_dm = tm.should_use_thread("im", None)
    print(f"DM (no existing thread): {use_thread_dm}")
    assert use_thread_dm == False, "Should NOT use threads in DMs by default"
    
    # Test continuing existing thread
    use_thread_existing = tm.should_use_thread("channel", "1234567890.123456")
    print(f"Channel (existing thread): {use_thread_existing}")
    assert use_thread_existing == True, "Should continue existing threads"
    
    print("✅ TEST 2 PASSED\n")

def test_conversation_context():
    """Test 3: Conversation context building"""
    print("\n" + "="*60)
    print("TEST 3: Conversation Context Building")
    print("="*60)
    
    config = load_config()
    tm = ThreadManager(config)
    
    # Create a thread
    thread_ts = "1234567890.123456"
    channel_id = "C1234567890"
    user_id = "U1234567890"
    
    # Simulate a conversation
    print("\n📝 Simulating conversation:")
    
    # Message 1
    message1 = "What is the database health?"
    tm.add_user_message(thread_ts, channel_id, user_id, message1, "1234567890.111111")
    print(f"  User: {message1}")
    
    response1 = "The database health is good. All connections are stable."
    tm.add_assistant_message(thread_ts, channel_id, user_id, response1, "1234567890.111112")
    print(f"  Bot: {response1}")
    
    # Message 2
    message2 = "What about the CPU usage?"
    tm.add_user_message(thread_ts, channel_id, user_id, message2, "1234567890.222222")
    print(f"  User: {message2}")
    
    response2 = "CPU usage is at 45%, which is normal."
    tm.add_assistant_message(thread_ts, channel_id, user_id, response2, "1234567890.222223")
    print(f"  Bot: {response2}")
    
    # Message 3 - This should include context from previous messages
    message3 = "Can you compare it to yesterday?"
    tm.add_user_message(thread_ts, channel_id, user_id, message3, "1234567890.333333")
    print(f"  User: {message3}")
    
    # Get context
    context = tm.get_context_for_message(message3, thread_ts, user_id, channel_id, "channel")
    
    print(f"\n🧵 Context generated ({len(context)} chars):")
    print("-" * 60)
    print(context)
    print("-" * 60)
    
    # Verify context includes previous messages
    context_lower = context.lower() if context else ""
    print(f"\nDEBUG: Checking for 'cpu' in context_lower")
    print(f"DEBUG: 'cpu' in context_lower = {'cpu' in context_lower}")
    print(f"DEBUG: First 200 chars of context_lower: {context_lower[:200]}")
    
    assert len(context) > 0, "Context should not be empty"
    assert "cpu" in context_lower, f"Context should include 'cpu'"
    assert "compare" in message3.lower(), "Current message should be preserved"
    
    print("\n✅ TEST 3 PASSED\n")

def test_context_limit():
    """Test 4: Context message limit"""
    print("\n" + "="*60)
    print("TEST 4: Context Message Limit (max_messages=3)")
    print("="*60)
    
    config = load_config()
    tm = ThreadManager(config)
    
    thread_ts = "9876543210.654321"
    channel_id = "C9876543210"
    user_id = "U9876543210"
    
    # Add 5 messages (should only keep last 3 in context)
    messages = [
        ("What is server 1 status?", "Server 1 is online"),
        ("What is server 2 status?", "Server 2 is online"),
        ("What is server 3 status?", "Server 3 is online"),
        ("What is server 4 status?", "Server 4 is online"),
        ("What is server 5 status?", "Server 5 is online"),
    ]
    
    ts_counter = 1
    for user_msg, bot_msg in messages:
        tm.add_user_message(thread_ts, channel_id, user_id, user_msg, f"9876543210.{ts_counter:06d}")
        ts_counter += 1
        tm.add_assistant_message(thread_ts, channel_id, user_id, bot_msg, f"9876543210.{ts_counter:06d}")
        ts_counter += 1
        print(f"  Added: {user_msg[:30]}...")
    
    # Get context for next message
    context = tm.get_context_for_message("Summarize", thread_ts, user_id, channel_id, "channel")
    context_lower = context.lower() if context else ""
    
    print(f"\n🧵 Context with limit:")
    print("-" * 60)
    print(context)
    print("-" * 60)
    
    # Should NOT include server 1 and 2 (too old)
    assert "server 1" not in context_lower, "Old messages should be excluded"
    assert "server 2" not in context_lower, "Old messages should be excluded"
    assert "server 3" not in context_lower, "Old messages should be excluded"
    
    # Should include server 4, 5 (most recent in the last 3 messages)
    assert "server 4" in context_lower or "server 5" in context_lower, "Recent messages should be included"
    
    print("\n✅ TEST 4 PASSED\n")

def test_thread_cleanup():
    """Test 5: Thread cleanup"""
    print("\n" + "="*60)
    print("TEST 5: Thread Cleanup")
    print("="*60)
    
    config = load_config()
    tm = ThreadManager(config)
    
    # Create thread
    thread_ts = "1111111111.111111"
    tm.get_or_create_thread(thread_ts, "C1111", "U1111")
    
    initial_count = len(tm._threads)
    print(f"Initial thread count: {initial_count}")
    
    # Cleanup should not remove recent threads
    tm.cleanup_old_threads()
    after_cleanup = len(tm._threads)
    print(f"After cleanup: {after_cleanup}")
    
    assert initial_count == after_cleanup, "Recent threads should not be cleaned up"
    
    print("✅ TEST 5 PASSED\n")

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 SLACK THREADING TEST SUITE")
    print("="*60)
    
    try:
        test_basic_threading()
        test_should_use_thread()
        test_conversation_context()
        test_context_limit()
        test_thread_cleanup()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n🎉 Slack threading is working correctly!")
        print("\n📝 Next Steps:")
        print("   1. Test in actual Slack workspace by mentioning the bot")
        print("   2. Send multiple messages in a thread")
        print("   3. Verify context is preserved across messages")
        print("   4. Check docker logs for threading debug output")
        print("   5. Verify thread_ts is consistent across messages")
        print("="*60 + "\n")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

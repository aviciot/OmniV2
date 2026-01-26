#!/usr/bin/env python
"""
Quick Test Script - Verify Microservices Architecture

Run this to quickly verify the architecture is working:
    docker exec omni2-bridge python /app/tests/quick_test.py
"""

import sys


def test_imports():
    """Test that imports work correctly"""
    print("🔍 Testing imports...")
    
    try:
        from app.services import auth_client
        print("  ✅ auth_client imported")
    except ImportError as e:
        print(f"  ❌ Failed to import auth_client: {e}")
        return False
    
    try:
        from app import models
        print("  ✅ models imported")
    except ImportError as e:
        print(f"  ❌ Failed to import models: {e}")
        return False
    
    return True


def test_user_model_removed():
    """Test that User model is NOT in omni2"""
    print("\n🔍 Testing User model removal...")
    
    from app import models
    
    if hasattr(models, 'User'):
        print("  ❌ User model still exists in omni2 (should be removed)")
        return False
    
    print("  ✅ User model correctly removed from omni2")
    return True


def test_omni2_models_exist():
    """Test that omni2-specific models exist"""
    print("\n🔍 Testing omni2 models...")
    
    from app import models
    
    required_models = [
        'AuditLog',
        'ChatSession',
        'UserTeam',
        'UserMCPPermission',
        'MCPServer',
        'MCPTool',
        'Omni2Config'
    ]
    
    for model_name in required_models:
        if not hasattr(models, model_name):
            print(f"  ❌ Missing model: {model_name}")
            return False
        print(f"  ✅ {model_name} exists")
    
    return True


def test_no_fk_constraints():
    """Test that user_id columns have no FK constraints"""
    print("\n🔍 Testing FK constraints removed...")
    
    from app.models import AuditLog, ChatSession
    
    # Check AuditLog
    user_id_col = AuditLog.__table__.columns.get('user_id')
    if user_id_col and len(list(user_id_col.foreign_keys)) > 0:
        print("  ❌ AuditLog.user_id still has FK constraint")
        return False
    print("  ✅ AuditLog.user_id has no FK constraint")
    
    # Check ChatSession
    user_id_col = ChatSession.__table__.columns.get('user_id')
    if user_id_col and len(list(user_id_col.foreign_keys)) > 0:
        print("  ❌ ChatSession.user_id still has FK constraint")
        return False
    print("  ✅ ChatSession.user_id has no FK constraint")
    
    return True


def test_auth_client_functions():
    """Test that auth_client has required functions"""
    print("\n🔍 Testing auth_client functions...")
    
    from app.services import auth_client
    
    required_functions = [
        'get_user',
        'get_user_by_email',
        'validate_token',
        'create_user',
        'update_user',
        'list_users'
    ]
    
    for func_name in required_functions:
        if not hasattr(auth_client, func_name):
            print(f"  ❌ Missing function: {func_name}")
            return False
        print(f"  ✅ {func_name} exists")
    
    return True


def main():
    """Run all tests"""
    print("="*80)
    print("🚀 MICROSERVICES ARCHITECTURE - QUICK TEST")
    print("="*80)
    
    tests = [
        ("Imports", test_imports),
        ("User Model Removed", test_user_model_removed),
        ("Omni2 Models Exist", test_omni2_models_exist),
        ("FK Constraints Removed", test_no_fk_constraints),
        ("Auth Client Functions", test_auth_client_functions)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("="*80)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Architecture is correct.")
        print("\n📚 Next Steps:")
        print("  1. Run full test suite: pytest /app/tests/test_auth_microservices.py")
        print("  2. Check omni2 logs: docker logs omni2-bridge --tail 50")
        print("  3. Test health endpoint: curl http://localhost:8000/health")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

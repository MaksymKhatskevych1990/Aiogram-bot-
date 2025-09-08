#!/usr/bin/env python3
"""
Test script to verify that all imports are working correctly
"""

import sys
import os

# Add the current directory to Python path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_imports():
    """Test that config variables can be imported correctly"""
    try:
        from config import TRC20_CONFIRMATIONS, ERC20_CONFIRMATIONS, TRONSCAN_API
        print(f"✅ Config imports successful:")
        print(f"   TRC20_CONFIRMATIONS: {TRC20_CONFIRMATIONS} (type: {type(TRC20_CONFIRMATIONS)})")
        print(f"   ERC20_CONFIRMATIONS: {ERC20_CONFIRMATIONS} (type: {type(ERC20_CONFIRMATIONS)})")
        print(f"   TRONSCAN_API: {TRONSCAN_API}")
        return True
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False

def test_network_imports():
    """Test that network modules can be imported correctly"""
    try:
        from networks.tron import check_tron_transaction
        print("✅ TRON module import successful")
    except ImportError as e:
        print(f"❌ TRON module import failed: {e}")
        return False
    
    try:
        from networks.ethereum import check_transaction_stages
        print("✅ Ethereum module import successful")
    except ImportError as e:
        print(f"❌ Ethereum module import failed: {e}")
        return False
    
    return True

def test_google_utils_imports():
    """Test that google_utils can be imported correctly"""
    try:
        from google_utils import verify_transaction
        print("✅ Google utils import successful")
        return True
    except ImportError as e:
        print(f"❌ Google utils import failed: {e}")
        return False

def test_type_comparisons():
    """Test that confirmation comparisons work correctly"""
    try:
        from config import TRC20_CONFIRMATIONS, ERC20_CONFIRMATIONS
        
        # Test integer comparisons
        test_confirmations = 81
        if test_confirmations < TRC20_CONFIRMATIONS:
            print(f"✓ TRC20 comparison works: {test_confirmations} < {TRC20_CONFIRMATIONS}")
        else:
            print(f"✓ TRC20 comparison works: {test_confirmations} >= {TRC20_CONFIRMATIONS}")
        
        if test_confirmations < ERC20_CONFIRMATIONS:
            print(f"✓ ERC20 comparison works: {test_confirmations} < {ERC20_CONFIRMATIONS}")
        else:
            print(f"✓ ERC20 comparison works: {test_confirmations} >= {ERC20_CONFIRMATIONS}")
            
        print("✅ All confirmation comparisons work correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Type comparison test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing imports and type compatibility...\n")
    
    tests = [
        ("Config imports", test_config_imports),
        ("Network module imports", test_network_imports),
        ("Google utils imports", test_google_utils_imports),
        ("Type comparisons", test_type_comparisons)
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        if not test_func():
            all_passed = False
        print()
    
    if all_passed:
        print("🎉 All tests passed! The fixes are working correctly.")
    else:
        print("💥 Some tests failed! There are still issues to resolve.")
        sys.exit(1) 
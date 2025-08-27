#!/usr/bin/env python3
"""
Test script to verify TRON confirmation comparison fix
"""

import sys
import os

# Add the current directory to Python path so we can import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TRC20_CONFIRMATIONS, ERC20_CONFIRMATIONS

def test_confirmation_types():
    """Test that confirmation constants are integers"""
    print(f"TRC20_CONFIRMATIONS type: {type(TRC20_CONFIRMATIONS)}, value: {TRC20_CONFIRMATIONS}")
    print(f"ERC20_CONFIRMATIONS type: {type(ERC20_CONFIRMATIONS)}, value: {ERC20_CONFIRMATIONS}")
    
    # Test that we can compare them with integers
    test_confirmations = 81
    try:
        if test_confirmations < TRC20_CONFIRMATIONS:
            print(f"✓ TRC20 comparison works: {test_confirmations} < {TRC20_CONFIRMATIONS}")
        else:
            print(f"✓ TRC20 comparison works: {test_confirmations} >= {TRC20_CONFIRMATIONS}")
        
        if test_confirmations < ERC20_CONFIRMATIONS:
            print(f"✓ ERC20 comparison works: {test_confirmations} < {ERC20_CONFIRMATIONS}")
        else:
            print(f"✓ ERC20 comparison works: {test_confirmations} >= {ERC20_CONFIRMATIONS}")
            
        print("✅ All confirmation comparisons work correctly!")
        
    except TypeError as e:
        print(f"❌ Type error in comparison: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing TRON confirmation fix...")
    success = test_confirmation_types()
    
    if success:
        print("\n🎉 Test passed! The fix is working correctly.")
    else:
        print("\n💥 Test failed! There's still an issue.")
        sys.exit(1) 
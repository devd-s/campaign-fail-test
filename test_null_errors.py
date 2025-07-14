#!/usr/bin/env python3
"""
Test script to demonstrate null pointer errors and their fixes
"""

import requests
import json
import sys

# Configuration
BASE_URL = "http://campaign-api-alb-492991282.eu-central-1.elb.amazonaws.com"

def test_broken_endpoint():
    """Test the broken analytics endpoint"""
    print("🧪 Testing Broken Analytics Endpoint")
    print("=" * 50)
    
    # Test with a campaign that likely exists (ID 1)
    endpoint = f"{BASE_URL}/campaigns/1/analytics"
    print(f"🔗 Testing: {endpoint}")
    
    try:
        response = requests.get(endpoint, timeout=10)
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 500:
            error_data = response.json()
            print("❌ Expected Error (Null Pointer Issues):")
            print(f"   Error Type: {error_data.get('detail', {}).get('error', 'Unknown')}")
            print(f"   Message: {error_data.get('detail', {}).get('message', 'No message')}")
            print(f"   Fix Needed: {error_data.get('detail', {}).get('fix_needed', 'Unknown')}")
            return True
        else:
            print(f"✅ Unexpected Success: {response.json()}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"🌐 Network Error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"📝 JSON Parse Error: {e}")
        return False

def test_fixed_endpoint():
    """Test the fixed analytics endpoint (after PR is applied)"""
    print("\n🧪 Testing Fixed Analytics Endpoint")
    print("=" * 50)
    
    endpoint = f"{BASE_URL}/campaigns/1/analytics"
    print(f"🔗 Testing: {endpoint}")
    
    try:
        response = requests.get(endpoint, timeout=10)
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success! Fixed Response:")
            print(f"   Campaign Name: {data.get('name', 'N/A')}")
            print(f"   Launch Date: {data.get('launch_date', 'N/A')}")
            print(f"   Description Length: {data.get('description_length', 'N/A')}")
            print(f"   Days Active: {data.get('days_active', 'N/A')}")
            print(f"   Fixes Applied: {len(data.get('fixes_applied', []))}")
            return True
        else:
            error_data = response.json()
            print(f"❌ Still has errors: {error_data}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"🌐 Network Error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"📝 JSON Parse Error: {e}")
        return False

def test_all_error_endpoints():
    """Test all error endpoints for comparison"""
    print("\n🧪 Testing All Error Endpoints")
    print("=" * 50)
    
    endpoints = [
        "/test-null-reference-error",
        "/test-table-not-found-error", 
        "/test-db-connection-error",
        "/campaigns/1/analytics"
    ]
    
    for endpoint in endpoints:
        url = f"{BASE_URL}{endpoint}"
        print(f"\n🔗 Testing: {endpoint}")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 500:
                error_data = response.json()
                error_type = error_data.get('error', 'Unknown')
                message = error_data.get('message', 'No message')
                print(f"   ❌ {error_type}: {message[:60]}...")
            else:
                print(f"   ✅ Status: {response.status_code}")
                
        except Exception as e:
            print(f"   🌐 Error: {str(e)[:60]}...")

def main():
    """Main test runner"""
    print("🤖 Null Pointer Error Testing Suite")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test-fixed':
        # Test the fixed version
        success = test_fixed_endpoint()
        if success:
            print("\n🎉 Fixed endpoint working correctly!")
        else:
            print("\n❌ Fixed endpoint still has issues")
    elif len(sys.argv) > 1 and sys.argv[1] == '--test-all':
        # Test all endpoints
        test_all_error_endpoints()
    else:
        # Test the broken version
        print("Testing broken endpoint to demonstrate null pointer errors...")
        success = test_broken_endpoint()
        if success:
            print("\n🎯 Demonstrated null pointer vulnerability!")
            print("\n📋 Next Steps:")
            print("1. Run: python fix_null_pointer_errors.py --create-pr")
            print("2. Review and merge the automated PR")
            print("3. Test fixed version: python test_null_errors.py --test-fixed")
        else:
            print("\n🤔 Endpoint might already be fixed or unavailable")
    
    print("\n📊 DataDog Monitoring:")
    print("- Check Logs → Search for 'AnalyticsError'")
    print("- Monitor error rates before/after fix")
    print("- Set up alerts for null pointer patterns")

if __name__ == "__main__":
    main()
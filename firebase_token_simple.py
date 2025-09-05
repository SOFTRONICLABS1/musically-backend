#!/usr/bin/env python3
"""
Simple Firebase ID token generator - hardcoded test user
"""
import requests
import json

def get_firebase_token():
    api_key = "AIzaSyCPAPOy37WNjDYQWfijKZNu8MGp3o5h714"
    
    # Test credentials (create this user in Firebase Console first)
    email = "test@example.com"
    password = "test123456"
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            id_token = data.get('idToken')
            
            print("✅ Firebase ID Token Generated:")
            print("=" * 50)
            print(id_token)
            print("=" * 50)
            
            print("\n📋 Test with curl:")
            print(f'curl -X POST "https://24pw8gqd0i.execute-api.us-east-1.amazonaws.com/api/v1/auth/sso" -H "Content-Type: application/json" -d \'{{"id_token": "{id_token}", "additional_details": {{"device": "test"}}}}\'')
            
            # Test immediately
            test_payload = {
                "id_token": id_token,
                "additional_details": {"device": "python_test"}
            }
            
            print("\n🧪 Testing API...")
            test_response = requests.post(
                "https://24pw8gqd0i.execute-api.us-east-1.amazonaws.com/api/v1/auth/sso",
                json=test_payload
            )
            
            print(f"Status: {test_response.status_code}")
            print("Response:", json.dumps(test_response.json(), indent=2))
            
        else:
            print("❌ Authentication failed:")
            print(json.dumps(response.json(), indent=2))
            print("\n💡 Create user 'test@example.com' with password 'test123456' in Firebase Console")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    get_firebase_token()
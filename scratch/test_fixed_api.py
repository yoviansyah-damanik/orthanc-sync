import requests
import json

# Testing the actual Django API endpoint
url = 'http://localhost:9123/api/check-study/US20260214000001'

try:
    # We need to be logged in to access this API, but maybe it's accessible during development or we can use a session
    # Actually, the middleware might block it or redirect to login.
    # Let's try to query it directly if possible.
    r = requests.get(url)
    print(f"API Response Status: {r.status_code}")
    print(f"API Response Body: {r.text}")
except Exception as e:
    print(f"Error: {e}")

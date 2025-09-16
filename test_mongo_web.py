import time
time.sleep(2)
import requests

try:
    r = requests.get('http://127.0.0.1:5000/test_mongodb', timeout=5)
    print('✅ MongoDB Endpoint Test')
    print('=' * 25)
    print(f'Status Code: {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        print(f'Status: {data["status"]}')
        print(f'Message: {data["message"][:100]}...')
        print('🎉 SUCCESS: MongoDB web endpoint is working!')
    else:
        print(f'❌ Error Response: {r.text}')
except Exception as e:
    print(f'❌ Test failed: {e}')

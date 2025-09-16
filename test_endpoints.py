import requests

print('🌐 Testing YouTube Scraping App Endpoints')
print('=' * 45)

# Test endpoints
endpoints = [
    ('http://127.0.0.1:5000/', 'Home Page'),
    ('http://127.0.0.1:5000/test_mongodb', 'MongoDB Connection Test'),
    ('http://127.0.0.1:5000/mongodb_stats', 'MongoDB Statistics')
]

for url, name in endpoints:
    try:
        print(f'\\n🔍 Testing {name}...')
        print(f'   URL: {url}')

        r = requests.get(url, timeout=10)
        print(f'   Status: {r.status_code}')

        if r.status_code == 200:
            if 'mongodb' in url:
                try:
                    data = r.json()
                    status = data.get("status", "Unknown")
                    print(f'   Response: {status}')
                    if 'message' in data:
                        message = data["message"][:80]
                        print(f'   Message: {message}...')
                    if 'database' in data:
                        print(f'   Database: {data["database"]}')
                    if 'collections' in data:
                        print(f'   Collections: {len(data["collections"])}')
                except:
                    response_text = r.text[:100]
                    print(f'   Response: {response_text}...')
            else:
                print(f'   ✅ Page loaded successfully')
        else:
            print(f'   ❌ Error: {r.status_code}')
            if r.status_code == 500:
                print(f'   Error details: {r.text[:200]}...')

    except requests.exceptions.ConnectionError:
        print(f'   ❌ Connection failed - Flask app may not be running')
    except Exception as e:
        print(f'   ❌ Error: {str(e)}')

print('\\n📋 Available Endpoints:')
print('   🏠 http://127.0.0.1:5000/ - Main application')
print('   🧪 http://127.0.0.1:5000/test_mongodb - Test MongoDB connection')
print('   📊 http://127.0.0.1:5000/mongodb_stats - View database statistics')
print('   🔍 POST http://127.0.0.1:5000/search - Perform search (requires JSON data)')

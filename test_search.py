import requests
import json

# Test the unified search
try:
    response = requests.post('http://127.0.0.1:5000/search',
                           json={'query': 'iPhone 15'},
                           timeout=30)
    if response.status_code == 200:
        result = response.json()
        print('SUCCESS: Search completed')
        print(f'Query: {result.get("search_query")}')
        print(f'Saved to: {result.get("saved_to")}')
        print(f'Sources: {result.get("sources")}')
        print(f'Total comments: {result.get("total_comments")}')
        print(f'Unique comments: {result.get("unique_comments")}')
    else:
        print(f'ERROR: {response.status_code} - {response.text}')
except requests.exceptions.ConnectionError:
    print('ERROR: Flask app not running - please start it first')
except Exception as e:
    print(f'ERROR: {e}')

#!/usr/bin/env python3
"""
Test script to demonstrate the new filename generation with query inclusion
"""

from app import YouTubeCommentFetcher
import os

def test_filename_generation():
    """Test the filename generation with various queries"""
    fetcher = YouTubeCommentFetcher()

    # Test different queries
    test_queries = [
        'Tesla Model 3 review',
        'Why buy electric cars?',
        'Best smartphones 2025',
        'AI technology trends',
        'Space exploration news',
        'Machine Learning basics',
        'Electric vehicle charging',
        'Sustainable energy solutions'
    ]

    print('=== FILENAME GENERATION TEST ===')
    print('Shows how queries are sanitized and included in filenames')
    print()

    for query in test_queries:
        sanitized = fetcher.sanitize_query_for_filename(query)
        print(f'📝 Original Query: "{query}"')
        print(f'🔧 Sanitized: "{sanitized}"')
        print(f'📄 Cleaned file: cleaned_unique_comments_{sanitized}_20250904_120000_abc123.json')
        print(f'📦 Batch file: batch_{sanitized}_20250904_120000_abc123.json')
        print('-' * 80)
        print()

if __name__ == "__main__":
    test_filename_generation()

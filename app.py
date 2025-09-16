from flask import Flask, render_template, request, jsonify
import os
import json
import uuid
import random
import string
from datetime import datetime
from googleapiclient.discovery import build
from dotenv import load_dotenv
import praw
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyDbWs2fojEoXcvehGd-OddoLfCPlUVYTmM"
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'youtube_scraper')

# Global MongoDB client
mongo_client = None
db = None

def get_mongo_client():
    """Get or create MongoDB client connection"""
    global mongo_client, db

    if mongo_client is None:
        try:
            print("🔌 Connecting to MongoDB...")
            print(f"📍 URI: {MONGODB_URI[:30]}..." if MONGODB_URI else "No URI configured")
            print(f"📊 Database: {MONGODB_DATABASE}")

            if not MONGODB_URI:
                print("❌ MongoDB URI not configured in environment variables")
                return None, None

            mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Test the connection
            mongo_client.admin.command('ping')
            db = mongo_client[MONGODB_DATABASE]
            print(f"✅ Connected to MongoDB database: {MONGODB_DATABASE}")
        except ConnectionFailure as e:
            print(f"❌ MongoDB connection failed: {e}")
            print("💡 This might be due to network issues or incorrect credentials")
            mongo_client = None
            db = None
        except ServerSelectionTimeoutError as e:
            print(f"❌ MongoDB server timeout: {e}")
            print("💡 Check your internet connection and MongoDB Atlas IP whitelist")
            mongo_client = None
            db = None
        except Exception as e:
            error_msg = str(e)
            if "authentication failed" in error_msg.lower():
                print("❌ MongoDB authentication failed!")
                print("💡 Please check:")
                print("   1. Username and password in MONGODB_URI")
                print("   2. User exists in MongoDB Atlas")
                print("   3. User has read/write permissions")
                print("   4. IP address is whitelisted in MongoDB Atlas")
            else:
                print(f"❌ Unexpected MongoDB error: {e}")
            mongo_client = None
            db = None

    return mongo_client, db

def generate_query_variations(original_query, num_variations=20):
    """Generate multiple variations of a query using Gemini AI"""
    try:
        print(f"🤖 Generating {num_variations} query variations using Gemini AI...")

        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""
        Generate {num_variations} different variations of this search query: "{original_query}"

        Requirements:
        - Each variation should have different wording and style
        - Keep the core meaning the same but vary the phrasing
        - Make them suitable for YouTube and Reddit search
        - Include different perspectives, synonyms, and rephrasings
        - Some should be more formal, some more casual
        - Some should be questions, some statements
        - Return only the variations as a numbered list, one per line
        - Do not include any explanations or additional text

        Example format:
        1. First variation here
        2. Second variation here
        ...
        """

        response = model.generate_content(prompt)
        variations_text = response.text.strip()

        # Parse the variations from the response
        variations = []
        for line in variations_text.split('\n'):
            line = line.strip()
            if line and any(char.isdigit() for char in line[:3]):  # Check if line starts with number
                # Remove numbering (e.g., "1. ", "2. ", etc.)
                variation = line.split('.', 1)[-1].strip()
                if variation:
                    variations.append(variation)

        # Ensure we have at least some variations
        if not variations:
            print("❌ No variations generated, using original query")
            return [original_query]

        # Limit to requested number
        variations = variations[:num_variations]

        print(f"✅ Generated {len(variations)} query variations:")
        for i, var in enumerate(variations[:5], 1):  # Show first 5
            print(f"   {i}. {var}")
        if len(variations) > 5:
            print(f"   ... and {len(variations) - 5} more")

        return variations

    except Exception as e:
        print(f"❌ Error generating query variations: {e}")
        print("💡 Falling back to original query")
        return [original_query]

def test_mongodb_connection():
    """Test MongoDB connection manually"""
    try:
        client, database = get_mongo_client()
        if client is not None and database is not None:
            # Test database operations
            collections = database.list_collection_names()
            print(f"📊 Available collections: {collections}")

            # Test a simple operation
            test_doc = {"test": "connection", "timestamp": datetime.now().isoformat()}
            result = database.test_collection.insert_one(test_doc)
            print(f"✅ Test document inserted with ID: {result.inserted_id}")

            # Clean up test document
            database.test_collection.delete_one({"_id": result.inserted_id})
            print("🧹 Test document cleaned up")

            return True, f"Connected to {MONGODB_DATABASE}. Collections: {collections}"
        else:
            return False, "Failed to connect to MongoDB. Check your connection string and Atlas settings."
    except Exception as e:
        error_details = str(e)
        if "authentication failed" in error_details:
            return False, ("Authentication failed. Please check:\n"
                          "1. Username/password in MONGODB_URI\n"
                          "2. User exists in MongoDB Atlas dashboard\n"
                          "3. User has database access permissions\n"
                          "4. Your IP is whitelisted in Network Access")
        elif "connection" in error_details.lower():
            return False, "Connection failed. Check your internet connection and MongoDB Atlas cluster status."
        else:
            return False, f"MongoDB test failed: {error_details}"

class YouTubeCommentFetcher:
    def __init__(self):
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("Please set YOUTUBE_API_KEY in .env file")

        self.youtube = build('youtube', 'v3', developerKey=self.api_key)

    def sanitize_query_for_filename(self, query):
        """Sanitize query string to be safe for filenames"""
        # Replace spaces with underscores
        sanitized = query.replace(' ', '_')
        # Remove or replace special characters that are problematic in filenames
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        # Limit length to avoid overly long filenames
        if len(sanitized) > 30:
            sanitized = sanitized[:30]
        # Remove trailing underscores
        sanitized = sanitized.rstrip('_')
        return sanitized.lower()

    def search_videos(self, query, max_results=10):
        """Search for multiple videos based on query"""
        try:
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                order='relevance'
            ).execute()

            videos = []
            for item in search_response['items']:
                video_data = {
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'channel': item['snippet']['channelTitle'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails']['high']['url'] if 'high' in item['snippet']['thumbnails'] else item['snippet']['thumbnails']['default']['url']
                }
                videos.append(video_data)

            return videos

        except Exception as e:
            print(f"Error searching videos: {e}")
            return []

    def get_comments(self, video_id, max_comments=100):
        """Fetch comments and replies from a video"""
        try:
            comments = []
            next_page_token = None

            while len(comments) < max_comments:
                request = self.youtube.commentThreads().list(
                    part='snippet,replies',
                    videoId=video_id,
                    maxResults=min(100, max_comments - len(comments)),
                    order='relevance',
                    pageToken=next_page_token
                )

                response = request.execute()

                for item in response['items']:
                    comment = item['snippet']['topLevelComment']['snippet']
                    comment_data = {
                        'author': comment['authorDisplayName'],
                        'text': comment['textDisplay'],
                        'likes': comment['likeCount'],
                        'published_at': comment['publishedAt'],
                        'author_profile': comment.get('authorProfileImageUrl', ''),
                        'replies': []
                    }

                    # Fetch replies if any
                    if item['snippet']['totalReplyCount'] > 0 and 'replies' in item:
                        for reply_item in item['replies']['comments']:
                            reply = reply_item['snippet']
                            reply_data = {
                                'author': reply['authorDisplayName'],
                                'text': reply['textDisplay'],
                                'likes': reply['likeCount'],
                                'published_at': reply['publishedAt'],
                                'author_profile': reply.get('authorProfileImageUrl', '')
                            }
                            comment_data['replies'].append(reply_data)

                    comments.append(comment_data)

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

            return comments

        except Exception as e:
            print(f"Error fetching comments: {e}")
            return []

    def get_unique_comments(self, videos_data):
        """Extract unique comments and replies from videos data"""
        unique_comments = {}
        total_comments = 0
        total_replies = 0

        for video in videos_data:
            for comment in video['comments']:
                comment_text = comment['text'].strip()
                if comment_text not in unique_comments:
                    unique_comments[comment_text] = {
                        'author': comment['author'],
                        'text': comment_text,
                        'likes': comment['likes'],
                        'published_at': comment['published_at'],
                        'author_profile': comment['author_profile'],
                        'video_title': video['video_info']['title'],
                        'replies': []
                    }
                    total_comments += 1

                # Add replies
                existing_replies = [r['text'] for r in unique_comments[comment_text]['replies']]
                for reply in comment['replies']:
                    reply_text = reply['text'].strip()
                    if reply_text not in existing_replies:
                        unique_comments[comment_text]['replies'].append({
                            'author': reply['author'],
                            'text': reply_text,
                            'likes': reply['likes'],
                            'published_at': reply['published_at'],
                            'author_profile': reply['author_profile']
                        })
                        total_replies += 1

        return list(unique_comments.values()), total_comments, total_replies

    def save_cleaned_data(self, query, unique_comments, total_comments, total_replies):
        """Save cleaned unique comments to JSON file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            batch_id = str(uuid.uuid4())[:8]
            sanitized_query = self.sanitize_query_for_filename(query)

            cleaned_data = {
                'batch_id': batch_id,
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'total_unique_comments': total_comments,
                'total_replies': total_replies,
                'unique_comments': unique_comments
            }

            filename = f"data/cleaned_unique_comments_{sanitized_query}_{timestamp}_{batch_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

            return filename

        except Exception as e:
            print(f"Error saving cleaned data: {e}")
            return None

    def save_combined_data(self, query, videos_data, unique_comments, unique_count, total_replies, total_comments):
        """Save combined batch and cleaned data in a single comprehensive file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)

            # Generate unique ID for this batch
            batch_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            sanitized_query = self.sanitize_query_for_filename(query)

            # Create comprehensive data structure
            combined_data = {
                'batch_id': batch_id,
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'total_videos': len(videos_data),
                'total_comments': total_comments,
                'unique_comments': unique_count,
                'total_replies': total_replies,
                'videos': videos_data,
                'unique_comments_data': unique_comments,
                'processing_info': {
                    'processed_at': datetime.now().isoformat(),
                    'duplicates_removed': total_comments - unique_count,
                    'comments_per_video_avg': total_comments / len(videos_data) if videos_data else 0
                }
            }

            filename = f"data/{sanitized_query}_complete_{timestamp}_{batch_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)

            return filename, combined_data

        except Exception as e:
            print(f"Error saving combined data: {e}")
            return None, None

class RedditCommentFetcher:
    def __init__(self):
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT')

        if not all([self.client_id, self.client_secret, self.user_agent]):
            raise ValueError("Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT in .env file")

        self.reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent
        )

    def search_subreddits(self, query, limit=10):
        """Search for relevant subreddits based on query"""
        try:
            # Common subreddits that might be relevant for various topics
            relevant_subreddits = [
                'all', 'AskReddit', 'todayilearned', 'news', 'worldnews',
                'technology', 'science', 'politics', 'gaming', 'movies',
                'music', 'books', 'sports', 'food', 'travel', 'history'
            ]

            # Filter subreddits that might be relevant to the query
            query_lower = query.lower()
            filtered_subreddits = []

            for subreddit_name in relevant_subreddits:
                try:
                    subreddit = self.reddit.subreddit(subreddit_name)
                    # Check if subreddit exists and is accessible
                    subreddit.display_name
                    filtered_subreddits.append(subreddit_name)
                except:
                    continue

            return filtered_subreddits[:limit]

        except Exception as e:
            print(f"Error searching subreddits: {e}")
            return ['all', 'AskReddit']  # fallback

    def get_comments_from_subreddit(self, subreddit_name, query, limit=500):
        """Fetch comments from a specific subreddit"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            comments_data = []

            # Search for posts related to the query
            search_results = subreddit.search(query, limit=min(limit // 10, 50), sort='relevance', time_filter='all')

            # Prepare query terms for relevance filtering
            query_terms = set(query.lower().split())
            if len(query_terms) == 1 and len(list(query_terms)[0]) > 3:
                # For single word queries, also check for partial matches
                query_terms.add(list(query_terms)[0][:4])  # First 4 characters

            print(f"DEBUG: Filtering Reddit comments in r/{subreddit_name} for query terms: {query_terms}")

            total_comments_processed = 0
            relevant_comments_found = 0

            for post in search_results:
                try:
                    # Get comments from this post
                    post.comments.replace_more(limit=0)  # Remove "load more comments" objects

                    for comment in post.comments.list():
                        if len(comments_data) >= limit:
                            break

                        total_comments_processed += 1
                        comment_text = comment.body.lower()

                        # Filter for relevance: comment must contain at least one query term
                        is_relevant = any(term in comment_text for term in query_terms)

                        # Additional check: if query has multiple words, check if comment contains most of them
                        if len(query_terms) > 1:
                            matching_terms = sum(1 for term in query_terms if term in comment_text)
                            is_relevant = matching_terms >= max(1, len(query_terms) // 2)  # At least half the terms

                        if not is_relevant:
                            continue  # Skip irrelevant comments

                        relevant_comments_found += 1

                        comment_data = {
                            'author': str(comment.author) if comment.author else 'Anonymous',
                            'text': comment.body,
                            'likes': comment.score,
                            'published_at': datetime.fromtimestamp(comment.created_utc).isoformat(),
                            'author_profile': '',
                            'post_title': post.title,
                            'subreddit': subreddit_name,
                            'replies': []
                        }

                        # Get replies and filter them for relevance too
                        if hasattr(comment, 'replies') and comment.replies:
                            for reply in comment.replies.list():
                                if len(comment_data['replies']) >= 5:  # Limit replies per comment
                                    break

                                reply_text = reply.body.lower()
                                reply_relevant = any(term in reply_text for term in query_terms)

                                if len(query_terms) > 1:
                                    reply_matching = sum(1 for term in query_terms if term in reply_text)
                                    reply_relevant = reply_matching >= max(1, len(query_terms) // 2)

                                if reply_relevant:
                                    reply_data = {
                                        'author': str(reply.author) if reply.author else 'Anonymous',
                                        'text': reply.body,
                                        'likes': reply.score,
                                        'published_at': datetime.fromtimestamp(reply.created_utc).isoformat(),
                                        'author_profile': ''
                                    }
                                    comment_data['replies'].append(reply_data)

                        comments_data.append(comment_data)

                    if len(comments_data) >= limit:
                        break

                except Exception as e:
                    print(f"Error processing post in r/{subreddit_name}: {e}")
                    continue

            print(f"DEBUG: Reddit r/{subreddit_name} - Processed {total_comments_processed} comments, found {relevant_comments_found} relevant comments")

            return comments_data

        except Exception as e:
            print(f"Error fetching comments from r/{subreddit_name}: {e}")
            return []

    def get_comments_parallel(self, query, total_limit=2500):
        """Fetch comments from multiple subreddits in parallel"""
        try:
            subreddits = self.search_subreddits(query, limit=8)
            print(f"Searching in subreddits: {subreddits}")

            all_comments = []
            comments_per_subreddit = max(100, total_limit // len(subreddits))

            def fetch_from_subreddit(subreddit_name):
                return self.get_comments_from_subreddit(subreddit_name, query, comments_per_subreddit)

            with ThreadPoolExecutor(max_workers=min(len(subreddits), 4)) as executor:
                future_to_subreddit = {
                    executor.submit(fetch_from_subreddit, subreddit): subreddit
                    for subreddit in subreddits
                }

                for future in as_completed(future_to_subreddit):
                    subreddit = future_to_subreddit[future]
                    try:
                        comments = future.result()
                        all_comments.extend(comments)
                        print(f"Got {len(comments)} comments from r/{subreddit}")
                    except Exception as e:
                        print(f"Error fetching from r/{subreddit}: {e}")

            return all_comments

        except Exception as e:
            print(f"Error in parallel comment fetching: {e}")
            return []

class UnifiedCommentFetcher:
    def __init__(self):
        self.youtube_fetcher = YouTubeCommentFetcher()
        self.reddit_fetcher = RedditCommentFetcher()

    def sanitize_query_for_filename(self, query):
        """Sanitize query string to be safe for filenames"""
        if not query or not query.strip():
            return "unknown_query"

        # Replace spaces with underscores
        sanitized = query.strip().replace(' ', '_')
        # Remove or replace special characters that are problematic in filenames
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        # Remove multiple consecutive underscores
        while '__' in sanitized:
            sanitized = sanitized.replace('__', '_')
        # Limit length to avoid overly long filenames
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        # Remove trailing underscores
        sanitized = sanitized.rstrip('_')
        # Ensure we have at least some content
        if not sanitized:
            sanitized = "query"
        return sanitized.lower()

    def fetch_all_comments_parallel(self, query, min_total_comments=50000, max_retries=3):
        """Fetch comments from both YouTube and Reddit in parallel with retry logic"""
        print(f"=== FETCHING COMMENTS FOR: '{query}' ===")
        print(f"Target: Minimum {min_total_comments} total comments (comments + replies)")

        all_videos = []
        total_comments = 0
        total_replies = 0
        attempt = 1
        sources_used = []

        while total_comments + total_replies < min_total_comments and attempt <= max_retries:
            print(f"\n--- ATTEMPT {attempt}/{max_retries} ---")

            results = {}
            errors = {}

            def fetch_youtube(max_videos=20, comments_per_video=150):
                try:
                    print("🔍 Starting YouTube search...")
                    # Increase video count and comments per video on retries
                    video_count = max_videos + (attempt - 1) * 10
                    comments_per_video = comments_per_video + (attempt - 1) * 30

                    videos = self.youtube_fetcher.search_videos(query, max_results=video_count)

                    if not videos:
                        return {'error': 'No YouTube videos found'}

                    print(f"📺 Found {len(videos)} YouTube videos")

                    videos_with_comments = []
                    total_yt_comments = 0

                    for i, video in enumerate(videos):
                        try:
                            comments = self.youtube_fetcher.get_comments(video['video_id'], max_comments=comments_per_video)
                            video_data = {
                                'video_info': video,
                                'comments': comments,
                                'comment_count': len(comments),
                                'source': 'youtube'
                            }
                            videos_with_comments.append(video_data)
                            total_yt_comments += len(comments)
                            print(f"  📹 Video {i+1}: {len(comments)} comments")
                        except Exception as e:
                            print(f"  ❌ Error with video {i+1}: {e}")

                    return {
                        'source': 'youtube',
                        'videos': videos_with_comments,
                        'total_comments': total_yt_comments
                    }

                except Exception as e:
                    print(f"❌ YouTube fetch error: {e}")
                    return {'error': str(e)}

            def fetch_reddit(comments_limit=3000):
                try:
                    print("🔍 Starting Reddit search...")
                    # Increase comment limit on retries
                    reddit_limit = comments_limit + (attempt - 1) * 1000

                    reddit_comments = self.reddit_fetcher.get_comments_parallel(query, reddit_limit)

                    # Convert Reddit comments to unified format
                    reddit_posts = []
                    for comment in reddit_comments:
                        reddit_posts.append({
                            'post_info': {
                                'title': comment['post_title'],
                                'subreddit': comment['subreddit'],
                                'source': 'reddit'
                            },
                            'comments': [comment],
                            'comment_count': 1,
                            'source': 'reddit'
                        })

                    print(f"🟠 Got {len(reddit_comments)} Reddit comments")

                    return {
                        'source': 'reddit',
                        'videos': reddit_posts,
                        'total_comments': len(reddit_comments)
                    }

                except Exception as e:
                    print(f"❌ Reddit fetch error: {e}")
                    return {'error': str(e)}

            # Run both fetches in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_yt = executor.submit(fetch_youtube)
                future_reddit = executor.submit(fetch_reddit)

                # Get results
                try:
                    yt_result = future_yt.result(timeout=180)
                    if 'error' not in yt_result:
                        results['youtube'] = yt_result
                        sources_used.append('youtube')
                    else:
                        errors['youtube'] = yt_result['error']
                except Exception as e:
                    errors['youtube'] = str(e)

                try:
                    reddit_result = future_reddit.result(timeout=180)
                    if 'error' not in reddit_result:
                        results['reddit'] = reddit_result
                        sources_used.append('reddit')
                    else:
                        errors['reddit'] = reddit_result['error']
                except Exception as e:
                    errors['reddit'] = str(e)

            # Add new results to accumulated data
            attempt_videos = []
            attempt_comments = 0
            attempt_replies = 0

            if 'youtube' in results:
                attempt_videos.extend(results['youtube']['videos'])
                attempt_comments += results['youtube']['total_comments']

            if 'reddit' in results:
                attempt_videos.extend(results['reddit']['videos'])
                attempt_comments += results['reddit']['total_comments']

            # Calculate replies in this attempt
            for video in attempt_videos:
                for comment in video['comments']:
                    attempt_replies += len(comment.get('replies', []))

            # Add to totals
            all_videos.extend(attempt_videos)
            total_comments += attempt_comments
            total_replies += attempt_replies

            current_total = total_comments + total_replies
            print(f"📊 Attempt {attempt} results:")
            print(f"   Comments collected: {attempt_comments}")
            print(f"   Replies collected: {attempt_replies}")
            print(f"   Total so far: {current_total}")
            print(f"   Target: {min_total_comments}")

            # Check if we've reached the target
            if current_total >= min_total_comments:
                print(f"✅ Target reached! Total: {current_total}")
                break
            elif attempt < max_retries:
                print(f"⚠️  Target not reached. Starting attempt {attempt + 1}...")
                time.sleep(3)  # Brief pause between attempts
            else:
                print(f"❌ Maximum retries reached. Final total: {current_total}")

            attempt += 1

        print(f"\n🎯 FINAL RESULTS:")
        print(f"   Total comments: {total_comments}")
        print(f"   Total replies: {total_replies}")
        print(f"   Grand total: {total_comments + total_replies}")
        print(f"   Sources used: {sources_used}")
        print(f"   Attempts made: {attempt - 1}")

        return {
            'videos': all_videos,
            'total_comments': total_comments,
            'total_replies': total_replies,
            'grand_total': total_comments + total_replies,
            'sources': sources_used,
            'errors': errors,
            'target_achieved': (total_comments + total_replies) >= min_total_comments,
            'attempts_made': attempt - 1
        }

    def fetch_multiple_queries_aggregated(self, queries, target_total_comments=50000):
        """Fetch comments for multiple queries and aggregate unique results"""
        print(f"🚀 STARTING MULTI-QUERY AGGREGATION")
        print(f"📋 Total queries to process: {len(queries)}")
        print(f"🎯 Target unique comments: {target_total_comments}")

        all_unique_comments = {}
        all_videos_data = []
        total_processed_comments = 0
        total_processed_replies = 0
        successful_queries = 0
        failed_queries = 0
        query_results = []

        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"🔄 PROCESSING QUERY {i}/{len(queries)}")
            print(f"📝 Query: '{query}'")
            print(f"{'='*60}")

            try:
                # Fetch comments for this specific query
                query_result = self.fetch_all_comments_parallel(
                    query=query,
                    min_total_comments=max(5000, target_total_comments // len(queries)),  # Distribute target
                    max_retries=2  # Reduce retries per query to speed up
                )

                if query_result['videos']:
                    # Extract unique comments from this query
                    query_unique, query_unique_count, query_replies = self.get_unique_comments_unified(query_result['videos'])

                    # Add to global unique comments (avoiding duplicates)
                    new_unique_count = 0
                    for comment in query_unique:
                        comment_text = comment['text'].strip()
                        if comment_text not in all_unique_comments:
                            all_unique_comments[comment_text] = comment
                            new_unique_count += 1

                    # Add video data
                    all_videos_data.extend(query_result['videos'])

                    # Update totals
                    total_processed_comments += query_result['total_comments']
                    total_processed_replies += query_result['total_replies']

                    query_results.append({
                        'query': query,
                        'status': 'success',
                        'total_comments': query_result['total_comments'],
                        'total_replies': query_result['total_replies'],
                        'unique_comments': query_unique_count,
                        'new_unique_comments': new_unique_count,
                        'sources': query_result['sources'],
                        'attempts': query_result['attempts_made']
                    })

                    successful_queries += 1
                    current_unique_total = len(all_unique_comments)

                    print(f"✅ Query {i} completed successfully!")
                    print(f"   📊 Comments: {query_result['total_comments']}, Replies: {query_result['total_replies']}")
                    print(f"   🎯 Unique from this query: {query_unique_count}")
                    print(f"   🆕 New unique added: {new_unique_count}")
                    print(f"   📈 Global unique total: {current_unique_total}")

                    # Check if we've reached the target
                    if current_unique_total >= target_total_comments:
                        print(f"🎉 TARGET REACHED! {current_unique_total} unique comments collected")
                        break

                else:
                    print(f"❌ Query {i} failed - no data collected")
                    failed_queries += 1
                    query_results.append({
                        'query': query,
                        'status': 'failed',
                        'error': 'No data collected'
                    })

            except Exception as e:
                print(f"❌ Query {i} crashed: {e}")
                failed_queries += 1
                query_results.append({
                    'query': query,
                    'status': 'error',
                    'error': str(e)
                })

            # Brief pause between queries to avoid rate limits
            if i < len(queries):
                print(f"⏳ Pausing 2 seconds before next query...")
                time.sleep(2)

        # Final results
        final_unique_comments = list(all_unique_comments.values())
        final_unique_count = len(final_unique_comments)

        print(f"\n{'='*60}")
        print(f"🎯 MULTI-QUERY AGGREGATION COMPLETE")
        print(f"{'='*60}")
        print(f"📊 Summary:")
        print(f"   🔢 Total queries processed: {len(queries)}")
        print(f"   ✅ Successful queries: {successful_queries}")
        print(f"   ❌ Failed queries: {failed_queries}")
        print(f"   💬 Total comments processed: {total_processed_comments}")
        print(f"   🔄 Total replies processed: {total_processed_replies}")
        print(f"   🎯 Final unique comments: {final_unique_count}")
        print(f"   📈 Target achieved: {'✅ YES' if final_unique_count >= target_total_comments else '❌ NO'}")

        return {
            'videos': all_videos_data,
            'unique_comments': final_unique_comments,
            'unique_count': final_unique_count,
            'total_processed_comments': total_processed_comments,
            'total_processed_replies': total_processed_replies,
            'grand_total': total_processed_comments + total_processed_replies,
            'successful_queries': successful_queries,
            'failed_queries': failed_queries,
            'query_results': query_results,
            'target_achieved': final_unique_count >= target_total_comments,
            'original_queries': queries
        }

    def get_unique_comments_unified(self, videos_data):
        """Extract unique comments from both YouTube and Reddit data"""
        unique_comments = {}
        total_comments = 0
        total_replies = 0

        for video in videos_data:
            source = video.get('source', 'unknown')

            for comment in video['comments']:
                comment_text = comment['text'].strip()

                # Skip empty comments
                if not comment_text or len(comment_text) < 3:
                    continue

                if comment_text not in unique_comments:
                    unique_comments[comment_text] = {
                        'author': comment['author'],
                        'text': comment_text,
                        'likes': comment.get('likes', 0),
                        'published_at': comment['published_at'],
                        'author_profile': comment.get('author_profile', ''),
                        'source': source,
                        'video_title': video.get('video_info', {}).get('title', video.get('post_info', {}).get('title', 'Unknown')),
                        'subreddit': video.get('post_info', {}).get('subreddit', ''),
                        'replies': []
                    }
                    total_comments += 1

                # Add replies
                existing_replies = [r['text'] for r in unique_comments[comment_text]['replies']]
                for reply in comment.get('replies', []):
                    reply_text = reply['text'].strip()
                    if reply_text and reply_text not in existing_replies and len(reply_text) > 3:
                        unique_comments[comment_text]['replies'].append({
                            'author': reply['author'],
                            'text': reply_text,
                            'likes': reply.get('likes', 0),
                            'published_at': reply['published_at'],
                            'author_profile': reply.get('author_profile', ''),
                            'source': source
                        })
                        total_replies += 1

        return list(unique_comments.values()), total_comments, total_replies

    def save_unified_data(self, query, videos_data, unique_comments, unique_count, total_replies, total_comments, sources):
        """Save unified data from both YouTube and Reddit to MongoDB only"""
        try:
            # Get MongoDB connection
            client, db = get_mongo_client()
            if client is None or db is None:
                print("❌ MongoDB connection failed - no data saved")
                return None, None

            batch_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            sanitized_query = self.sanitize_query_for_filename(query)

            print(f"DEBUG: Original query: '{query}'")
            print(f"DEBUG: Sanitized query: '{sanitized_query}'")
            print(f"DEBUG: Batch ID: {batch_id}")
            print(f"DEBUG: Timestamp: {timestamp}")

            # Separate YouTube and Reddit data
            youtube_videos = [v for v in videos_data if v.get('source') == 'youtube']
            reddit_posts = [v for v in videos_data if v.get('source') == 'reddit']

            combined_data = {
                'batch_id': batch_id,
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'sources': sources,
                'total_youtube_videos': len(youtube_videos),
                'total_reddit_posts': len(reddit_posts),
                'total_comments': total_comments,
                'total_replies': total_replies,
                'grand_total': total_comments + total_replies,
                'unique_comments': unique_count,
                'youtube_data': youtube_videos,
                'reddit_data': reddit_posts,
                'unique_comments_data': unique_comments,
                'processing_info': {
                    'processed_at': datetime.now().isoformat(),
                    'duplicates_removed': total_comments - unique_count,
                    'youtube_comments': sum(len(v['comments']) for v in youtube_videos),
                    'reddit_comments': sum(len(v['comments']) for v in reddit_posts),
                    'comments_per_source_avg': {
                        'youtube': sum(len(v['comments']) for v in youtube_videos) / len(youtube_videos) if youtube_videos else 0,
                        'reddit': sum(len(v['comments']) for v in reddit_posts) / len(reddit_posts) if reddit_posts else 0
                    }
                }
            }

            # Create summary data for MongoDB (to avoid size limits)
            summary_data = {
                'batch_id': batch_id,
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'sources': sources,
                'total_youtube_videos': len(youtube_videos),
                'total_reddit_posts': len(reddit_posts),
                'total_comments': total_comments,
                'total_replies': total_replies,
                'grand_total': total_comments + total_replies,
                'unique_comments': unique_count,
                'processing_info': {
                    'processed_at': datetime.now().isoformat(),
                    'duplicates_removed': total_comments - unique_count,
                    'youtube_comments': sum(len(v['comments']) for v in youtube_videos),
                    'reddit_comments': sum(len(v['comments']) for v in reddit_posts),
                    'comments_per_source_avg': {
                        'youtube': sum(len(v['comments']) for v in youtube_videos) / len(youtube_videos) if youtube_videos else 0,
                        'reddit': sum(len(v['comments']) for v in reddit_posts) / len(reddit_posts) if reddit_posts else 0
                    }
                },
                'data_storage': {
                    'full_data_saved_to_files': True,
                    'history_file': f"history/unique_comments_{sanitized_query}_{timestamp}_{batch_id}.json",
                    'videos_file': f"data/{sanitized_query}_videos_{timestamp}_{batch_id}.json"
                }
            }

            # Try to save summary to MongoDB
            mongo_result = None
            try:
                collection_name = 'search_results'
                result = db[collection_name].insert_one(summary_data)
                mongo_result = f"mongodb:{result.inserted_id}"
                print(f"✅ Summary data saved to MongoDB with ID: {result.inserted_id}")
                print(f"📊 Collection: {collection_name}, Database: {MONGODB_DATABASE}")
            except Exception as mongo_error:
                if "DocumentTooLarge" in str(mongo_error):
                    print(f"⚠️  MongoDB document too large, saving metadata only...")
                    # Save minimal metadata
                    minimal_data = {
                        'batch_id': batch_id,
                        'query': query,
                        'timestamp': datetime.now().isoformat(),
                        'total_comments': total_comments,
                        'unique_comments': unique_count,
                        'error': 'Data too large for MongoDB',
                        'data_storage': {
                            'full_data_saved_to_files': True,
                            'history_file': f"history/unique_comments_{sanitized_query}_{timestamp}_{batch_id}.json",
                            'videos_file': f"data/{sanitized_query}_videos_{timestamp}_{batch_id}.json"
                        }
                    }
                    try:
                        result = db[collection_name].insert_one(minimal_data)
                        mongo_result = f"mongodb:{result.inserted_id} (metadata only)"
                        print(f"✅ Minimal metadata saved to MongoDB with ID: {result.inserted_id}")
                    except Exception as e:
                        print(f"❌ Failed to save even metadata to MongoDB: {e}")
                        mongo_result = "files_only"
                else:
                    print(f"❌ MongoDB error: {mongo_error}")
                    mongo_result = "files_only"

            # Save full video data to separate JSON file
            try:
                videos_filename = f"data/{sanitized_query}_videos_{timestamp}_{batch_id}.json"
                os.makedirs('data', exist_ok=True)
                videos_data_to_save = {
                    'batch_id': batch_id,
                    'query': query,
                    'timestamp': datetime.now().isoformat(),
                    'youtube_data': youtube_videos,
                    'reddit_data': reddit_posts
                }
                with open(videos_filename, 'w', encoding='utf-8') as f:
                    json.dump(videos_data_to_save, f, indent=2, ensure_ascii=False)
                print(f"✅ Full video data saved to: {videos_filename}")
            except Exception as e:
                print(f"❌ Error saving video data to file: {e}")

            # Also save unique comments to history folder
            try:
                history_filename = f"history/unique_comments_{sanitized_query}_{timestamp}_{batch_id}.json"
                unique_comments_data = {
                    'batch_id': batch_id,
                    'query': query,
                    'timestamp': datetime.now().isoformat(),
                    'total_unique_comments': unique_count,
                    'unique_comments': unique_comments
                }
                with open(history_filename, 'w', encoding='utf-8') as f:
                    json.dump(unique_comments_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Unique comments saved to: {history_filename}")
            except Exception as e:
                print(f"❌ Error saving to history: {e}")

            return mongo_result, summary_data

        except Exception as e:
            print(f"❌ Error saving to MongoDB: {e}")
            import traceback
            traceback.print_exc()
            return None, None

@app.route('/test_mongodb', methods=['GET'])
def test_mongodb():
    """Test MongoDB connection manually"""
    try:
        success, message = test_mongodb_connection()

        if success:
            return jsonify({
                'status': 'success',
                'message': message,
                'database': MONGODB_DATABASE,
                'connection_uri': MONGODB_URI[:50] + '...' if MONGODB_URI else 'Not configured'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': message,
                'database': MONGODB_DATABASE,
                'connection_uri': MONGODB_URI[:50] + '...' if MONGODB_URI else 'Not configured'
            }), 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Test failed: {str(e)}',
            'database': MONGODB_DATABASE
        }), 500

@app.route('/')
def home():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/mongodb_stats', methods=['GET'])
def mongodb_stats():
    """Get MongoDB collection statistics"""
    try:
        client, db = get_mongo_client()
        if client is None or db is None:
            return jsonify({'error': 'MongoDB connection failed'}), 500

        # Get collection stats
        collections = db.list_collection_names()
        stats = {}

        for collection_name in collections:
            collection = db[collection_name]
            count = collection.count_documents({})
            stats[collection_name] = {
                'document_count': count,
                'collection_name': collection_name
            }

        return jsonify({
            'database': MONGODB_DATABASE,
            'collections': stats,
            'total_collections': len(collections)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_filename', methods=['POST'])
def test_filename():
    """Test endpoint to verify filename generation"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()

        if not query:
            return jsonify({'error': 'Please enter a query!'}), 400

        print(f"Testing filename generation for query: {query}")

        # Test the sanitization method directly
        sanitized = query.replace(' ', '_')
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        sanitized = sanitized.rstrip('_')
        if not sanitized:
            sanitized = "query"
        sanitized = sanitized.lower()

        batch_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data/{sanitized}_unified_{timestamp}_{batch_id}.json"

        print(f"Generated filename: {filename}")

        return jsonify({
            'original_query': query,
            'sanitized_query': sanitized,
            'batch_id': batch_id,
            'timestamp': timestamp,
            'filename': filename
        })

    except Exception as e:
        print(f"Error in test_filename: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['POST'])
def search():
    print("=== AI-POWERED MULTI-QUERY SEARCH ENDPOINT CALLED ===")
    try:
        data = request.get_json()
        print(f"Received data: {data}")
        original_query = data.get('query', '').strip()

        print(f"Original Query: '{original_query}'")

        if not original_query:
            print("ERROR: No query provided")
            return jsonify({'error': 'Please enter a valid query!'}), 400

        print("🤖 Generating query variations with Gemini AI...")
        start_time = time.time()

        # Generate 20 query variations using Gemini
        query_variations = generate_query_variations(original_query, num_variations=20)

        if not query_variations:
            return jsonify({'error': 'Failed to generate query variations!'}), 500

        print(f"✅ Generated {len(query_variations)} query variations")

        print("🚀 Starting multi-query aggregation...")
        fetcher = UnifiedCommentFetcher()

        # Process all query variations and aggregate results
        aggregation_result = fetcher.fetch_multiple_queries_aggregated(
            queries=query_variations,
            target_total_comments=50000
        )

        # End timing
        end_time = time.time()
        latency_seconds = end_time - start_time

        if not aggregation_result['videos']:
            return jsonify({'error': 'No content found from any query variation!'}), 404

        # Extract final results
        total_comments = aggregation_result['total_processed_comments']
        total_replies = aggregation_result['total_processed_replies']
        grand_total = aggregation_result['grand_total']
        unique_count = aggregation_result['unique_count']
        unique_comments = aggregation_result['unique_comments']

        print(f"🎯 Final Results:")
        print(f"   Total comments processed: {total_comments}")
        print(f"   Total replies processed: {total_replies}")
        print(f"   Grand total processed: {grand_total}")
        print(f"   Unique comments: {unique_count}")
        print(f"   Target achieved: {aggregation_result['target_achieved']}")
        print(f"   Successful queries: {aggregation_result['successful_queries']}")
        print(f"   Failed queries: {aggregation_result['failed_queries']}")
        print(f"   Total latency: {round(latency_seconds, 2)} seconds")

        # Save unified data
        print("💾 Saving unified data...")
        save_result, combined_data = fetcher.save_unified_data(
            original_query,
            aggregation_result['videos'],
            unique_comments,
            unique_count,
            total_replies,
            grand_total,
            ['youtube', 'reddit']  # Both sources
        )

        print(f"✅ Data saved with result: {save_result}")

        # Calculate some additional stats
        youtube_videos = [v for v in aggregation_result['videos'] if v.get('source') == 'youtube']
        reddit_posts = [v for v in aggregation_result['videos'] if v.get('source') == 'reddit']

        result = {
            'search_query': original_query,
            'query_variations_generated': len(query_variations),
            'batch_id': combined_data['batch_id'] if combined_data else None,
            'sources': ['youtube', 'reddit'],
            'total_youtube_videos': len(youtube_videos),
            'total_reddit_posts': len(reddit_posts),
            'total_comments': total_comments,
            'total_replies': total_replies,
            'grand_total': grand_total,
            'unique_comments': unique_count,
            'videos': aggregation_result['videos'],
            'saved_to': save_result,
            'storage_type': 'mongodb',
            'target_achieved': aggregation_result['target_achieved'],
            'successful_queries': aggregation_result['successful_queries'],
            'failed_queries': aggregation_result['failed_queries'],
            'latency_seconds': round(latency_seconds, 2),
            'query_results': aggregation_result['query_results'],
            'processing_complete': True,
            'ai_powered': True
        }

        print("🎉 AI-powered multi-query search completed successfully!")
        return jsonify(result)

    except Exception as e:
        print(f"ERROR in AI search endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'AI-powered search failed: {str(e)}'}), 500

@app.route('/batch/<batch_id>')
def get_batch(batch_id):
    """Get batch data by ID from MongoDB only"""
    try:
        client, db = get_mongo_client()
        if client is None or db is None:
            return jsonify({'error': 'MongoDB connection failed - cannot retrieve batch data'}), 500

        # Try to find by batch_id
        collection = db['search_results']
        batch_data = collection.find_one({'batch_id': batch_id})

        if not batch_data:
            return jsonify({'error': 'Batch not found in MongoDB!'}), 404

        # Convert ObjectId to string for JSON serialization
        batch_data['_id'] = str(batch_data['_id'])

        return jsonify(batch_data)

    except Exception as e:
        print(f"Error retrieving batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/batches')
def list_batches():
    """List all saved batches from MongoDB only"""
    try:
        client, db = get_mongo_client()
        if client is None or db is None:
            return jsonify({'error': 'MongoDB connection failed - cannot retrieve batches'}), 500

        collection = db['search_results']

        # Get all batches, sorted by timestamp (newest first)
        batches_cursor = collection.find({}, {
            'batch_id': 1,
            'query': 1,
            'timestamp': 1,
            'total_youtube_videos': 1,
            'total_reddit_posts': 1,
            'grand_total': 1,
            'unique_comments': 1,
            'sources': 1
        }).sort('timestamp', -1)

        batches = []
        for batch in batches_cursor:
            batches.append({
                'batch_id': batch['batch_id'],
                'query': batch['query'],
                'timestamp': batch['timestamp'],
                'total_youtube_videos': batch.get('total_youtube_videos', 0),
                'total_reddit_posts': batch.get('total_reddit_posts', 0),
                'grand_total': batch.get('grand_total', 0),
                'unique_comments': batch.get('unique_comments', 0),
                'sources': batch.get('sources', []),
                'storage': 'mongodb'
            })

        return jsonify({'batches': batches, 'total': len(batches)})

    except Exception as e:
        print(f"Error listing batches: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

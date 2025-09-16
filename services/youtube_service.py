"""
YouTube service for video search and comment fetching
Handles YouTube API integration and comment processing
"""
from datetime import datetime
from googleapiclient.discovery import build
from config import Config


class YouTubeService:
    """Service for YouTube API operations and comment fetching"""
    
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.YOUTUBE_API_KEY
        
        if not self.api_key:
            raise ValueError("Please set YOUTUBE_API_KEY in environment variables")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
    
    def sanitize_query_for_filename(self, query):
        """Sanitize query string to be safe for filenames"""
        # Replace spaces with underscores
        sanitized = query.replace(' ', '_')
        # Remove or replace special characters that are problematic in filenames
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        # Limit length to avoid overly long filenames
        if len(sanitized) > self.config.MAX_FILENAME_LENGTH:
            sanitized = sanitized[:self.config.MAX_FILENAME_LENGTH]
        # Remove trailing underscores
        sanitized = sanitized.rstrip('_')
        return sanitized.lower()
    
    def search_videos(self, query, max_results=None):
        """Search for multiple videos based on query"""
        if max_results is None:
            max_results = self.config.MAX_VIDEOS_PER_QUERY
        
        try:
            print(f"🔍 Searching YouTube for: '{query}' (max results: {max_results})")
            
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

            print(f"✅ Found {len(videos)} YouTube videos")
            return videos

        except Exception as e:
            print(f"❌ Error searching YouTube videos: {e}")
            return []
    
    def get_comments(self, video_id, max_comments=None):
        """Fetch comments and replies from a video"""
        if max_comments is None:
            max_comments = self.config.MAX_COMMENTS_PER_VIDEO
        
        try:
            print(f"💬 Fetching comments for video: {video_id} (max: {max_comments})")
            
            comments = []
            next_page_token = None

            while len(comments) < max_comments:
                try:
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
                        
                except Exception as e:
                    print(f"⚠️  Error fetching comments page: {e}")
                    break

            print(f"✅ Fetched {len(comments)} comments from video {video_id}")
            return comments

        except Exception as e:
            print(f"❌ Error fetching comments from video {video_id}: {e}")
            return []
    
    def get_video_details(self, video_id):
        """Get detailed information about a video"""
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            ).execute()
            
            if response['items']:
                video = response['items'][0]
                return {
                    'video_id': video_id,
                    'title': video['snippet']['title'],
                    'description': video['snippet']['description'],
                    'channel_title': video['snippet']['channelTitle'],
                    'published_at': video['snippet']['publishedAt'],
                    'view_count': int(video['statistics'].get('viewCount', 0)),
                    'like_count': int(video['statistics'].get('likeCount', 0)),
                    'comment_count': int(video['statistics'].get('commentCount', 0)),
                    'duration': video['contentDetails']['duration'],
                    'thumbnails': video['snippet']['thumbnails']
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting video details for {video_id}: {e}")
            return None
    
    def search_and_get_comments(self, query, max_videos=None, max_comments_per_video=None):
        """Search for videos and get their comments in one operation"""
        if max_videos is None:
            max_videos = self.config.MAX_VIDEOS_PER_QUERY
        if max_comments_per_video is None:
            max_comments_per_video = self.config.MAX_COMMENTS_PER_VIDEO
        
        print(f"🚀 Starting YouTube search and comment fetch for: '{query}'")
        
        # Search for videos
        videos = self.search_videos(query, max_videos)
        
        if not videos:
            print("❌ No videos found")
            return []
        
        # Get comments for each video
        videos_with_comments = []
        total_comments = 0
        
        for i, video in enumerate(videos):
            try:
                print(f"📹 Processing video {i+1}/{len(videos)}: {video['title'][:50]}...")
                comments = self.get_comments(video['video_id'], max_comments_per_video)
                
                video_data = {
                    'video_info': video,
                    'comments': comments,
                    'comment_count': len(comments),
                    'source': 'youtube'
                }
                
                videos_with_comments.append(video_data)
                total_comments += len(comments)
                
                print(f"  ✅ Got {len(comments)} comments")
                
            except Exception as e:
                print(f"  ❌ Error processing video {i+1}: {e}")
                continue
        
        print(f"🎯 YouTube fetch complete: {len(videos_with_comments)} videos, {total_comments} total comments")
        return videos_with_comments
    
    def get_trending_videos(self, max_results=10, region_code='US'):
        """Get trending videos for a region"""
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics',
                chart='mostPopular',
                regionCode=region_code,
                maxResults=max_results
            ).execute()
            
            trending_videos = []
            for item in response['items']:
                video_data = {
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'channel': item['snippet']['channelTitle'],
                    'description': item['snippet']['description'],
                    'published_at': item['snippet']['publishedAt'],
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'like_count': int(item['statistics'].get('likeCount', 0)),
                    'comment_count': int(item['statistics'].get('commentCount', 0)),
                    'thumbnail': item['snippet']['thumbnails']['high']['url'] if 'high' in item['snippet']['thumbnails'] else item['snippet']['thumbnails']['default']['url']
                }
                trending_videos.append(video_data)
            
            return trending_videos
            
        except Exception as e:
            print(f"❌ Error getting trending videos: {e}")
            return []


# Global YouTube service instance
youtube_service = YouTubeService()
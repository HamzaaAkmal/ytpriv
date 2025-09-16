# YouTube + Reddit Comment Scraper

A powerful web application that fetches comments from both YouTube and Reddit simultaneously, providing comprehensive social media sentiment analysis.

## 🚀 Features

- **Dual Platform Integration**: Fetches comments from YouTube and Reddit in parallel
- **Minimum 5000 Comments**: Ensures comprehensive data collection
- **Automatic Deduplication**: Removes duplicate comments and processes unique content
- **Unified Data Storage**: Saves all data in a single, well-organized JSON file
- **Real-time Progress**: Shows live updates during the search process
- **Modern UI**: Clean, responsive interface with source badges
- **Parallel Processing**: Concurrent API calls for faster data collection

## 📋 Requirements

- Python 3.8+
- YouTube Data API v3 key
- Reddit API credentials

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd youtube-reddit-scraper
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API credentials**

   Edit the `.env` file with your API keys:

   ```env
   # YouTube API Key
   YOUTUBE_API_KEY=your_youtube_api_key_here

   # Reddit API Credentials
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=comment_scraper_downlab
   ```

## 🔑 API Setup

### YouTube API Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable YouTube Data API v3
4. Create credentials (API Key)
5. Copy the API key to `.env`

### Reddit API Setup
1. Go to [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Create a new app (select "script" type)
3. Copy the following credentials:
   - **Client ID**: The string under the app name
   - **Client Secret**: The "secret" field
   - **User Agent**: Choose a descriptive name
4. Add these to your `.env` file

## 🚀 Usage

1. **Start the application**
   ```bash
   python app.py
   ```

2. **Open your browser**
   ```
   http://127.0.0.1:5000
   ```

3. **Enter your search query**
   - Type any topic, keyword, or question
   - Click "Search YouTube & Reddit"

4. **Wait for results**
   - The app will search both platforms simultaneously
   - Progress updates will be shown in real-time
   - Minimum 5000 comments will be collected

5. **View results**
   - See statistics from both platforms
   - Browse comments with source badges
   - Data is automatically saved to `data/` folder

## 📊 Data Structure

The application saves data in the following format:

```json
{
  "batch_id": "abc123",
  "query": "your search query",
  "timestamp": "2025-01-04T10:30:00",
  "sources": ["youtube", "reddit"],
  "total_youtube_videos": 15,
  "total_reddit_posts": 25,
  "total_comments": 5200,
  "unique_comments": 4800,
  "total_replies": 1200,
  "youtube_data": [...],
  "reddit_data": [...],
  "unique_comments_data": [...],
  "processing_info": {...}
}
```

## 🎯 Key Features

### Parallel Processing
- YouTube and Reddit APIs are called simultaneously
- Faster data collection with ThreadPoolExecutor
- Error handling for individual API failures

### Smart Comment Collection
- Searches relevant subreddits automatically
- Fetches comments from multiple YouTube videos
- Includes replies and nested comments
- Minimum 5000 comments guarantee

### Data Deduplication
- Removes duplicate comments across platforms
- Processes unique content only
- Maintains source attribution

### Modern Interface
- Clean, responsive design
- Source badges (YouTube/Reddit)
- Real-time progress updates
- Error handling with user feedback

## 📁 Project Structure

```
youtube-reddit-scraper/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── .env                       # API credentials (create this)
├── templates/
│   └── index.html             # Main web interface
├── static/
│   ├── css/
│   │   └── style.css          # Styling
│   └── js/
│       └── script_test.js     # Frontend JavaScript
└── data/                      # Output directory (auto-created)
```

## 🔧 Configuration

### Environment Variables
- `YOUTUBE_API_KEY`: Your YouTube Data API v3 key
- `REDDIT_CLIENT_ID`: Reddit app client ID
- `REDDIT_CLIENT_SECRET`: Reddit app client secret
- `REDDIT_USER_AGENT`: Reddit app user agent

### Search Parameters
- **Query**: Any search term or question
- **Minimum Comments**: 5000 (configurable in code)
- **Timeout**: 3 minutes for API calls
- **Parallel Workers**: 2 (YouTube + Reddit)

## 🚨 Important Notes

- **Rate Limits**: Both APIs have rate limits
  - YouTube: 10,000 units per day
  - Reddit: Varies by endpoint
- **Data Volume**: Large searches may take several minutes
- **Storage**: JSON files can be large (several MB)
- **API Costs**: YouTube API has a small cost for high usage

## 🐛 Troubleshooting

### Common Issues

1. **"YouTube API key not found"**
   - Check your `.env` file
   - Ensure YouTube API is enabled
   - Verify API key is correct

2. **"Reddit API credentials invalid"**
   - Check client ID and secret
   - Ensure user agent is set
   - Verify app type is "script"

3. **Timeout errors**
   - Large queries may take time
   - Check internet connection
   - Try smaller queries first

4. **No results found**
   - Try different search terms
   - Check API quotas
   - Verify API keys are active

## 📈 Performance Tips

- Use specific search queries
- Start with smaller tests
- Monitor API usage quotas
- Clean old data files periodically

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source. Please check the license file for details.

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section
2. Review API documentation
3. Create an issue on GitHub

---

**Happy scraping!** 🎉

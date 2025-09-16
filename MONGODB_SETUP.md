# MongoDB Atlas Setup Guide

## 🚀 Quick Setup for MongoDB Integration

### Step 1: MongoDB Atlas Configuration
1. Go to [MongoDB Atlas](https://cloud.mongodb.com/)
2. Log in to your account
3. Select your project (or create a new one)

### Step 2: Check Database Access
1. Go to **Database Access** (left sidebar)
2. Make sure the user `mkamranashrafali_db_user` exists
3. If not, create a new user with:
   - Username: `mkamranashrafali_db_user`
   - Password: Your chosen password
   - Built-in Role: `Read and write` or `Atlas admin`

### Step 3: Check Network Access
1. Go to **Network Access** (left sidebar)
2. Make sure your IP address is whitelisted
3. If not added, click **Add IP Address** and add `0.0.0.0/0` for testing (allow from anywhere)

### Step 4: Update Connection String
1. Go to **Clusters** (left sidebar)
2. Click **Connect** on your cluster
3. Choose **Connect your application**
4. Copy the connection string and replace the password
5. Update your `.env` file with the correct `MONGODB_URI`

### Step 5: Test Connection
1. Run the Flask app: `python app.py`
2. Open browser to: `http://127.0.0.1:5000/test_mongodb`
3. Check the response for connection status

## 🔧 Troubleshooting

### Authentication Failed
- ✅ Check username/password in connection string
- ✅ Verify user exists in Database Access
- ✅ Ensure user has read/write permissions
- ✅ Check IP whitelist in Network Access

### Connection Timeout
- ✅ Check internet connection
- ✅ Verify cluster is running (not paused)
- ✅ Check firewall settings
- ✅ Try different network

### Database Not Found
- ✅ Check database name in `MONGODB_DATABASE`
- ✅ Ensure database exists or will be created automatically

## 📝 Current Configuration
- **URI**: mongodb+srv://mkamranashrafali_db_user:***@cluster0.ydfsgsw.mongodb.net/
- **Database**: youtube_scraper
- **Status**: Authentication issue detected

## 🛠️ Alternative: Local MongoDB
If Atlas doesn't work, you can use local MongoDB:
1. Install MongoDB locally
2. Update `.env`: `MONGODB_URI="mongodb://localhost:27017"`
3. Update `.env`: `MONGODB_DATABASE="youtube_scraper"`

## 📞 Support
If you continue having issues:
1. Check MongoDB Atlas logs
2. Verify cluster tier (free tier has limitations)
3. Contact MongoDB Atlas support</content>
<parameter name="filePath">c:\Users\Lenovo\Desktop\getopinion\Youtube-Scrapping\MONGODB_SETUP.md

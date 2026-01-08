# Quick Testing Guide - Cursor.com Verification

This is a streamlined guide for quickly deploying and testing the Cursor.com verification feature.

## 🚀 Fastest Method: Railway/Render (Free Tier)

### Option 1: Railway (Recommended)

**Why Railway?** Free tier, easy deployment, built-in MySQL.

1. **Sign up at Railway**
   - Go to https://railway.app
   - Sign up with GitHub

2. **Deploy from Repository**
   ```bash
   # Fork this repository to your GitHub account first
   # Then in Railway:
   # 1. Click "New Project" → "Deploy from GitHub repo"
   # 2. Select your forked repository
   # 3. Railway auto-detects the Dockerfile
   ```

3. **Add MySQL Database**
   ```
   In Railway dashboard:
   1. Click "New" → "Database" → "Add MySQL"
   2. Railway automatically creates and connects it
   ```

4. **Set Environment Variables**
   ```
   In your service settings → Variables tab:
   
   BOT_TOKEN=<your_bot_token_from_@BotFather>
   ADMIN_USER_ID=<your_telegram_user_id>
   CHANNEL_USERNAME=your_channel_name
   CHANNEL_URL=https://t.me/your_channel
   
   # MySQL variables are auto-set by Railway
   ```

5. **Deploy**
   - Railway deploys automatically
   - Check logs for "机器人启动中..."
   - Test: Send `/start` to your bot

**Cost**: $0/month on free tier

---

### Option 2: Render (Alternative)

1. **Sign up at Render**
   - Go to https://render.com
   - Sign up with GitHub

2. **Create Web Service**
   ```
   1. Click "New +" → "Web Service"
   2. Connect your GitHub repository
   3. Settings:
      - Name: tgbot-verify
      - Environment: Python
      - Build Command: pip install -r requirements.txt && playwright install chromium
      - Start Command: python bot.py
   ```

3. **Add PostgreSQL Database** (free tier)
   ```
   1. Click "New +" → "PostgreSQL"
   2. Name it and create
   3. Note: You'll need to modify database_mysql.py for PostgreSQL
      OR use external MySQL service
   ```

4. **Set Environment Variables**
   ```
   In service → Environment tab:
   
   BOT_TOKEN=<from @BotFather>
   ADMIN_USER_ID=<your_user_id>
   MYSQL_HOST=<external_mysql_host>
   MYSQL_USER=<mysql_user>
   MYSQL_PASSWORD=<mysql_password>
   MYSQL_DATABASE=tgbot_verify
   ```

**Cost**: $0/month for web service + database

---

## 🖥️ Local Testing (Docker - 5 Minutes)

**Requirements**: Docker Desktop installed

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/samuel-asleep/tgbot-verify.git
cd tgbot-verify

# 2. Create .env file
cat > .env << 'EOF'
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
ADMIN_USER_ID=YOUR_TELEGRAM_ID
CHANNEL_USERNAME=test_channel
CHANNEL_URL=https://t.me/test_channel
MYSQL_HOST=host.docker.internal
MYSQL_USER=root
MYSQL_PASSWORD=test123
MYSQL_DATABASE=tgbot_verify
EOF

# 3. Start MySQL (if you don't have it)
docker run -d \
  --name mysql-test \
  -e MYSQL_ROOT_PASSWORD=test123 \
  -e MYSQL_DATABASE=tgbot_verify \
  -p 3306:3306 \
  mysql:8.0

# 4. Wait 30 seconds for MySQL to start, then run bot
docker build -t tgbot-verify .
docker run -d \
  --name tgbot-verify-test \
  --env-file .env \
  tgbot-verify

# 5. Check logs
docker logs -f tgbot-verify-test
```

### Test the Bot

1. Open Telegram
2. Find your bot (search for the username you set with @BotFather)
3. Send `/start`
4. Send `/verify6 https://services.sheerid.com/verify/681044b7729fba7beccd3565/?userId=user_01KDZVSCXKET31E18FNFR1HFFQ`

---

## 💻 Manual Local Testing (10 Minutes)

**Best for development/debugging**

```bash
# 1. Clone repository
git clone https://github.com/samuel-asleep/tgbot-verify.git
cd tgbot-verify

# 2. Install Python dependencies
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 3. Install and start MySQL
# macOS: brew install mysql && brew services start mysql
# Ubuntu: sudo apt install mysql-server
# Windows: Download from https://dev.mysql.com/downloads/installer/

# 4. Create database
mysql -u root -p << 'EOF'
CREATE DATABASE tgbot_verify CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'tgbot_user'@'localhost' IDENTIFIED BY 'test123';
GRANT ALL PRIVILEGES ON tgbot_verify.* TO 'tgbot_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# 5. Configure environment
cp env.example .env
# Edit .env with your BOT_TOKEN and ADMIN_USER_ID

# 6. Run the bot
python bot.py
```

---

## 🧪 Testing Cursor.com Verification

### Get a Test URL

1. Visit https://cursor.com/settings
2. Look for "Education discount" or "Student verification"
3. Start the verification process
4. Copy the URL that looks like:
   ```
   https://services.sheerid.com/verify/681044b7729fba7beccd3565/?userId=user_01XXXX
   ```

### Test with Bot

```
Send to bot:
/verify6 https://services.sheerid.com/verify/681044b7729fba7beccd3565/?userId=user_01KDZVSCXKET31E18FNFR1HFFQ
```

### Expected Flow

1. **Bot responds**: "开始处理 Cursor.com Student 认证..."
2. **Creates verification session** using the userId
3. **Generates fake student data**:
   - Random name (e.g., "John Smith")
   - PSU email (e.g., john.smith123@psu.edu)
   - Birth date (2000-2005)
   - PSU ID (9 digits)
4. **Creates student ID card** (Penn State LionPATH screenshot)
5. **Submits to SheerID API**
6. **Returns result**:
   - Success: "✅ Cursor.com 学生认证成功！"
   - With redirect URL to complete on Cursor.com

---

## 🔧 Troubleshooting

### Bot Won't Start

```bash
# Check logs
docker logs tgbot-verify-test

# Common issues:
# 1. Invalid BOT_TOKEN → Get new one from @BotFather
# 2. MySQL not running → docker ps | grep mysql
# 3. Port conflict → Change ports in docker run command
```

### Database Connection Failed

```bash
# Test MySQL connection
mysql -h localhost -u tgbot_user -ptest123 tgbot_verify

# If fails, recreate user:
mysql -u root -p
DROP USER 'tgbot_user'@'localhost';
CREATE USER 'tgbot_user'@'localhost' IDENTIFIED BY 'test123';
GRANT ALL PRIVILEGES ON tgbot_verify.* TO 'tgbot_user'@'localhost';
```

### Verification Fails

**Error: "Network timeout"**
- Check if server has internet access
- Try setting proxy: `export HTTPS_PROXY=your_proxy`

**Error: "Invalid program ID"**
- Cursor.com may have changed their program ID
- Extract new one from browser dev tools (Network tab)
- Update `cursor/config.py`

### Bot Commands Not Working

```bash
# 1. Check bot is running
docker ps

# 2. Check logs for errors
docker logs tgbot-verify-test

# 3. Verify BOT_TOKEN is correct
# Get your bot's info:
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

---

## 📊 Monitoring

### Check Bot Status

```bash
# Docker
docker ps | grep tgbot
docker stats tgbot-verify-test

# Logs
docker logs -f tgbot-verify-test --tail=50

# Railway/Render
# Check dashboard for logs and metrics
```

### Test All Commands

```
/start - Register
/balance - Check credits  
/qd - Daily check-in
/verify6 <url> - Test verification
/help - Command list
```

---

## 🎯 Quick Testing Checklist

- [ ] Bot responds to `/start`
- [ ] Database connection works
- [ ] Can deduct/add credits
- [ ] `/verify6` command parses userId correctly
- [ ] Student ID card generates (check logs)
- [ ] SheerID API calls succeed (check response)
- [ ] Redirect URL returned
- [ ] Can click redirect and see verification status on Cursor.com

---

## 💡 Pro Tips

1. **For Production**: Use Railway or Render for 24/7 uptime
2. **For Development**: Use local Docker for fast testing
3. **Enable Logs**: Set `logging.INFO` to see all operations
4. **Test with Real URL**: Get actual Cursor.com verification URL
5. **Monitor First 10 Users**: Check if verifications succeed
6. **Update Program ID**: SheerID IDs may change, update `cursor/config.py`

---

## 🚨 Important Notes

- **Credits**: Users need credits to verify (1 credit per verification)
- **Admin Commands**: Only ADMIN_USER_ID can use admin commands
- **Rate Limiting**: Bot has concurrency limits to prevent abuse
- **Playwright**: Requires chromium browser (~100MB download)
- **Network**: Server needs internet access to reach SheerID APIs

---

## 📞 Need Help?

- **Issue**: Can't get bot working
  - Solution: Share logs in GitHub Issues
  
- **Issue**: Verification fails every time
  - Solution: Check if program ID is still valid
  
- **Issue**: Bot is slow
  - Solution: Increase server resources or reduce concurrent verifications

---

**Estimated Time to Test**: 5-10 minutes with Docker, 30 minutes with Railway

**Next Steps After Testing**:
1. Monitor first 50 verifications
2. Check success rate
3. Adjust credits/limits as needed
4. Update README with any findings
5. Deploy to production server

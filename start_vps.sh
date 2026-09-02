#!/bin/bash

# ==========================================
# VPS Deployment Script for Prithu ML Engine
# ==========================================

echo "🚀 Starting deployment for Prithu ML Engine..."

# 1. Ensure Python 3 and venv are installed (Ubuntu/Debian)
# Uncomment the line below if Python isn't installed yet
# sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# 2. Create the virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# 5. Install uvicorn explicitly if it's not in requirements
pip install uvicorn

# 6. Ensure PM2 is installed globally (requires Node.js)
if ! command -v pm2 &> /dev/null
then
    echo "⚙️  Installing PM2..."
    npm install -g pm2
fi

# 7. Start the application using PM2
echo "🔥 Starting ML Engine via PM2..."
pm2 start ecosystem.config.js

# 8. Save PM2 state so it restarts on server reboot
pm2 save
pm2 startup

echo "✅ ML Engine is now running in the background on port 8001!"
echo "👉 Use 'pm2 logs prithu-ml-engine' to view logs."
echo "👉 Use 'pm2 status' to check the status."

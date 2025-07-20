#!/bin/bash

# Paper Manager Configuration Setup Script (macOS/Linux)
echo "========================================"
echo "    Paper Manager Configuration Setup"
echo "========================================"
echo

# Check and activate virtual environment
if [ -d "paper_manager_env" ]; then
    echo "✅ Activating virtual environment..."
    source paper_manager_env/bin/activate
    echo "🐍 Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Virtual environment not found"
    echo "Please run ./quick_install.sh first"
    exit 1
fi

echo
echo "🚀 Starting configuration tool..."
echo "📱 Browser will open automatically at http://localhost:8502"
echo "🛑 Press Ctrl+C to stop"
echo

# Start the setup-only Streamlit app
streamlit run setup_only.py --server.port 8502
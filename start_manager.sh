#\!/bin/bash

# スクリプトのあるディレクトリに移動
cd "$(dirname "$0")"

# Paper Manager GUI Startup Script (macOS/Linux)
echo "========================================"
echo "    Paper Manager GUI Startup"
echo "========================================"
echo

# Check if virtual environment exists
if [ -d "paper_manager_env" ]; then
    echo "✅ Activating virtual environment..."
    source paper_manager_env/bin/activate
    echo "🐍 Virtual environment activated: $VIRTUAL_ENV"
else
    echo "⚠️  Virtual environment not found."
    echo "❓ Do you want to create one? (y/n)"
    read -r create_venv
    
    if [[ $create_venv =~ ^[Yy]$ ]]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv paper_manager_env
        source paper_manager_env/bin/activate
        echo "✅ Virtual environment created"
        
        echo "📦 Installing GUI dependencies..."
        pip install streamlit plotly PyYAML python-dotenv pydantic requests
    else
        echo "Using system Python"
    fi
fi

echo
echo "🚀 Starting Paper Manager GUI..."
echo "📱 Browser will open automatically at http://localhost:8501"
echo "🛑 Press Ctrl+C to stop the server"
echo

# Check configuration status
echo "🔍 Checking configuration..."
python check_config.py
if [ $? -ne 0 ]; then
    echo
    echo "==============================================="
    echo "    Configuration Required - Starting Setup"
    echo "==============================================="
    echo
    echo "Your Paper Manager is not configured yet."
    echo "Starting the configuration tool..."
    echo
    read -p "Press Enter to continue..."
    
    # Start setup tool instead
    ./setup_config.sh
    exit 0
else
    echo "✅ Configuration OK - Starting main application..."
fi

# Start the GUI
python start_manager.py

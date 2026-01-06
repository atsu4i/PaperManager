#!/bin/bash
# Paper Searcher Launcher (Mac/Linux)

# スクリプトのあるディレクトリに移動
cd "$(dirname "$0")"

echo "========================================"
echo "   Paper Searcher Starting..."
echo "========================================"
echo ""

# Check and activate virtual environment
if [ -d "paper_manager_env" ]; then
    echo "Activating virtual environment..."
    source paper_manager_env/bin/activate
    echo "Virtual environment activated: $VIRTUAL_ENV"
else
    echo "Virtual environment not found. Using system Python."
fi

# Check Python version
echo "Using Python: $(which python3)"
python3 --version

# Check if Streamlit is installed
python3 -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: Streamlit is not installed."
    echo "Please run: pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Start Paper Searcher
echo "Starting Paper Searcher..."
echo "Browser will open automatically at http://localhost:8503"
echo "Press Ctrl+C to exit."
echo ""

python3 start_searcher.py

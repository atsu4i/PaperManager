#!/bin/bash

# Paper Manager Quick Install Script (macOS/Linux)
echo "========================================"
echo "    Paper Manager Quick Install"
echo "========================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python first."
    echo "📝 Visit: https://www.python.org/downloads/"
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"

# Check and create virtual environment
if [ -d "paper_manager_env" ]; then
    echo "✅ Virtual environment found"
    source paper_manager_env/bin/activate
else
    echo "📦 Creating virtual environment..."
    python3 -m venv paper_manager_env
    source paper_manager_env/bin/activate
    echo "✅ Virtual environment created"
fi

echo "🐍 Using Python: $(which python)"
echo

echo "📦 Installing all dependencies..."

# Try different installation methods
echo "Step 1: Installing from requirements.txt..."
if pip install -r requirements.txt; then
    echo "✅ All packages installed successfully"
else
    echo "⚠️  requirements.txt failed, trying simplified version..."
    echo "Step 2: Installing from requirements-simple.txt..."
    
    if pip install -r requirements-simple.txt; then
        echo "✅ All packages installed successfully"
    else
        echo "⚠️  Simplified installation failed, trying essential packages..."
        echo "Step 3: Installing essential packages individually..."
        
        # Essential packages
        essential_packages=(
            "streamlit>=1.28.0"
            "plotly>=5.17.0"
            "PyYAML>=6.0.0"
            "python-dotenv>=1.0.0"
            "pydantic>=2.6.0"
            "requests>=2.31.0"
        )
        
        for package in "${essential_packages[@]}"; do
            echo "   Installing $package..."
            pip install "$package" || echo "⚠️  Failed to install $package"
        done
        
        echo "Essential packages installation completed with possible warnings"
    fi
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p pdfs processed_pdfs logs credentials

echo
echo "========================================"
echo "    Installation Complete!"
echo "========================================"
echo
echo "You can now:"
echo "  1. Run Manager GUI: ./start_manager.sh"
echo "  2. Run Paper Searcher: ./start_searcher.sh"
echo "  3. Run CLI: python cli.py config"
echo
echo "💡 First run will show setup wizard for API configuration"
echo

echo "Press Enter to continue..."
read -r
#!/usr/bin/env python3
"""
Paper Manager GUI インストールスクリプト
GUI依存関係を自動インストールします
"""

import sys
import subprocess
import os
from pathlib import Path

def check_package(package_name):
    """パッケージがインストールされているかチェック"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

def install_packages():
    """必要なパッケージをインストール"""
    packages = [
        "streamlit>=1.28.0",
        "plotly>=5.17.0"
    ]
    
    print("📦 Installing GUI packages...")
    print(f"🐍 Using Python: {sys.executable}")
    
    for package in packages:
        print(f"   Installing {package}...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package
            ])
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    return True

def main():
    """メイン関数"""
    print("=" * 50)
    print("   Paper Manager GUI Setup")
    print("=" * 50)
    print()
    
    # 仮想環境の確認
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment detected")
        print(f"   Environment: {os.environ.get('VIRTUAL_ENV', 'Unknown')}")
    else:
        print("⚠️  No virtual environment detected")
        print("   Using system Python")
    
    print()
    
    # 既存パッケージの確認
    print("🔍 Checking existing packages...")
    
    streamlit_installed = check_package("streamlit")
    plotly_installed = check_package("plotly")
    
    if streamlit_installed:
        print("   ✅ Streamlit is already installed")
    else:
        print("   ❌ Streamlit not found")
    
    if plotly_installed:
        print("   ✅ Plotly is already installed")
    else:
        print("   ❌ Plotly not found")
    
    print()
    
    # インストールが必要かチェック
    if streamlit_installed and plotly_installed:
        print("🎉 All GUI packages are already installed!")
        print("📱 You can now run: python start_gui.py")
    else:
        print("📦 Installing missing packages...")
        if install_packages():
            print("✅ Installation completed successfully!")
            print("📱 You can now run: python start_gui.py")
        else:
            print("❌ Installation failed!")
            print("💡 Please check your internet connection and try again")
            return 1
    
    print()
    input("Press Enter to continue...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
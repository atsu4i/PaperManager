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
    print("📦 Installing all required packages...")
    print(f"🐍 Using Python: {sys.executable}")
    
    # Step 1: Try requirements.txt
    try:
        print("   Installing from requirements.txt...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ All packages installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install from requirements.txt: {e}")
    
    # Step 2: Try requirements-simple.txt (without comments)
    try:
        print("   Trying requirements-simple.txt...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements-simple.txt"
        ])
        print("✅ All packages installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install from requirements-simple.txt: {e}")
    
    # Step 3: Fallback to individual packages
    print("📦 Trying individual package installation...")
    
    # Essential packages for GUI
    essential_packages = [
        "streamlit>=1.28.0",
        "plotly>=5.17.0",
        "PyYAML>=6.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.6.0",
        "requests>=2.31.0",
        "pathlib"
    ]
    
    failed_packages = []
    for package in essential_packages:
        print(f"   Installing {package}...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package
            ])
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            failed_packages.append(package)
    
    if failed_packages:
        print(f"⚠️  Some packages failed to install: {failed_packages}")
        print("💡 GUI may work with limited functionality")
        return len(failed_packages) < len(essential_packages) / 2  # 半分以上成功なら OK
    
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
    
    # 必要なパッケージの確認
    print("🔍 Checking required packages...")
    
    required_packages = ["streamlit", "plotly", "yaml", "dotenv", "pydantic"]
    missing_packages = []
    
    for package in required_packages:
        package_name = package if package != "yaml" else "PyYAML"
        module_name = package if package != "dotenv" else "dotenv"
        
        if check_package(module_name):
            print(f"   ✅ {package_name} is installed")
        else:
            print(f"   ❌ {package_name} not found")
            missing_packages.append(package)
    
    print()
    
    # インストールが必要かチェック
    if not missing_packages:
        print("🎉 All required packages are already installed!")
        print("📱 You can now run: python start_gui.py")
    else:
        print(f"📦 Installing {len(missing_packages)} missing packages...")
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
"""
Simple build script for Xiaoyuan desktop app
Usage: python build.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).parent

def clean():
    """Clean previous builds"""
    for dir_name in ['build', 'dist']:
        dir_path = ROOT_DIR / dir_name
        if dir_path.exists():
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_path)

def build():
    """Build using PyInstaller"""
    print("Building Xiaoyuan desktop app...")
    
    # Install PyInstaller if needed
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Build using spec file
    spec_file = ROOT_DIR / "xiaoyuan.spec"
    if spec_file.exists():
        cmd = [sys.executable, "-m", "PyInstaller", str(spec_file)]
    else:
        # Fallback to command line
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name=Xiaoyuan",
            "--onedir",
            "--windowed",
            "--noconfirm",
            f"--paths={ROOT_DIR}",
            "--hidden-import=uvicorn",
            "--hidden-import=backend",
            "--collect-all=backend",
            "--collect-all=uvicorn",
            str(ROOT_DIR / "run.py"),
        ]
    
    subprocess.check_call(cmd)
    print("\nBuild complete!")
    print(f"Output: {ROOT_DIR / 'dist' / 'Xiaoyuan'}")

if __name__ == "__main__":
    print("=" * 50)
    print("  小圆助教 桌面应用构建")
    print("=" * 50)
    
    clean()
    build()
    
    print("\n" + "=" * 50)
    print("  构建完成！")
    print("=" * 50)
    print("\n发布方式：")
    print("1. 分发 dist/Xiaoyuan 文件夹（便携版）")
    print("2. 用 Inno Setup 等工具制作安装包")

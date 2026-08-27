import sys
import os
import webbrowser
import threading
import time
import logging
import signal

import uvicorn

def open_browser():
    """Open browser after a short delay"""
    time.sleep(2)
    webbrowser.open("http://localhost:8000")

def create_tray_icon(server_process):
    """Create system tray icon with quit option"""
    try:
        import pystray
        from PIL import Image
        
        # Load icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "tray_icon.png")
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path)
        else:
            # Create a simple fallback icon
            icon_image = Image.new('RGBA', (64, 64), (150, 187, 133, 255))
        
        def on_quit(icon, item):
            """Quit the application"""
            icon.stop()
            os._exit(0)
        
        def on_show(icon, item):
            """Show browser window"""
            webbrowser.open("http://localhost:8000")
        
        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("打开小圆助教", on_show, default=True),
            pystray.MenuItem("退出", on_quit)
        )
        
        # Create icon
        icon = pystray.Icon(
            "xiaoyuan",
            icon_image,
            "小圆助教",
            menu
        )
        
        # Run icon in background
        icon.run_detached()
        return icon
    except Exception as e:
        print(f"Failed to create tray icon: {e}")
        return None

if __name__ == "__main__":
    # Fix: when running as.exe, stdout/stderr are None
    if getattr(sys, 'frozen', False):
        if sys.stdout is None:
            sys.stdout = open(os.devnull, 'w', encoding='utf-8')
        if sys.stderr is None:
            sys.stderr = open(os.devnull, 'w', encoding='utf-8')
        
        # Create tray icon
        tray_icon = create_tray_icon(None)
        
        # Open browser in background
        threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    
    print("小圆助教启动中...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)

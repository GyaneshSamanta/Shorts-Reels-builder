"""
Creates a .lnk shortcut on the Desktop for the start_app.bat with the custom icon.
Run this once after cloning / setting up the project.
"""
import os, sys

def create_shortcut():
    try:
        import winshell
        from win32com.client import Dispatch
    except ImportError:
        print("Install winshell + pypiwin32 first:  pip install winshell pypiwin32")
        return

    base = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(base, "start_app.bat")
    icon   = os.path.join(base, "assets", "icon.ico")
    desktop = winshell.desktop()
    lnk = os.path.join(desktop, "Podcast-to-Shorts.lnk")

    shell = Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(lnk)
    sc.TargetPath = target
    sc.WorkingDirectory = base
    if os.path.exists(icon):
        sc.IconLocation = icon
    sc.Description = "Launch Podcast-to-Shorts"
    sc.save()
    print(f"Shortcut created: {lnk}")

if __name__ == "__main__":
    create_shortcut()

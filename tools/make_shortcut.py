"""Puts a MyVocab shortcut on the desktop and in the app menu (the Start menu on
Windows), so the app starts with a double-click instead of ./run.sh. On Windows,
install.bat does this for you. Otherwise run it once:

    python3 tools/make_shortcut.py        (Linux)
    py tools\\make_shortcut.py             (Windows)

The shortcut opens a window that shows the app's log; closing it stops the app.
To remove it, delete the shortcut from the desktop and from the menu
(~/.local/share/applications/myvocab.desktop on Linux).
"""
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PNG = os.path.join(ROOT, "static", "img", "favicon.png")


def windows_folder(name):
    """A special folder, such as Desktop or Programs (the Start menu), wherever Windows keeps it (OneDrive too)."""
    out = subprocess.run(["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{name}')"],
                         capture_output=True, text=True)
    return out.stdout.strip()


def desktop_dir():
    if os.name == "nt":
        return windows_folder("Desktop") or os.path.join(os.path.expanduser("~"), "Desktop")
    try:
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except FileNotFoundError:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def linux():
    entry = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=MyVocab",
        "Comment=Learn English: dictionary, practice, listening, reading and writing",
        f'Exec="{os.path.join(ROOT, "run.sh")}"',  # run.sh moves into its own folder
        f"Path={ROOT}",
        f"Icon={ICON_PNG}",
        "Terminal=true",
        "Categories=Education;",
        "StartupNotify=false",
        "",
    ])
    menu = os.path.expanduser("~/.local/share/applications/myvocab.desktop")
    desk = os.path.join(desktop_dir(), "myvocab.desktop")
    for path in (menu, desk):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(entry)
        os.chmod(path, 0o755)
    # Cinnamon (Linux Mint) and GNOME only run desktop launchers marked as trusted.
    subprocess.run(["gio", "set", desk, "metadata::trusted", "true"], capture_output=True)
    print(f"Shortcut on the desktop: {desk}\nAnd in the app menu: {menu}")


def png_to_ico(png_path, ico_path):
    """An .ico that simply wraps the PNG (Windows Vista and later read these)."""
    data = open(png_path, "rb").read()
    width, height = struct.unpack(">II", data[16:24])
    size = lambda n: 0 if n >= 256 else n
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size(width), size(height), 0, 0, 1, 32, len(data), 6 + 16)
    with open(ico_path, "wb") as f:
        f.write(header + entry + data)


def windows():
    ico = os.path.join(ROOT, "static", "img", "favicon.ico")
    png_to_ico(ICON_PNG, ico)
    # (shortcut, what it opens, its tooltip)
    links = [(os.path.join(desktop_dir(), "MyVocab.lnk"), "run.bat", "Start MyVocab")]
    programs = windows_folder("Programs")
    if programs:  # the Start menu
        links += [
            (os.path.join(programs, "MyVocab.lnk"), "run.bat", "Start MyVocab"),
            (os.path.join(programs, "MyVocab Setup.lnk"), "install.bat", "Change your keys or set MyVocab up again"),
            (os.path.join(programs, "MyVocab Backup.lnk"), "backup.bat", "Save a copy of your words"),
        ]
    quote = lambda text: "'" + text.replace("'", "''") + "'"  # a PowerShell string literal
    script = "".join(
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({quote(link)});"
        f"$s.TargetPath = {quote(os.path.join(ROOT, target))}; $s.WorkingDirectory = {quote(ROOT)};"
        f"$s.IconLocation = {quote(ico)}; $s.Description = {quote(tip)}; $s.Save();"
        for link, target, tip in links
    )
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("Could not make the shortcut: " + result.stderr.strip())
    print("Shortcuts: " + ", ".join(link for link, _, _ in links))


if __name__ == "__main__":
    if os.name == "nt":
        windows()
    elif sys.platform == "darwin":
        sys.exit("On macOS, drag run.sh to the Dock, or make an Automator app that runs it.")
    else:
        linux()

#!/usr/bin/env python3
"""
rdebrid - Real-Debrid CLI Downloader
Usage: rdebrid <link1> [link2] [magnet:?...] ...
       rdebrid --setup

Downloads are saved to the current working directory.
Uses aria2c for fast multi-connection downloads.
"""

import os
import subprocess
import sys
import time
import shutil
import platform

import requests

from rdebrid.config import get_token, setup_interactive

BASE = "https://api.real-debrid.com/rest/1.0"
ARIA2C_CONNECTIONS = 16


def get_headers():
    token = get_token()
    return {"Authorization": f"Bearer {token}"}


def ensure_aria2c():
    """Check for aria2c and attempt to install it if missing."""
    if shutil.which("aria2c"):
        return True

    print("aria2c not found. Attempting to install...")

    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["winget", "install", "aria2.aria2", "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("  aria2c installed via winget.")
                return True
        except FileNotFoundError:
            pass

        print("  Could not auto-install aria2c.")
        print("  Install manually: https://github.com/aria2/aria2/releases")
        print("  Or via: winget install aria2.aria2")
        print("  Or via: choco install aria2")
    elif platform.system() == "Darwin":
        print("  Install with: brew install aria2")
    else:
        print("  Install with: sudo apt install aria2  (or your package manager)")

    print("  Falling back to Python downloads.\n")
    return False


def unrestrict_link(link):
    resp = requests.post(f"{BASE}/unrestrict/link", headers=get_headers(), data={"link": link})
    resp.raise_for_status()
    return resp.json()


def download_with_aria2c(url, filename, output_dir):
    cmd = [
        "aria2c",
        "--file-allocation=none",
        f"--max-connection-per-server={ARIA2C_CONNECTIONS}",
        f"--split={ARIA2C_CONNECTIONS}",
        "--min-split-size=1M",
        "--summary-interval=0",
        f"--dir={output_dir}",
        f"--out={filename}",
        url,
    ]
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_with_requests(url, filename, output_dir):
    """Fallback if aria2c is not installed."""
    filepath = os.path.join(output_dir, filename)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    size_mb = downloaded / 1048576
                    total_mb = total / 1048576
                    filled = int(40 * downloaded // total)
                    bar = "#" * filled + "-" * (40 - filled)
                    print(f"\r  [{bar}] {pct:.1f}% ({size_mb:.1f}/{total_mb:.1f} MB)", end="", flush=True)
        print()
    return True


def download_file(url, filename, has_aria2c, output_dir="."):
    if has_aria2c:
        return download_with_aria2c(url, filename, output_dir)
    else:
        return download_with_requests(url, filename, output_dir)


def handle_magnet(magnet, has_aria2c, output_dir="."):
    headers = get_headers()

    print("Adding magnet...")
    resp = requests.post(f"{BASE}/torrents/addMagnet", headers=headers, data={"magnet": magnet})
    resp.raise_for_status()
    torrent_id = resp.json()["id"]

    resp = requests.get(f"{BASE}/torrents/info/{torrent_id}", headers=headers)
    info = resp.json()
    print(f"Torrent: {info.get('filename', 'Unknown')}")

    # Select all files
    requests.post(
        f"{BASE}/torrents/selectFiles/{torrent_id}",
        headers=headers,
        data={"files": "all"},
    )

    # Poll until ready
    while True:
        resp = requests.get(f"{BASE}/torrents/info/{torrent_id}", headers=headers)
        info = resp.json()
        status = info["status"]

        if status == "downloaded":
            break
        elif status in ("magnet_error", "error", "virus", "dead"):
            print(f"  Error: torrent status is '{status}'")
            return
        else:
            progress = info.get("progress", 0)
            speed = info.get("speed", 0)
            speed_mb = speed / 1048576 if speed else 0
            print(f"\r  Status: {status} | {progress}% | {speed_mb:.1f} MB/s", end="", flush=True)
            time.sleep(5)

    print(f"\n  Ready. {len(info['links'])} file(s) to download.\n")

    for link in info["links"]:
        try:
            result = unrestrict_link(link)
            filename = result["filename"]
            filesize_mb = result.get("filesize", 0) / 1048576
            print(f"  Downloading: {filename} ({filesize_mb:.1f} MB)")
            download_file(result["download"], filename, has_aria2c, output_dir)
        except requests.HTTPError as e:
            error_msg = e.response.json().get("error", "Unknown")
            print(f"  Failed to unrestrict: {error_msg}")


def handle_link(link, has_aria2c, output_dir="."):
    print(f"Unrestricting: {link}")
    result = unrestrict_link(link)
    filename = result["filename"]
    filesize_mb = result.get("filesize", 0) / 1048576
    print(f"  Downloading: {filename} ({filesize_mb:.1f} MB)")
    download_file(result["download"], filename, has_aria2c, output_dir)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        setup_interactive()
        return

    token = get_token()
    if not token:
        print("No API token configured. Run setup first:")
        print("  rdebrid --setup")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: rdebrid [options] <link1> [link2] [magnet:?...] ...")
        print()
        print("Options:")
        print("  --setup                   Configure your API token")
        print("  -d, --dir <path>          Download to specified directory")
        print()
        print("Examples:")
        print("  rdebrid https://filehost.com/file/abc123")
        print('  rdebrid "magnet:?xt=urn:btih:..."')
        print("  rdebrid -d ~/Downloads link1 link2")
        print()
        print("Shorthand: 'rdb' works the same as 'rdebrid'")
        sys.exit(0)

    # Parse --dir / -d flag
    args = sys.argv[1:]
    output_dir = "."

    if "-d" in args or "--dir" in args:
        flag = "-d" if "-d" in args else "--dir"
        idx = args.index(flag)
        if idx + 1 >= len(args):
            print(f"Error: {flag} requires a path argument.")
            sys.exit(1)
        output_dir = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

        os.makedirs(output_dir, exist_ok=True)

    has_aria2c = ensure_aria2c()

    magnets = [l for l in args if l.startswith("magnet:")]
    direct = [l for l in args if not l.startswith("magnet:")]

    print(f"Processing {len(direct)} link(s) and {len(magnets)} magnet(s)")
    if output_dir != ".":
        print(f"Downloading to: {os.path.abspath(output_dir)}")
    print()

    for link in direct:
        try:
            handle_link(link, has_aria2c, output_dir)
        except requests.HTTPError as e:
            error_msg = e.response.json().get("error", "Unknown")
            print(f"  API Error: {e.response.status_code} - {error_msg}")
        except Exception as e:
            print(f"  Error: {e}")
        print()

    for magnet in magnets:
        try:
            handle_magnet(magnet, has_aria2c, output_dir)
        except requests.HTTPError as e:
            error_msg = e.response.json().get("error", "Unknown")
            print(f"  API Error: {e.response.status_code} - {error_msg}")
        except Exception as e:
            print(f"  Error: {e}")
        print()

    print("Done!")


if __name__ == "__main__":
    main()

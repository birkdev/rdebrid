# rdebrid

CLI tool to download files via Real-Debrid. Unrestricts links and magnets, downloads with aria2c. Built with Claude Code.

## Install

```
pip install rdebrid
```

Or with pipx:

```
pipx install rdebrid
```

## Setup

```
rdebrid --setup
```

Enter your API token from https://real-debrid.com/apitoken

## Usage

```
rdebrid https://filehost.com/file/abc123
rdebrid link1 link2 link3
rdebrid "magnet:?xt=urn:btih:..."
```

Shorthand `rdb` also works:

```
rdb link1 link2
```

## aria2c

For fast multi-connection downloads, install [aria2](https://github.com/aria2/aria2/releases). If aria2c is not found, rdebrid will attempt to install it automatically on Windows (via winget) or fall back to Python downloads.

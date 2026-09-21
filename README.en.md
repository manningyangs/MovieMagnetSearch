# MovieMagnetSearch

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[简体中文](#) | 🌐 English

A PySide6-based desktop tool for searching torrent magnet links. Supports multi-source parallel search, automatic Chinese film title translation, and grouped episode/series display.

---

## ✨ Features

- **Multi-source parallel search**: The Pirate Bay (apibay API) · YTS · Nyaa.si · 1337x · BT BT · Dytt · Custom Jackett
- **Automatic Chinese title translation**: Wikipedia free translation (default), optional TMDB API Key for better accuracy
- **Movie / TV dual mode**: TV mode automatically groups results by S01E05, S01 Complete, etc.
- **Smart quality scoring**: Weighted ranking combining seeders, resolution, and freshness
- **Relevance filtering**: Drops irrelevant default "hot" results
- **One-click copy**: Double-click or right-click to copy magnet link / info_hash / open source page
- **Proxy support**: HTTP / SOCKS5 proxy
- **Live progress indicator**: Shows completed source count and hit count in real time
- **Ready-to-run Windows binary**: Packaged as a standalone exe

---

## 🖼️ Screenshots

(TODO — PRs welcome)

---

## 📥 Download

Grab the latest Windows 64-bit executable from **[GitHub Releases](../../releases)**.

> Users in mainland China may need a proxy to access GitHub.

---

## 🛠️ Run from Source

### Requirements

- Python 3.10+
- Windows / macOS / Linux (fully tested on Windows 11)

### Install & Run

```bash
git clone https://github.com/manningyangs/MovieMagnetSearch.git
cd MovieMagnetSearch

# Recommended: create a virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch
python main.py
```

### Build as exe (optional)

```bash
pip install pyinstaller
pyinstaller MovieMagnetSearch.spec --noconfirm
# Output: dist/MovieMagnetSearch/MovieMagnetSearch.exe
```

---

## ⚙️ Configuration

Click the **"Settings"** button at the bottom of the main window.

| Option | Description |
|---|---|
| **Search sources** | Tick sources to enable. Recommended default: The Pirate Bay + Nyaa.si |
| **Proxy** | Fill in if overseas sources are blocked, e.g. `http://127.0.0.1:7890` or `socks5://127.0.0.1:1080` |
| **Jackett** | Optional. Run Jackett locally (port 9117) to aggregate dozens of Chinese BT trackers |
| **TMDB API Key** | Optional. Get a free key at [themoviedb.org](https://www.themoviedb.org/settings/api) for better title translation |
| **Score weights** | Customize the importance of seeders / resolution / freshness |

Config is saved in `config.json` next to the executable (and is gitignored).

---

## 🏗️ Project Structure

```
movies_search/
├── main.py                 # Entry point
├── config.py               # Config management
├── MovieMagnetSearch.spec  # PyInstaller spec
├── requirements.txt
├── core/
│   ├── models.py           # TorrentResult / Resolution
│   ├── search_manager.py   # Parallel search + aggregate + score
│   ├── http_client.py      # HTTP client (requests / curl_cffi)
│   ├── scorer.py           # Quality scoring
│   ├── tmdb.py             # TMDB title translation
│   └── wikipedia.py        # Wikipedia free title translation
├── sources/                # Search sources (base + implementations)
│   ├── base.py
│   ├── piratebay.py
│   ├── yts.py
│   ├── nyaa.py
│   ├── one337x.py
│   ├── btbtt.py
│   ├── dytt.py
│   └── jackett.py
├── ui/
│   ├── main_window.py      # Main window (movie / TV dual mode)
│   ├── results_table.py    # Flat table for movie mode
│   └── settings_dialog.py  # Settings dialog
└── utils/
    ├── episode.py          # Episode title parser
    ├── relevance.py        # Relevance filter
    ├── resolution.py       # Resolution enum
    └── magnet.py           # Magnet link utilities
```

---

## 🔍 About Chinese Films

Most domestic Chinese BT search engines (BT BT, Dytt, etc.) are either down or heavily anti-scraping in 2025-2026. Among the currently working sources:

- **Chinese films with international release** (The Wandering Earth, Ne Zha, No More Bets): indexed by both The Pirate Bay and Nyaa.si
- **Films released only in mainland China** (Johnny Keep Walking, Full River Red): not indexed on international trackers

If you frequently need the latter, we recommend running [Jackett](https://github.com/Jackett/Jackett) locally (Docker one-liner), then fill in its URL and API Key in the app settings — it aggregates dozens of Chinese BT indexers.

---

## 🤝 Contributing

PRs welcome! Adding a new source only requires subclassing `SearchSource` in `sources/base.py` and implementing the `search()` method.

---

## 📄 License

[MIT License](LICENSE)

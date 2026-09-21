# MovieMagnetSearch

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[简体中文](#) | 🌐 English

A PySide6-based desktop tool for searching torrent magnet links. Supports multi-source parallel search, automatic Chinese film title translation, grouped episode/series display, and a Douban Top 250 discovery tab.

---

## ✨ Features

### 🔍 Magnet Search
- **Multi-source parallel search**: The Pirate Bay (apibay API) · YTS · Nyaa.si · 1337x · BT BT · Dytt · Custom Jackett
- **Automatic Chinese title translation**: Wikipedia free translation (default), optional TMDB API Key for better accuracy
- **Movie / TV dual mode**: TV mode automatically groups results by S01E05, S01 Complete, etc.
- **Stop button**: Abort an in-progress search at any time
- **Smart quality scoring**: Weighted ranking combining seeders, resolution, and freshness
- **Relevance filtering**: Drops irrelevant default "hot" results
- **One-click copy**: Double-click or right-click to copy magnet link / info_hash / open source page
- **Proxy support**: HTTP / SOCKS5 proxy (Douban domestic site bypasses proxy automatically)
- **Live progress indicator**: Shows completed source count and hit count in real time

### 🎬 Douban Discover (new in v0.2.0)
- **Douban Top 250**: Auto-loads on app start; cover images downloaded asynchronously with local file cache
- **Douban keyword search**: Uses the subject_suggest JSON API, returns movies + TV shows
- **Card-based browsing**: Rank / rating / directors / cast / summary at a glance
- **One-click jump to torrent search**: Click "Search Torrent" on a card — switches to the Magnet tab and launches automatically
- **Open Douban detail page**: Click "Open Douban" to open the film page in your browser
- **Zero extra dependencies**: Direct crawl of movie.douban.com, no API Key needed

### 🖥️ UI
- **Two-tab layout**: 🔍 Magnet Search + 🎬 Douban Discover — independent and clean

### 📦 Other
- **Ready-to-run Windows binary**: Packaged as a standalone exe

---

## 🖼️ Screenshots

<details>
<summary>Magnet Search</summary>

<img width="1197" height="611" alt="Magnet Search" src="https://github.com/user-attachments/assets/d2d2c875-5e1e-4817-b052-49be21409c2a" />
</details>

<details>
<summary>TV Episode Grouping</summary>

<img width="458" height="650" alt="TV Episode Grouping" src="https://github.com/user-attachments/assets/a7e9b3e7-1e67-4641-894c-825377b8f08a" />
</details>

<details>
<summary>Douban Discover (illustration)</summary>

The Douban Discover tab renders the Top 250 as cards. Each card shows rank, rating, directors, cover art, plus "Search Torrent" / "Open Douban" action buttons.
</details>

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
│   ├── search_manager.py   # Parallel search + aggregate + score + stop()
│   ├── douban.py           # Douban crawler (Top250 / search / detail)
│   ├── http_client.py      # HTTP client
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
│   ├── main_window.py      # QTabWidget two-tab main window
│   ├── douban_tab.py       # Douban Discover tab (Top250 / search / cards / cover cache)
│   ├── results_table.py    # Flat table for movie mode
│   └── settings_dialog.py  # Settings dialog
└── utils/
    ├── episode.py          # Episode title parser
    ├── relevance.py        # Relevance filter
    ├── resolution.py       # Resolution enum
    └── magnet.py           # Magnet link utilities
```

### Cached Data

Douban cover images are cached locally under `~/.movie_search/cache/covers/` for near-instant re-display on subsequent launches.

---

## 🔍 About Chinese Films

Most domestic Chinese BT search engines (BT BT, Dytt, etc.) are either down or heavily anti-scraping in 2025–2026. Among the currently working sources:

- **Chinese films with international release** (The Wandering Earth, Ne Zha, No More Bets): indexed by both The Pirate Bay and Nyaa.si
- **Films released only in mainland China** (Johnny Keep Walking, Full River Red): not indexed on international trackers

If you frequently need the latter, we recommend running [Jackett](https://github.com/Jackett/Jackett) locally (Docker one-liner), then fill in its URL and API Key in the app settings — it aggregates dozens of Chinese BT indexers.

---

## 🤝 Contributing

PRs welcome! Adding a new source only requires subclassing `SearchSource` in `sources/base.py` and implementing the `search()` method.

---

## 📄 License

[MIT License](LICENSE)

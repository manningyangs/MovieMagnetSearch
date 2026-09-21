# MovieMagnetSearch

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🌐 English | [简体中文](#)

一款基于 PySide6 的磁力链接搜索桌面工具，支持多源并发搜索、中文片名自动翻译、剧集/综艺按集分组展示。

---

## ✨ 主要特性

- **多源并发搜索**：The Pirate Bay (apibay API) · YTS · Nyaa.si · 1337x · BT之家 · 电影天堂 · 自定义 Jackett
- **中文片名自动翻译**：维基百科免费翻译（默认启用），可额外配置 TMDB API Key 获得更精确结果
- **电影 / 剧集双模式**：剧集模式下按 S01E05、S01 Complete 等自动分组展示
- **智能评分排序**：综合做种数、分辨率、发布时间加权评分
- **相关性过滤**：自动剔除无关热门默认结果
- **磁力链接一键复制**：双击或右键快速复制，也支持复制 info_hash、打开来源页面
- **代理支持**：HTTP / SOCKS5 代理
- **搜索进度提示**：实时显示已完成源数和命中条数
- **Windows 可执行文件**：打包好的 exe 直接运行，无需 Python 环境

---

## 🖼️ 截图

<img width="1197" height="611" alt="image" src="https://github.com/user-attachments/assets/d2d2c875-5e1e-4817-b052-49be21409c2a" />
<img width="458" height="650" alt="image" src="https://github.com/user-attachments/assets/a7e9b3e7-1e67-4641-894c-825377b8f08a" />



---

## 📥 下载

可执行文件请前往 **[GitHub Releases](../../releases)** 下载最新版本（Windows 64-bit）。

> 国内用户如 GitHub 下载缓慢，建议开启代理。

---

## 🛠️ 从源码运行

### 环境要求

- Python 3.10+
- Windows / macOS / Linux（已在 Windows 11 上充分测试）

### 安装与运行

```bash
# 克隆仓库
git clone https://github.com/manningyangs/MovieMagnetSearch.git
cd MovieMagnetSearch

# 建议在虚拟环境中安装
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

### 打包为 exe（可选）

```bash
# Windows
pip install pyinstaller
pyinstaller MovieMagnetSearch.spec --noconfirm
# 产物在 dist/MovieMagnetSearch/MovieMagnetSearch.exe
```

---

## ⚙️ 配置说明

点击主窗口右下角 **"设置"** 按钮：

| 配置项 | 说明 |
|---|---|
| **搜索源** | 勾选启用的搜索源。推荐默认组合：The Pirate Bay + Nyaa.si |
| **代理** | 访问国外源受阻时填写，如 `http://127.0.0.1:7890` 或 `socks5://127.0.0.1:1080` |
| **Jackett** | 可选，本地运行 Jackett（端口默认 9117）可聚合更多 BT 索引器 |
| **TMDB API Key** | 可选，在 [themoviedb.org](https://www.themoviedb.org/settings/api) 免费注册后获取，获得更精确的片名翻译 |
| **评分权重** | 自定义做种数 / 分辨率 / 发布时间的评分占比 |

配置保存在程序运行目录下的 `config.json`（不会被提交到 git）。

---

## 🏗️ 项目结构

```
movies_search/
├── main.py                 # 入口
├── config.py               # 配置管理
├── MovieMagnetSearch.spec  # PyInstaller 打包规格
├── requirements.txt
├── core/
│   ├── models.py           # TorrentResult / Resolution
│   ├── search_manager.py   # 多源并发 + 聚合 + 评分
│   ├── http_client.py      # 统一 HTTP 客户端（requests / curl_cffi）
│   ├── scorer.py           # 质量评分
│   ├── tmdb.py             # TMDB 片名翻译
│   └── wikipedia.py        # 维基百科免费片名翻译
├── sources/                # 搜索源（基类 + 实现）
│   ├── base.py
│   ├── piratebay.py
│   ├── yts.py
│   ├── nyaa.py
│   ├── one337x.py
│   ├── btbtt.py
│   ├── dytt.py
│   └── jackett.py
├── ui/
│   ├── main_window.py      # 主窗口（电影/剧集双模式）
│   ├── results_table.py    # 电影模式扁平表格
│   └── settings_dialog.py  # 设置对话框
└── utils/
    ├── episode.py          # 剧集标题解析
    ├── relevance.py        # 相关性过滤
    ├── resolution.py       # 分辨率枚举
    └── magnet.py           # 磁力链接工具
```

---

## 🔍 关于国产片的说明

近年国内 BT 磁力搜索站点（BT之家、电影天堂等）大部分已不可用或全面反爬。当前可用的搜索源中：

- **有海外发行的国产片**（流浪地球、哪吒、孤注一掷等）：国际站（The Pirate Bay + Nyaa.si）都能搜到
- **纯国内发行未出海的片**（年会不能停、满江红等）：国际站没有收录

如果经常需要搜后者，推荐在本地运行 [Jackett](https://github.com/Jackett/Jackett)（Docker 一键部署），在本程序设置里填 Jackett 地址和 API Key 即可聚合数十个中文 BT 索引器。

---

## 🤝 贡献

欢迎 PR！添加新搜索源只需继承 `sources/base.py` 里的 `SearchSource` 类并实现 `search()` 方法。

---

## 📄 许可证

[MIT License](LICENSE)

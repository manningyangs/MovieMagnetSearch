"""设置对话框：Jackett / 代理 / 源开关 / 评分权重。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig, WeightConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setMinimumWidth(460)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 搜索源
        src_box = QGroupBox("搜索源（启用/禁用）")
        src_layout = QVBoxLayout(src_box)
        self.chk_yts = QCheckBox("YTS（yts.mx API，国际电影）")
        self.chk_piratebay = QCheckBox("The Pirate Bay（apibay.org API）")
        self.chk_nyaa = QCheckBox("Nyaa.si（亚洲影视/动漫，干净 HTML 接口）")
        self.chk_1337x = QCheckBox("1337x（需 curl_cffi 绕 Cloudflare）")
        self.chk_btbtt = QCheckBox("BT之家（1lou.me，当前服务器不稳定）")
        self.chk_dytt = QCheckBox("电影天堂（dyttt.me，当前服务器不稳定）")
        for w in (self.chk_yts, self.chk_piratebay, self.chk_nyaa, self.chk_1337x, self.chk_btbtt, self.chk_dytt):
            src_layout.addWidget(w)
        layout.addWidget(src_box)

        # Jackett
        jk_box = QGroupBox("Jackett 聚合源（可选，需本地运行 Jackett）")
        jk_layout = QFormLayout(jk_box)
        self.chk_jackett = QCheckBox("启用 Jackett")
        self.jk_url = QLineEdit()
        self.jk_url.setPlaceholderText("http://127.0.0.1:9117")
        self.jk_key = QLineEdit()
        self.jk_key.setPlaceholderText("Jackett Web UI 顶部可复制的 API Key")
        jk_layout.addRow(self.chk_jackett)
        jk_layout.addRow("地址:", self.jk_url)
        jk_layout.addRow("API Key:", self.jk_key)
        layout.addWidget(jk_box)

        # 代理
        proxy_box = QGroupBox("网络代理（访问国外站或国内站需代理时填写）")
        proxy_layout = QFormLayout(proxy_box)
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("http://127.0.0.1:7890 或 socks5://127.0.0.1:1080")
        proxy_layout.addRow("代理地址:", self.proxy)
        layout.addWidget(proxy_box)

        # TMDB 片名翻译增强
        tmdb_box = QGroupBox("片名翻译增强（可选）")
        tmdb_layout = QFormLayout(tmdb_box)
        self.tmdb_key = QLineEdit()
        self.tmdb_key.setPlaceholderText("在 themoviedb.org 免费注册后获取 API Key")
        tip = QLabel(
            "默认已通过维基百科免费自动翻译中文片名，无需填写；"
            '<a href="https://www.themoviedb.org/settings/api">填写 TMDB Key</a>'
            " 可获得更精确的匹配结果"
        )
        tip.setOpenExternalLinks(True)
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666; font-size: 11px;")
        tmdb_layout.addRow("TMDB Key:", self.tmdb_key)
        tmdb_layout.addRow(tip)
        layout.addWidget(tmdb_box)

        # 评分权重
        w_box = QGroupBox("评分权重（会自动归一化）")
        w_layout = QFormLayout(w_box)
        self.sl_seeders = self._make_slider()
        self.sl_res = self._make_slider()
        self.sl_fresh = self._make_slider()
        self.lbl_seeders = QLabel("50")
        self.lbl_res = QLabel("30")
        self.lbl_fresh = QLabel("20")
        self.sl_seeders.valueChanged.connect(lambda v: self.lbl_seeders.setText(str(v)))
        self.sl_res.valueChanged.connect(lambda v: self.lbl_res.setText(str(v)))
        self.sl_fresh.valueChanged.connect(lambda v: self.lbl_fresh.setText(str(v)))
        w_layout.addRow("做种数:", self._slider_row(self.sl_seeders, self.lbl_seeders))
        w_layout.addRow("分辨率:", self._slider_row(self.sl_res, self.lbl_res))
        w_layout.addRow("新鲜度:", self._slider_row(self.sl_fresh, self.lbl_fresh))
        layout.addWidget(w_box)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_slider(self) -> QSlider:
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 100)
        s.setValue(50)
        return s

    def _slider_row(self, slider: QSlider, label: QLabel) -> QWidget:
        row = QHBoxLayout()
        row.addWidget(slider, 1)
        row.addWidget(label)
        w = QWidget()
        w.setLayout(row)
        return w

    def _load_values(self) -> None:
        c = self.config
        self.chk_yts.setChecked(c.sources.yts)
        self.chk_piratebay.setChecked(c.sources.piratebay)
        self.chk_nyaa.setChecked(c.sources.nyaa)
        self.chk_1337x.setChecked(c.sources.one337x)
        self.chk_btbtt.setChecked(c.sources.btbtt)
        self.chk_dytt.setChecked(c.sources.dytt)
        self.chk_jackett.setChecked(c.jackett.enabled)
        self.jk_url.setText(c.jackett.url)
        self.jk_key.setText(c.jackett.api_key)
        self.proxy.setText(c.proxy)
        self.tmdb_key.setText(c.tmdb_api_key)
        self.sl_seeders.setValue(int(c.weights.seeders * 100))
        self.sl_res.setValue(int(c.weights.resolution * 100))
        self.sl_fresh.setValue(int(c.weights.freshness * 100))

    def accept(self) -> None:
        c = self.config
        c.sources.yts = self.chk_yts.isChecked()
        c.sources.piratebay = self.chk_piratebay.isChecked()
        c.sources.nyaa = self.chk_nyaa.isChecked()
        c.sources.one337x = self.chk_1337x.isChecked()
        c.sources.btbtt = self.chk_btbtt.isChecked()
        c.sources.dytt = self.chk_dytt.isChecked()
        c.jackett.enabled = self.chk_jackett.isChecked()
        c.jackett.url = self.jk_url.text().strip() or "http://127.0.0.1:9117"
        c.jackett.api_key = self.jk_key.text().strip()
        c.proxy = self.proxy.text().strip()
        c.tmdb_api_key = self.tmdb_key.text().strip()
        c.weights = WeightConfig(
            seeders=self.sl_seeders.value() / 100.0,
            resolution=self.sl_res.value() / 100.0,
            freshness=self.sl_fresh.value() / 100.0,
        )
        super().accept()

from __future__ import annotations

"""Hero widget for the enhanced Media Library.

The hero widget highlights one featured media item with cover art, metadata,
ratings, and action buttons, following the Netflix-style layout described in
the design brief.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:  # Qt imports (guarded for tests)
    from PySide6.QtCore import Qt, QSize  # type: ignore
    from PySide6.QtGui import QPixmap  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QLabel,
        QPushButton,
        QHBoxLayout,
        QVBoxLayout,
        QWidget,
    )
except Exception:  # pragma: no cover - headless fallback
    Qt = QSize = QPixmap = QLabel = QPushButton = QHBoxLayout = QVBoxLayout = QWidget = object  # type: ignore


@dataclass
class HeroMedia:
    title: str
    subtitle: str
    genre: str
    duration: str
    rating: float
    cover_path: Optional[Path] = None


class HeroWidget(QWidget):  # type: ignore[misc]
    """Display a featured media item with call-to-action buttons."""

    def __init__(
        self,
        provider: Callable[[], Optional[HeroMedia]],
        *,
        play_callback: Optional[Callable[[HeroMedia], None]] = None,
        add_callback: Optional[Callable[[HeroMedia], None]] = None,
    ):  # type: ignore[override]
        super().__init__()
        self._provider = provider
        self._play_callback = play_callback
        self._add_callback = add_callback
        self._current: Optional[HeroMedia] = None

        root = QHBoxLayout(self)  # type: ignore
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(24)

        # Cover ---------------------------------------------------------
        self._cover_label = QLabel()  # type: ignore
        self._cover_label.setObjectName("HeroCover")
        self._cover_label.setFixedSize(260, 340)
        self._cover_label.setStyleSheet("background:#1f2023;border-radius:12px;")
        self._cover_label.setAlignment(Qt.AlignCenter) if hasattr(Qt, "AlignCenter") else None  # type: ignore[attr-defined]
        root.addWidget(self._cover_label)

        # Metadata ------------------------------------------------------
        meta_col = QVBoxLayout()  # type: ignore
        meta_col.setSpacing(8)

        self._title = QLabel("Titel")  # type: ignore
        self._title.setObjectName("HeroTitle")
        meta_col.addWidget(self._title)

        self._subtitle = QLabel("Untertitel")  # type: ignore
        self._subtitle.setObjectName("HeroSubtitle")
        meta_col.addWidget(self._subtitle)

        self._tags = QLabel("Genre · Dauer")  # type: ignore
        self._tags.setObjectName("HeroTags")
        meta_col.addWidget(self._tags)

        self._rating = QLabel("★★★★★")  # type: ignore
        self._rating.setObjectName("HeroRating")
        meta_col.addWidget(self._rating)

        button_row = QHBoxLayout()  # type: ignore
        button_row.setSpacing(8)

        self._play_button = QPushButton("▶️ Abspielen")  # type: ignore
        self._play_button.clicked.connect(self._on_play) if hasattr(self._play_button, "clicked") else None  # type: ignore[attr-defined]
        button_row.addWidget(self._play_button)

        self._add_button = QPushButton("➕ Zur Playlist")  # type: ignore
        self._add_button.clicked.connect(self._on_add) if hasattr(self._add_button, "clicked") else None  # type: ignore[attr-defined]
        button_row.addWidget(self._add_button)

        self._info_button = QPushButton("ℹ️ Info")  # type: ignore
        button_row.addWidget(self._info_button)

        meta_col.addLayout(button_row)
        meta_col.addStretch(1)

        root.addLayout(meta_col, stretch=1)

        self._apply_styles()
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        media = self._provider() if callable(self._provider) else None
        if not media:
            self._current = None
            self._title.setText("Keine Medien verfügbar")
            self._subtitle.setText("")
            self._tags.setText("")
            self._rating.setText("★ ☆ ☆ ☆ ☆")
            self._cover_label.setText("–")
            if hasattr(self._cover_label, "setPixmap"):
                self._cover_label.setPixmap(None)
            return
        self._current = media
        self._title.setText(media.title)
        self._subtitle.setText(media.subtitle)
        self._tags.setText(f"{media.genre} · {media.duration}")
        stars = int(round(media.rating))
        self._rating.setText("★" * stars + "☆" * (5 - stars))
        if media.cover_path and media.cover_path.exists() and QPixmap is not object:
            pix = QPixmap(str(media.cover_path))  # type: ignore
            if hasattr(pix, "isNull") and pix.isNull():
                self._cover_label.setText(media.title)
            else:
                scaled = pix.scaled(260, 340, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)  # type: ignore[attr-defined]
                self._cover_label.setPixmap(scaled)
                self._cover_label.setText("")
        else:
            self._cover_label.setText("🎬")

    # ------------------------------------------------------------------
    def _on_play(self) -> None:
        if self._current and callable(self._play_callback):
            self._play_callback(self._current)

    def _on_add(self) -> None:
        if self._current and callable(self._add_callback):
            self._add_callback(self._current)

    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        self.setStyleSheet(
            "#HeroTitle{font-size:28px;font-weight:700;color:#fff;}"
            "#HeroSubtitle{font-size:16px;color:#cfd2d8;}"
            "#HeroTags{font-size:14px;color:#9ea3a8;}"
            "#HeroRating{font-size:20px;color:#ffb347;}"
            "QPushButton{background:#5865f2;border:1px solid #4752c4;color:#fff;"
            "padding:8px 14px;border-radius:6px;}"
            "QPushButton:hover{background:#4752c4;border-color:#3c45a0;}"
        )


__all__ = ["HeroWidget", "HeroMedia"]

"""Real-time spectrum analyzer widget using FFT visualization."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QTimer  # type: ignore[import-not-found]
from PySide6.QtGui import QColor, QPainter, QPen  # type: ignore[import-not-found]
from PySide6.QtWidgets import QWidget  # type: ignore[import-not-found]

if TYPE_CHECKING:
    pass

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - missing runtime dependency
    np = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import sounddevice as sd  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - missing runtime dependency
    sd = None  # type: ignore[assignment]


class SpectrumAnalyzerWidget(QWidget):
    """Real-time FFT-based spectrum analyzer visualization."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setMaximumHeight(200)
        
        # Frequency bands matching the 10-band EQ
        self._bands = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
        self._magnitudes = [0.0] * len(self._bands)
        
        # Audio capture state
        self._stream = None
        self._active = False
        self._device_id: Optional[int] = None
        
        # Visualization settings
        self._smoothing = 0.7  # Smoothing factor for visual stability
        
        # Update timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_display)
        self._timer.setInterval(50)  # 20 FPS
        
        # Set dark background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(30, 30, 30))
        self.setPalette(palette)
    
    def start(self, device_id: Optional[int] = None) -> None:
        """Start capturing and analyzing audio."""
        if sd is None or np is None:
            return
        
        self._device_id = device_id
        self._active = True
        
        try:
            # Start audio input stream
            self._stream = sd.InputStream(
                device=self._device_id,
                channels=1,
                samplerate=44100,
                blocksize=2048,
                callback=self._audio_callback
            )
            self._stream.start()
            self._timer.start()
        except Exception:
            self._active = False
            self._stream = None
    
    def stop(self) -> None:
        """Stop capturing and analyzing audio."""
        self._active = False
        self._timer.stop()
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            finally:
                self._stream = None
        
        # Reset magnitudes
        self._magnitudes = [0.0] * len(self._bands)
        self.update()
    
    def is_active(self) -> bool:
        """Check if analyzer is currently active."""
        return self._active
    
    def _audio_callback(self, indata, frames, time, status) -> None:  # type: ignore[no-untyped-def]
        """Process incoming audio data with FFT analysis."""
        if not self._active or np is None:
            return
        
        try:
            # Get mono audio data
            audio = indata[:, 0] if indata.ndim > 1 else indata
            
            # Perform FFT
            fft = np.fft.rfft(audio)
            magnitude = np.abs(fft)
            
            # Sample rate and frequency bins
            samplerate = 44100
            freqs = np.fft.rfftfreq(len(audio), 1 / samplerate)
            
            # Calculate magnitude for each band
            new_mags = []
            for band_freq in self._bands:
                # Find frequencies within band range (±half octave)
                low = band_freq / 1.4142
                high = band_freq * 1.4142
                mask = (freqs >= low) & (freqs <= high)
                
                # Average magnitude in this band
                if mask.any():
                    avg_mag = float(np.mean(magnitude[mask]))
                    # Normalize to 0-1 range with log scale
                    normalized = min(1.0, np.log10(avg_mag + 1) / 3.0)
                    new_mags.append(normalized)
                else:
                    new_mags.append(0.0)
            
            # Apply smoothing for visual stability
            for i in range(len(self._bands)):
                self._magnitudes[i] = (
                    self._smoothing * self._magnitudes[i] + 
                    (1 - self._smoothing) * new_mags[i]
                )
        except Exception:
            # Ignore errors during processing
            pass
    
    def _update_display(self) -> None:
        """Trigger repaint of visualization."""
        self.update()
    
    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """Paint the spectrum bars."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background
        painter.fillRect(0, 0, width, height, QColor(30, 30, 30))
        
        # Calculate bar dimensions
        bar_count = len(self._bands)
        bar_spacing = 4
        total_spacing = bar_spacing * (bar_count - 1)
        bar_width = (width - total_spacing) // bar_count
        
        # Draw frequency bars
        for i, magnitude in enumerate(self._magnitudes):
            x = i * (bar_width + bar_spacing)
            bar_height = int(magnitude * (height - 20))
            y = height - bar_height
            
            # Color gradient based on magnitude
            if magnitude > 0.8:
                color = QColor(255, 80, 80)  # Red for high levels
            elif magnitude > 0.5:
                color = QColor(255, 200, 0)  # Yellow/orange for medium
            else:
                color = QColor(80, 200, 80)  # Green for low levels
            
            painter.fillRect(x, y, bar_width, bar_height, color)
            
            # Frequency label at bottom
            painter.setPen(QPen(QColor(150, 150, 150)))
            freq_label = str(self._bands[i])
            if self._bands[i] >= 1000:
                freq_label = f"{self._bands[i] // 1000}k"
            painter.drawText(x, height - 5, bar_width, 15, 
                           Qt.AlignmentFlag.AlignCenter, freq_label)
        
        painter.end()

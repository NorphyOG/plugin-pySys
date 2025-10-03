"""
Real-time audio equalizer engine using scipy.signal for DSP.

This module implements a 10-band parametric equalizer that can be applied
to audio streams in real-time via sounddevice callbacks.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy import signal


@dataclass
class BandConfig:
    """Configuration for a single EQ band."""
    frequency: int  # Center frequency in Hz
    gain_db: float  # Gain in decibels (-12 to +12)
    q_factor: float = 1.0  # Q factor (bandwidth), typically 0.5-2.0


class EqualizerEngine:
    """
    Real-time 10-band parametric equalizer using IIR filters.
    
    This engine processes audio in real-time by applying a chain of
    peaking filters (one per frequency band) with configurable gains.
    """
    
    # Standard 10-band EQ frequencies (Hz)
    BANDS: Tuple[int, ...] = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
    
    def __init__(self, sample_rate: int = 48000, channels: int = 2) -> None:
        """
        Initialize the equalizer engine.
        
        Args:
            sample_rate: Audio sample rate in Hz (default 48000)
            channels: Number of audio channels (default 2 for stereo)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self._enabled = False
        self._lock = threading.Lock()
        
        # Initialize band gains to 0 dB (flat response)
        self._gains: List[float] = [0.0] * len(self.BANDS)
        
        # Pre-compute filter coefficients for each band
        self._filters: List[Tuple[np.ndarray, np.ndarray]] = []
        self._update_filters()
        
        # Filter states for each channel and band (for continuity between blocks)
        # Shape: [channels][bands][filter_order]
        self._reset_states()
    
    def _update_filters(self) -> None:
        """Recompute IIR filter coefficients based on current gains."""
        self._filters = []
        for i, freq in enumerate(self.BANDS):
            gain_db = self._gains[i]
            if abs(gain_db) < 0.01:  # Flat response, use pass-through
                # Identity filter: y[n] = x[n]
                b = np.array([1.0])
                a = np.array([1.0])
            else:
                # Design a peaking (parametric) EQ filter
                # Q=1.0 gives ~1 octave bandwidth
                b, a = self._design_peaking_filter(freq, gain_db, q=1.0)
            self._filters.append((b, a))
    
    def _design_peaking_filter(
        self,
        center_freq: float,
        gain_db: float,
        q: float = 1.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Design a peaking (parametric) EQ filter using scipy.signal.
        
        Args:
            center_freq: Center frequency in Hz
            gain_db: Gain in decibels
            q: Q factor (bandwidth)
        
        Returns:
            Tuple of (b, a) filter coefficients
        """
        # Normalize frequency to Nyquist
        nyquist = self.sample_rate / 2.0
        w0 = center_freq / nyquist
        
        # Clamp to valid range (avoid instability)
        w0 = np.clip(w0, 0.01, 0.99)
        
        # Convert gain from dB to linear
        A = 10 ** (gain_db / 40.0)  # sqrt of power ratio
        
        # Bandwidth (BW) in octaves: BW = w0 / Q
        # For peaking filters, we use the shelf filter formula
        # which scipy doesn't have directly, so we use iirpeak/iirnotch analog
        
        # Alternative: use second-order sections (SOS) design
        # For simplicity, we'll use a biquad peaking filter formula
        alpha = np.sin(w0 * np.pi) / (2 * q)
        
        if gain_db >= 0:  # Boost
            b0 = 1 + alpha * A
            b1 = -2 * np.cos(w0 * np.pi)
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * np.cos(w0 * np.pi)
            a2 = 1 - alpha / A
        else:  # Cut
            b0 = 1 + alpha / A
            b1 = -2 * np.cos(w0 * np.pi)
            b2 = 1 - alpha / A
            a0 = 1 + alpha * A
            a1 = -2 * np.cos(w0 * np.pi)
            a2 = 1 - alpha * A
        
        # Normalize by a0
        b = np.array([b0 / a0, b1 / a0, b2 / a0])
        a = np.array([1.0, a1 / a0, a2 / a0])
        
        return b, a
    
    def _reset_states(self) -> None:
        """Reset filter states (used when starting or changing configuration)."""
        # For each channel and band, initialize filter state to zeros
        # State size depends on max(len(b), len(a)) - 1
        max_order = max(3, 3)  # Biquad filters are order 2 (3 coefficients)
        self._states = [
            [np.zeros(max_order - 1) for _ in range(len(self.BANDS))]
            for _ in range(self.channels)
        ]
    
    def set_gains(self, gains: List[float]) -> None:
        """
        Update EQ band gains.
        
        Args:
            gains: List of 10 gain values in dB (-12 to +12)
        """
        with self._lock:
            if len(gains) != len(self.BANDS):
                raise ValueError(f"Expected {len(self.BANDS)} gains, got {len(gains)}")
            
            # Clamp gains to valid range
            self._gains = [np.clip(g, -12.0, 12.0) for g in gains]
            self._update_filters()
            # Don't reset states to avoid clicks/pops during live adjustment
    
    def get_gains(self) -> List[float]:
        """Get current EQ band gains."""
        with self._lock:
            return list(self._gains)
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the equalizer."""
        with self._lock:
            if enabled and not self._enabled:
                # Reset states when enabling to avoid discontinuities
                self._reset_states()
            self._enabled = enabled
    
    def is_enabled(self) -> bool:
        """Check if the equalizer is enabled."""
        with self._lock:
            return self._enabled
    
    def process(self, audio_block: np.ndarray) -> np.ndarray:
        """
        Process an audio block through the equalizer.
        
        Args:
            audio_block: Input audio array with shape (frames, channels)
        
        Returns:
            Processed audio array with same shape
        """
        with self._lock:
            if not self._enabled:
                # Pass through unmodified
                return audio_block
            
            # Ensure input is float32 for processing
            audio = audio_block.astype(np.float32)
            
            # Process each channel separately
            for ch in range(min(self.channels, audio.shape[1])):
                channel_data = audio[:, ch]
                
                # Apply each band filter sequentially
                for band_idx, (b, a) in enumerate(self._filters):
                    if len(b) == 1 and len(a) == 1:
                        # Pass-through filter, skip
                        continue
                    
                    # Apply IIR filter with state preservation
                    filtered, self._states[ch][band_idx] = signal.lfilter(
                        b, a, channel_data,
                        zi=self._states[ch][band_idx]
                    )
                    channel_data = filtered
                
                audio[:, ch] = channel_data
            
            # Prevent clipping by soft-limiting
            audio = np.clip(audio, -1.0, 1.0)
            
            return audio


class EqualizerStream:
    """
    High-level interface for real-time equalization via sounddevice.
    
    This class manages the sounddevice stream and applies the equalizer
    to audio passing through it.
    """
    
    def __init__(
        self,
        input_device: Optional[int] = None,
        output_device: Optional[int] = None,
        sample_rate: int = 48000,
        block_size: int = 512,
        channels: int = 2,
    ) -> None:
        """
        Initialize the equalizer stream.
        
        Args:
            input_device: Input device ID (None for default)
            output_device: Output device ID (None for default)
            sample_rate: Sample rate in Hz
            block_size: Audio block size (lower = less latency, more CPU)
            channels: Number of channels
        """
        self.input_device = input_device
        self.output_device = output_device
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels
        
        self.engine = EqualizerEngine(sample_rate, channels)
        self._stream: Optional[object] = None  # sounddevice.Stream
        self._running = False
    
    def start(self) -> None:
        """Start the real-time equalizer stream."""
        if self._running:
            return
        
        # Lazy import to avoid dependency issues
        try:
            import sounddevice as sd
        except ImportError:
            raise RuntimeError("sounddevice not available")
        
        def callback(indata: np.ndarray, outdata: np.ndarray, frames: int, time, status) -> None:
            """Audio callback for processing."""
            if status:
                print(f"Stream status: {status}")
            
            # Process input through equalizer
            processed = self.engine.process(indata.copy())
            outdata[:] = processed
        
        self._stream = sd.Stream(
            device=(self.input_device, self.output_device),
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            channels=self.channels,
            callback=callback,
        )
        self._stream.start()
        self._running = True
    
    def stop(self) -> None:
        """Stop the real-time equalizer stream."""
        if not self._running or not self._stream:
            return
        
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._running = False
    
    def is_running(self) -> bool:
        """Check if the stream is running."""
        return self._running

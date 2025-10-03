"""Tests for the AudioTools equalizer engine."""
import numpy as np
import pytest

from mmst.plugins.audio_tools.equalizer import BandConfig, EqualizerEngine


class TestEqualizerEngine:
    """Test the real-time equalizer engine."""

    def test_engine_initialization(self):
        """Test engine initialization with default parameters."""
        engine = EqualizerEngine()
        assert engine.sample_rate == 48000
        assert engine.channels == 2
        assert not engine.is_enabled()
        assert len(engine.get_gains()) == 10
        assert all(g == 0.0 for g in engine.get_gains())

    def test_engine_custom_parameters(self):
        """Test engine initialization with custom parameters."""
        engine = EqualizerEngine(sample_rate=44100, channels=1)
        assert engine.sample_rate == 44100
        assert engine.channels == 1

    def test_set_gains(self):
        """Test setting EQ band gains."""
        engine = EqualizerEngine()
        
        # Set gains
        test_gains = [1.0, 2.0, 3.0, 4.0, 5.0, -1.0, -2.0, -3.0, -4.0, -5.0]
        engine.set_gains(test_gains)
        
        retrieved_gains = engine.get_gains()
        assert len(retrieved_gains) == 10
        for actual, expected in zip(retrieved_gains, test_gains):
            assert abs(actual - expected) < 0.01

    def test_set_gains_clamping(self):
        """Test that gains are clamped to valid range."""
        engine = EqualizerEngine()
        
        # Try to set gains outside valid range
        test_gains = [15.0, -15.0, 0.0, 12.0, -12.0, 20.0, -20.0, 5.0, -5.0, 0.0]
        engine.set_gains(test_gains)
        
        retrieved_gains = engine.get_gains()
        for gain in retrieved_gains:
            assert -12.0 <= gain <= 12.0

    def test_set_gains_wrong_count(self):
        """Test error when setting wrong number of gains."""
        engine = EqualizerEngine()
        
        with pytest.raises(ValueError, match="Expected 10 gains"):
            engine.set_gains([0.0, 1.0, 2.0])  # Only 3 gains

    def test_enable_disable(self):
        """Test enabling and disabling the engine."""
        engine = EqualizerEngine()
        
        assert not engine.is_enabled()
        
        engine.set_enabled(True)
        assert engine.is_enabled()
        
        engine.set_enabled(False)
        assert not engine.is_enabled()

    def test_process_passthrough_disabled(self):
        """Test that audio passes through unmodified when disabled."""
        engine = EqualizerEngine(channels=2)
        engine.set_enabled(False)
        
        # Create test audio (sine wave)
        frames = 1024
        t = np.linspace(0, 1, frames)
        input_audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t),  # 440 Hz
            np.sin(2 * np.pi * 880 * t),  # 880 Hz
        ]).astype(np.float32)
        
        output_audio = engine.process(input_audio)
        
        # Should be identical when disabled
        np.testing.assert_array_almost_equal(input_audio, output_audio, decimal=5)

    def test_process_with_eq_enabled(self):
        """Test that audio is modified when EQ is enabled with gains."""
        engine = EqualizerEngine(channels=2)
        
        # Set some gains
        gains = [3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # Boost 31 Hz
        engine.set_gains(gains)
        engine.set_enabled(True)
        
        # Create test audio
        frames = 1024
        t = np.linspace(0, 1, frames)
        input_audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t),  # 440 Hz
            np.sin(2 * np.pi * 880 * t),  # 880 Hz
        ]).astype(np.float32)
        
        output_audio = engine.process(input_audio)
        
        # Output should be different from input
        assert output_audio.shape == input_audio.shape
        # Since we're filtering, they shouldn't be identical
        diff = np.sum(np.abs(output_audio - input_audio))
        assert diff > 0  # Some difference should exist

    def test_process_clipping_prevention(self):
        """Test that output is clipped to prevent overflow."""
        engine = EqualizerEngine(channels=1)
        
        # Set high gains across all bands
        gains = [12.0] * 10
        engine.set_gains(gains)
        engine.set_enabled(True)
        
        # Create loud test audio
        frames = 1024
        t = np.linspace(0, 1, frames)
        input_audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t) * 0.9,  # High amplitude
        ]).astype(np.float32)
        
        output_audio = engine.process(input_audio)
        
        # Output should be clipped to [-1, 1]
        assert np.all(output_audio >= -1.0)
        assert np.all(output_audio <= 1.0)

    def test_process_stereo(self):
        """Test processing stereo audio."""
        engine = EqualizerEngine(channels=2)
        engine.set_gains([2.0] * 10)
        engine.set_enabled(True)
        
        # Create stereo test audio
        frames = 512
        t = np.linspace(0, 1, frames)
        input_audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t),  # Left channel
            np.sin(2 * np.pi * 880 * t),  # Right channel
        ]).astype(np.float32)
        
        output_audio = engine.process(input_audio)
        
        assert output_audio.shape == (frames, 2)

    def test_process_flat_eq(self):
        """Test that flat EQ (all 0 dB) minimally affects audio."""
        engine = EqualizerEngine(channels=1)
        
        # Flat EQ
        gains = [0.0] * 10
        engine.set_gains(gains)
        engine.set_enabled(True)
        
        # Create test audio
        frames = 1024
        t = np.linspace(0, 1, frames)
        input_audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t),
        ]).astype(np.float32)
        
        output_audio = engine.process(input_audio)
        
        # With flat EQ, output should be very close to input
        # Allow small differences due to numerical precision
        np.testing.assert_array_almost_equal(input_audio, output_audio, decimal=3)

    def test_filter_design(self):
        """Test that filter design produces valid coefficients."""
        engine = EqualizerEngine()
        
        # Set some gains to trigger filter design
        gains = [6.0, -6.0, 3.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        engine.set_gains(gains)
        
        # Check that filters were created
        assert len(engine._filters) == 10
        
        for b, a in engine._filters:
            # Coefficients should be finite
            assert np.all(np.isfinite(b))
            assert np.all(np.isfinite(a))
            # First element of 'a' should be 1.0 (normalized)
            assert abs(a[0] - 1.0) < 0.01

    def test_state_preservation(self):
        """Test that filter states are preserved between blocks."""
        engine = EqualizerEngine(channels=1)
        engine.set_gains([3.0] * 10)
        engine.set_enabled(True)
        
        # Process multiple blocks
        frames = 256
        for _ in range(3):
            t = np.linspace(0, 1, frames)
            audio_block = np.column_stack([
                np.sin(2 * np.pi * 440 * t),
            ]).astype(np.float32)
            
            output = engine.process(audio_block)
            
            # Should process without errors
            assert output.shape == (frames, 1)
            assert np.all(np.isfinite(output))


class TestBandConfig:
    """Test the BandConfig dataclass."""

    def test_band_config_creation(self):
        """Test creating a band configuration."""
        band = BandConfig(frequency=1000, gain_db=3.5)
        assert band.frequency == 1000
        assert band.gain_db == 3.5
        assert band.q_factor == 1.0  # Default

    def test_band_config_custom_q(self):
        """Test creating a band with custom Q factor."""
        band = BandConfig(frequency=500, gain_db=-6.0, q_factor=2.0)
        assert band.frequency == 500
        assert band.gain_db == -6.0
        assert band.q_factor == 2.0

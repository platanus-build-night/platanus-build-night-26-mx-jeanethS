"""
Unit tests for the procedural audio engine.

Covers buffer generation, ADSR envelope, tremolo, sub-bass, crossfading,
volume limits, and pygame mixer initialization.
"""

import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

# Inject a mock pygame module before importing audio (pygame may not be installed)
_mock_pygame = MagicMock()
sys.modules["pygame"] = _mock_pygame

import audio as audio_module
from config import CHORDS, VOLUME, CROSSFADE_SECONDS


class TestPygameInitialization(unittest.TestCase):
    """(1) Verify pygame.mixer is initialized correctly."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_mixer_pre_init_and_init_called(self):
        engine = audio_module.AudioEngine()
        _mock_pygame.mixer.pre_init.assert_called_once_with(
            frequency=44100, size=-16, channels=2, buffer=1024
        )
        _mock_pygame.mixer.init.assert_called_once()

    def test_custom_sample_rate(self):
        _mock_pygame.mixer.reset_mock()
        engine = audio_module.AudioEngine(sample_rate=48000, buffer_size=512)
        _mock_pygame.mixer.pre_init.assert_called_once_with(
            frequency=48000, size=-16, channels=2, buffer=512
        )
        _mock_pygame.mixer.init.assert_called_once()


class TestSineWaveGeneration(unittest.TestCase):
    """(2) Verify numpy sine wave generation produces clean buffers."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_buffer_shape_and_dtype(self):
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer([440.0], duration=0.5)
        expected_samples = int(0.5 * engine.sample_rate)
        self.assertEqual(buffer.shape, (expected_samples, 2))
        self.assertEqual(buffer.dtype, np.int16)

    def test_buffer_finite(self):
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer([440.0, 554.37], duration=1.0)
        self.assertTrue(np.all(np.isfinite(buffer)))

    def test_buffer_not_silent(self):
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer([440.0], duration=1.0)
        self.assertGreater(np.max(np.abs(buffer)), 0)

    def test_multiple_frequencies(self):
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer(CHORDS["flow"], duration=1.0)
        self.assertGreater(np.max(np.abs(buffer)), 0)

    def test_empty_chord_is_silent(self):
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer([], duration=1.0)
        self.assertTrue(np.all(buffer == 0))


class TestADSR(unittest.TestCase):
    """(3) Test ADSR envelope: attack 0.3s, decay 0.2s, sustain 0.8, release 0.5s."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_envelope_length(self):
        engine = audio_module.AudioEngine()
        samples = int(3.0 * engine.sample_rate)
        env = engine._create_adsr_envelope(samples)
        self.assertEqual(len(env), samples)

    def test_attack_rise(self):
        engine = audio_module.AudioEngine()
        samples = int(3.0 * engine.sample_rate)
        env = engine._create_adsr_envelope(samples)
        attack_samples = int(engine.attack_time * engine.sample_rate)
        self.assertAlmostEqual(env[0], 0.0, places=5)
        self.assertAlmostEqual(env[attack_samples - 1], 1.0, places=5)
        # Monotonic increase
        self.assertTrue(np.all(np.diff(env[:attack_samples]) >= -1e-12))

    def test_decay_fall(self):
        engine = audio_module.AudioEngine()
        samples = int(3.0 * engine.sample_rate)
        env = engine._create_adsr_envelope(samples)
        attack_samples = int(engine.attack_time * engine.sample_rate)
        decay_samples = int(engine.decay_time * engine.sample_rate)
        decay_start = attack_samples
        decay_end = attack_samples + decay_samples
        self.assertAlmostEqual(env[decay_start], 1.0, places=5)
        self.assertAlmostEqual(env[decay_end - 1], engine.sustain_level, places=5)
        self.assertTrue(np.all(np.diff(env[decay_start:decay_end]) <= 1e-12))

    def test_sustain_plateau(self):
        engine = audio_module.AudioEngine()
        samples = int(3.0 * engine.sample_rate)
        env = engine._create_adsr_envelope(samples)
        attack_samples = int(engine.attack_time * engine.sample_rate)
        decay_samples = int(engine.decay_time * engine.sample_rate)
        release_samples = int(engine.release_time * engine.sample_rate)
        sustain_start = attack_samples + decay_samples
        sustain_end = samples - release_samples
        self.assertTrue(sustain_start < sustain_end)
        self.assertTrue(np.all(env[sustain_start:sustain_end] == engine.sustain_level))

    def test_release_fall(self):
        engine = audio_module.AudioEngine()
        samples = int(3.0 * engine.sample_rate)
        env = engine._create_adsr_envelope(samples)
        release_samples = int(engine.release_time * engine.sample_rate)
        self.assertAlmostEqual(env[-release_samples], engine.sustain_level, places=5)
        self.assertAlmostEqual(env[-1], 0.0, places=5)
        self.assertTrue(np.all(np.diff(env[-release_samples:]) <= 1e-12))

    def test_full_range(self):
        engine = audio_module.AudioEngine()
        samples = int(3.0 * engine.sample_rate)
        env = engine._create_adsr_envelope(samples)
        self.assertGreaterEqual(np.min(env), 0.0)
        self.assertLessEqual(np.max(env), 1.0)


class TestTremolo(unittest.TestCase):
    """(4) Test tremolo LFO at 0.5 Hz with depth 0.05."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_tremolo_array_properties(self):
        engine = audio_module.AudioEngine()
        duration = 2.0
        samples = int(duration * engine.sample_rate)
        time_array = np.linspace(0, duration, samples, False)
        tremolo = engine._create_tremolo(time_array)
        self.assertEqual(len(tremolo), samples)
        expected_min = 1.0 - engine.tremolo_depth
        expected_max = 1.0 + engine.tremolo_depth
        self.assertAlmostEqual(np.min(tremolo), expected_min, places=5)
        self.assertAlmostEqual(np.max(tremolo), expected_max, places=5)

    def test_tremolo_frequency(self):
        engine = audio_module.AudioEngine()
        duration = 4.0
        samples = int(duration * engine.sample_rate)
        time_array = np.linspace(0, duration, samples, False)
        tremolo = engine._create_tremolo(time_array)
        # Zero-mean to remove DC before FFT
        centered = tremolo - np.mean(tremolo)
        fft = np.fft.rfft(centered)
        freqs = np.fft.rfftfreq(len(centered), d=1.0 / engine.sample_rate)
        peak_idx = np.argmax(np.abs(fft[1:])) + 1  # skip DC
        self.assertAlmostEqual(freqs[peak_idx], engine.tremolo_freq, delta=0.1)

    def test_tremolo_applied_to_buffer(self):
        engine = audio_module.AudioEngine()
        # Flatten ADSR to isolate tremolo effect
        engine._create_adsr_envelope = lambda s: np.ones(s)
        buffer = engine.generate_chord_buffer([440.0], duration=2.0)
        float_buf = buffer[:, 0].astype(np.float64) / 32767.0
        # Moving-average envelope detection
        window = int(0.02 * engine.sample_rate)  # 20 ms
        envelope = np.convolve(np.abs(float_buf), np.ones(window) / window, mode="valid")
        # Tremolo at 0.5 Hz should create clear variation in the envelope
        self.assertGreater(np.std(envelope), 0.001)


class TestSubBass(unittest.TestCase):
    """(5) Test sub-bass generation at root/2 for warmth."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_sub_bass_frequency_present(self):
        engine = audio_module.AudioEngine()
        root = 440.0
        buffer = engine.generate_chord_buffer([root], duration=1.0)
        samples = buffer.shape[0]
        spectrum = np.abs(np.fft.rfft(buffer[:, 0].astype(np.float64)))
        freqs = np.fft.rfftfreq(samples, d=1.0 / engine.sample_rate)
        idx_root = np.argmin(np.abs(freqs - root))
        idx_sub = np.argmin(np.abs(freqs - (root / 2)))
        mag_root = spectrum[idx_root]
        mag_sub = spectrum[idx_sub]
        self.assertGreater(mag_sub, mag_root * 0.05)
        self.assertGreater(mag_sub, 100.0)


class TestCrossfading(unittest.TestCase):
    """(6) Test crossfading between two different state chords."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()
        _mock_pygame.mixer.Sound.side_effect = None
        _mock_pygame.mixer.Sound.return_value = None

        self.sleep_patch = patch("audio.time.sleep")
        self.mock_sleep = self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)

        # Speed up crossfade so tests don't wait
        self.crossfade_patch = patch.object(audio_module, "CROSSFADE_SECONDS", 0.01)
        self.crossfade_patch.start()
        self.addCleanup(self.crossfade_patch.stop)

    def test_crossfade_volume_progression(self):
        engine = audio_module.AudioEngine()
        mock_sound1 = MagicMock()
        mock_sound2 = MagicMock()
        _mock_pygame.mixer.Sound.side_effect = [mock_sound1, mock_sound2]

        engine.play_state("flow")
        self.assertEqual(engine.current_state, "flow")
        mock_sound1.play.assert_called_once_with(-1)
        self.assertTrue(engine.is_playing)

        engine.play_state("stuck")
        if engine.crossfade_thread:
            engine.crossfade_thread.join(timeout=2.0)

        # Verify old sound volumes decrease
        old_volumes = [call.args[0] for call in mock_sound1.set_volume.call_args_list]
        self.assertGreater(len(old_volumes), 0)
        self.assertAlmostEqual(old_volumes[0], VOLUME, places=5)
        self.assertAlmostEqual(old_volumes[-1], 0.0, places=5)

        # Verify new sound volumes increase
        new_volumes = [call.args[0] for call in mock_sound2.set_volume.call_args_list]
        self.assertGreater(len(new_volumes), 0)
        self.assertAlmostEqual(new_volumes[0], 0.0, places=5)
        self.assertAlmostEqual(new_volumes[-1], VOLUME, places=5)

        mock_sound1.stop.assert_called_once()
        self.assertEqual(engine.current_sound, mock_sound2)

    def test_no_crossfade_when_state_unchanged(self):
        engine = audio_module.AudioEngine()
        mock_sound = MagicMock()
        _mock_pygame.mixer.Sound.return_value = mock_sound

        engine.play_state("debugging")
        self.assertEqual(engine.current_state, "debugging")
        play_calls = mock_sound.play.call_count

        engine.play_state("debugging")
        self.assertEqual(mock_sound.play.call_count, play_calls)
        self.assertEqual(engine.current_state, "debugging")

    def test_crossfade_starts_new_sound_on_loop(self):
        engine = audio_module.AudioEngine()
        mock_sound1 = MagicMock()
        mock_sound2 = MagicMock()
        _mock_pygame.mixer.Sound.side_effect = [mock_sound1, mock_sound2]

        engine.play_state("reviewing")
        engine.play_state("context_switching")
        if engine.crossfade_thread:
            engine.crossfade_thread.join(timeout=2.0)

        mock_sound2.play.assert_called_once_with(-1)


class TestVolumeAndClipping(unittest.TestCase):
    """(7) Verify volume stays at max 0.35 and doesn't cause clipping."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_max_volume_within_limit(self):
        engine = audio_module.AudioEngine()
        for state, freqs in CHORDS.items():
            buffer = engine.generate_chord_buffer(freqs, duration=1.0)
            float_buf = buffer.astype(np.float64) / 32767.0
            max_amp = np.max(np.abs(float_buf))
            self.assertLessEqual(
                max_amp, VOLUME + 1e-6, f"State '{state}' exceeds max volume"
            )

    def test_no_integer_clipping(self):
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer(CHORDS["flow"], duration=3.0)
        self.assertEqual(buffer.dtype, np.int16)
        self.assertGreaterEqual(np.min(buffer), -32768)
        self.assertLessEqual(np.max(buffer), 32767)

    def test_volume_headroom(self):
        """After normalization the peak should be close to VOLUME * 32767."""
        engine = audio_module.AudioEngine()
        buffer = engine.generate_chord_buffer([261.63, 329.63, 392.00], duration=2.0)
        max_val = np.max(np.abs(buffer))
        expected_max = int(VOLUME * 32767)
        # Allow off-by-one due to rounding
        self.assertLessEqual(max_val, expected_max + 1)


class TestAudioEngineLifecycle(unittest.TestCase):
    """Miscellaneous lifecycle tests."""

    def setUp(self):
        _mock_pygame.reset_mock()
        _mock_pygame.mixer.reset_mock()

    def test_stop(self):
        engine = audio_module.AudioEngine()
        mock_sound = MagicMock()
        _mock_pygame.mixer.Sound.return_value = mock_sound
        engine.play_state("flow")
        engine.stop()
        mock_sound.stop.assert_called_once()
        self.assertFalse(engine.is_playing)

    def test_cleanup(self):
        engine = audio_module.AudioEngine()
        engine.cleanup()
        _mock_pygame.mixer.stop.assert_called_once()
        _mock_pygame.mixer.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)

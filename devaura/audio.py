"""
Procedural Audio Engine for DevAura

Generates ambient music based on cognitive states using pure Python synthesis.
Features smooth transitions, layered oscillators, harmonic overtones,
soft rhythmic pulse, stereo panning, pad-style envelopes, and crossfading.
"""

import threading
import time
from typing import List, Optional
from config import CHORDS, VOLUME, CROSSFADE_SECONDS

# Handle optional audio dependencies gracefully
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore

_AUDIO_AVAILABLE = np is not None and pygame is not None

if _AUDIO_AVAILABLE:
    class AudioEngine:
        def __init__(self, sample_rate: int = 44100, buffer_size: int = 1024):
            self.sample_rate = sample_rate
            self.buffer_size = buffer_size
            self.current_state = None
            self.current_sound = None
            self.is_playing = False
            self.crossfade_thread = None

            # Legacy ADSR parameters (kept for backward compatibility / tests)
            self.attack_time = 0.3
            self.decay_time = 0.2
            self.sustain_level = 0.8
            self.release_time = 0.5
            self.tremolo_freq = 0.5
            self.tremolo_depth = 0.05

            # Pad-style ADSR for ambient sound
            self.pad_attack_time = 1.5
            self.pad_decay_time = 0.5
            self.pad_sustain_level = 0.7
            self.pad_release_time = 2.0

            # Stereo panning LFO
            self.pan_lfo_freq = 0.15
            self.pan_lfo_depth = 0.3

            # Soft rhythmic pulse
            self.kick_volume = 0.12
            self.beat_bpm = 60.0

            # Arpeggiator option
            self.arpeggiator = False
            self.arpeggiator_speed = 0.4

            # Initialize pygame mixer
            pygame.mixer.pre_init(
                frequency=self.sample_rate,
                size=-16,
                channels=2,
                buffer=self.buffer_size
            )
            pygame.mixer.init()

        def _generate_wave(self, freq: float, time_array, wave_type: str = "sine"):
            """Generate a basic wave (sine, triangle, square)."""
            phase = 2 * np.pi * freq * time_array
            if wave_type == "sine":
                return np.sin(phase)
            elif wave_type == "triangle":
                sin_val = np.clip(np.sin(phase), -1.0, 1.0)
                return (2.0 / np.pi) * np.arcsin(sin_val)
            elif wave_type == "square":
                return np.sign(np.sin(phase))
            else:
                return np.sin(phase)

        def _create_adsr_envelope(self, samples: int):
            """Create ADSR envelope for smooth attack and release.

            Kept for backward compatibility and unit tests.
            """
            envelope = np.ones(samples)

            attack_samples = int(self.attack_time * self.sample_rate)
            decay_samples = int(self.decay_time * self.sample_rate)
            release_samples = int(self.release_time * self.sample_rate)

            # Attack
            if attack_samples > 0:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

            # Decay
            if decay_samples > 0 and attack_samples + decay_samples < samples:
                decay_end = attack_samples + decay_samples
                envelope[attack_samples:decay_end] = np.linspace(1, self.sustain_level, decay_samples)

            # Sustain
            sustain_start = attack_samples + decay_samples
            sustain_end = samples - release_samples
            if sustain_start < sustain_end:
                envelope[sustain_start:sustain_end] = self.sustain_level

            # Release
            if release_samples > 0:
                envelope[-release_samples:] = np.linspace(self.sustain_level, 0, release_samples)

            return envelope

        def _create_pad_envelope(self, samples: int):
            """Longer, softer envelope for pad-style ambient sound."""
            envelope = np.ones(samples)

            attack_samples = min(int(self.pad_attack_time * self.sample_rate), samples)
            decay_samples = min(int(self.pad_decay_time * self.sample_rate), max(0, samples - attack_samples))
            release_samples = min(int(self.pad_release_time * self.sample_rate), max(0, samples - attack_samples - decay_samples))

            if attack_samples > 0:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

            if decay_samples > 0:
                decay_end = attack_samples + decay_samples
                envelope[attack_samples:decay_end] = np.linspace(1, self.pad_sustain_level, decay_samples)

            sustain_start = attack_samples + decay_samples
            sustain_end = samples - release_samples
            if sustain_start < sustain_end:
                envelope[sustain_start:sustain_end] = self.pad_sustain_level

            if release_samples > 0:
                envelope[-release_samples:] = np.linspace(self.pad_sustain_level, 0, release_samples)

            return envelope

        def _create_tremolo(self, time_array):
            """Create tremolo LFO array."""
            return 1 + self.tremolo_depth * np.sin(2 * np.pi * self.tremolo_freq * time_array)

        def _generate_kick(self, time_array, duration: float):
            """Generate a soft kick drum pattern (gentle pulse)."""
            beat_interval = 60.0 / self.beat_bpm
            kick = np.zeros_like(time_array)
            dt = time_array[1] - time_array[0] if len(time_array) > 1 else 1.0 / self.sample_rate

            for beat_time in np.arange(0, duration, beat_interval):
                mask = (time_array >= beat_time) & (time_array < beat_time + 0.15)
                t = time_array[mask] - beat_time
                if len(t) > 0:
                    # Exponential frequency sweep 150Hz -> 40Hz
                    freqs = 150 * np.exp(-t * 20)
                    phases = 2 * np.pi * np.cumsum(freqs) * dt
                    envelope = np.exp(-t * 25)
                    kick[mask] += np.sin(phases) * envelope

            return kick * self.kick_volume

        def generate_chord_buffer(self, frequencies: List[float], duration: float = 3.0):
            """Generate a stereo audio buffer for a chord with layered synthesis."""
            samples = int(duration * self.sample_rate)
            time_array = np.linspace(0, duration, samples, False)

            # Empty chord = silence
            if not frequencies:
                return np.zeros((samples, 2), dtype=np.int16)

            # Initialize stereo buffer
            buffer = np.zeros((samples, 2))

            # Pad envelope and tremolo
            envelope = self._create_pad_envelope(samples)
            tremolo = self._create_tremolo(time_array)

            # Stereo panning LFO
            pan_lfo = self.pan_lfo_depth * np.sin(2 * np.pi * self.pan_lfo_freq * time_array)

            if self.arpeggiator and len(frequencies) > 1:
                # Arpeggiator mode: cycle through notes
                note_duration = min(self.arpeggiator_speed, duration / len(frequencies))
                segment_samples = int(note_duration * self.sample_rate)

                for i, freq in enumerate(frequencies):
                    start = i * segment_samples
                    if start >= samples:
                        break
                    end = min(start + segment_samples, samples)
                    seg_len = end - start
                    t_seg = time_array[start:end]

                    sine = self._generate_wave(freq, t_seg, "sine")
                    triangle = self._generate_wave(freq, t_seg, "triangle")
                    wave = sine + 0.3 * triangle

                    # Harmonic overtones
                    wave += 0.2 * self._generate_wave(freq * 2, t_seg, "sine")
                    wave += 0.15 * self._generate_wave(freq * 1.5, t_seg, "sine")

                    # Sub-bass for root note
                    if i == 0:
                        wave += 0.3 * self._generate_wave(freq / 2, t_seg, "sine")

                    # Short crossfade envelope per note
                    seg_env = np.ones(seg_len)
                    fade = min(int(0.08 * self.sample_rate), seg_len // 3)
                    if fade > 0:
                        seg_env[:fade] = np.linspace(0, 1, fade)
                        seg_env[-fade:] = np.linspace(1, 0, fade)

                    wave *= seg_env * tremolo[start:end]

                    note_pan = pan_lfo[start:end]
                    buffer[start:end, 0] += wave * (1.0 - note_pan)
                    buffer[start:end, 1] += wave * (1.0 + note_pan)
            else:
                # Normal chord mode: all notes layered together
                for i, freq in enumerate(frequencies):
                    # Layered oscillator: sine + triangle for warmth
                    sine = self._generate_wave(freq, time_array, "sine")
                    triangle = self._generate_wave(freq, time_array, "triangle")
                    wave = sine + 0.3 * triangle

                    # Harmonic overtones
                    wave += 0.2 * self._generate_wave(freq * 2, time_array, "sine")   # Octave
                    wave += 0.15 * self._generate_wave(freq * 1.5, time_array, "sine")  # Fifth

                    # Sub-bass for root note
                    if i == 0:
                        wave += 0.3 * self._generate_wave(freq / 2, time_array, "sine")

                    # Apply envelope and tremolo
                    wave *= envelope
                    wave *= tremolo

                    # Stereo panning per note + global LFO
                    base_pan = 0.15 * (i - len(frequencies) / 2) / max(len(frequencies) / 2, 1)
                    note_pan = base_pan + pan_lfo

                    buffer[:, 0] += wave * (1.0 - note_pan)
                    buffer[:, 1] += wave * (1.0 + note_pan)

            # Add soft kick drum pattern
            kick = self._generate_kick(time_array, duration)
            buffer[:, 0] += kick * 0.6
            buffer[:, 1] += kick * 0.6

            # Normalize to prevent clipping
            max_val = np.max(np.abs(buffer))
            if max_val > 0:
                buffer = buffer / max_val

            # Apply master volume and convert to 16-bit
            buffer *= VOLUME
            buffer = np.clip(buffer, -1.0, 1.0)
            buffer = (buffer * 32767).astype(np.int16)

            return buffer

        def create_sound_from_state(self, state: str):
            """Create a pygame Sound object for a given cognitive state."""
            if state not in CHORDS:
                state = "reviewing"  # Fallback

            frequencies = CHORDS[state]
            buffer = self.generate_chord_buffer(frequencies)

            # Create pygame sound from buffer
            return pygame.mixer.Sound(buffer)

        def play_state(self, state: str):
            """Play audio for a cognitive state with smooth transition."""
            if state == self.current_state and self.is_playing:
                return  # No change needed

            new_sound = self.create_sound_from_state(state)

            if self.current_sound and self.is_playing:
                # Crossfade to new state
                self._crossfade_to_sound(new_sound)
            else:
                # Start playing new sound
                self._start_playing(new_sound)

            self.current_state = state

        def _start_playing(self, sound):
            """Start playing a sound on loop."""
            self.current_sound = sound
            self.is_playing = True
            sound.play(-1)  # Loop indefinitely

        def _crossfade_to_sound(self, new_sound):
            """Smoothly crossfade from current sound to new sound."""
            if self.crossfade_thread and self.crossfade_thread.is_alive():
                return  # Already crossfading

            self.crossfade_thread = threading.Thread(
                target=self._do_crossfade,
                args=(new_sound,)
            )
            self.crossfade_thread.start()

        def _do_crossfade(self, new_sound):
            """Perform the actual crossfade operation."""
            # Start new sound at low volume
            new_sound.set_volume(0.0)
            new_sound.play(-1)

            # Crossfade over CROSSFADE_SECONDS
            steps = 50
            step_time = CROSSFADE_SECONDS / steps

            for i in range(steps + 1):
                progress = i / steps

                # Fade out old sound
                if self.current_sound:
                    old_volume = VOLUME * (1 - progress)
                    self.current_sound.set_volume(old_volume)

                # Fade in new sound
                new_volume = VOLUME * progress
                new_sound.set_volume(new_volume)

                time.sleep(step_time)

            # Stop old sound and update current
            if self.current_sound:
                self.current_sound.stop()

            self.current_sound = new_sound
            new_sound.set_volume(VOLUME)

        def toggle_arpeggiator(self, enabled: Optional[bool] = None):
            """Toggle arpeggiator mode on or off."""
            if enabled is None:
                self.arpeggiator = not self.arpeggiator
            else:
                self.arpeggiator = enabled
            return self.arpeggiator

        def stop(self):
            """Stop all audio playback."""
            if self.current_sound:
                self.current_sound.stop()
            self.is_playing = False
            pygame.mixer.stop()

        def cleanup(self):
            """Clean up audio resources."""
            self.stop()
            pygame.mixer.quit()

else:
    class AudioEngine:
        """Mock audio engine that prints to terminal when pygame/numpy are unavailable."""

        def __init__(self, sample_rate: int = 44100, buffer_size: int = 1024):
            self.sample_rate = sample_rate
            self.buffer_size = buffer_size
            self.current_state = None
            self.is_playing = False
            self.arpeggiator = False
            import sys
            print("[AUDIO MOCK] pygame/numpy not available — audio playback disabled")
            if sys.version_info >= (3, 14):
                print("[AUDIO MOCK] Tip: use Python 3.13 (py -3.13) or activate .venv in the project root")

        def play_state(self, state: str):
            """Print the requested state instead of playing audio."""
            if state == self.current_state and self.is_playing:
                return
            self.current_state = state
            self.is_playing = True
            chord = CHORDS.get(state, [])
            arp = " (arpeggiator ON)" if self.arpeggiator else ""
            print(f"[AUDIO MOCK] Playing state: {state}{arp} | chord: {chord}")

        def toggle_arpeggiator(self, enabled: Optional[bool] = None):
            """Toggle arpeggiator mode on or off."""
            if enabled is None:
                self.arpeggiator = not self.arpeggiator
            else:
                self.arpeggiator = enabled
            return self.arpeggiator

        def stop(self):
            """Stop mock playback."""
            self.is_playing = False
            print("[AUDIO MOCK] Stopped audio playback")

        def cleanup(self):
            """Clean up mock audio resources."""
            self.stop()
            print("[AUDIO MOCK] Cleaned up audio resources")

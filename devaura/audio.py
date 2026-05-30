"""
Procedural Audio Engine for DevAura

Generates ambient music based on cognitive states using pure Python synthesis.
Features smooth transitions, ADSR envelopes, crossfading, and synthesized drums.
"""

import threading
import time
from typing import List, Optional, Dict, Tuple
from config import VOLUME, CROSSFADE_SECONDS

# Pentatonic-based scales for each cognitive state (pleasant, no dissonance)
SCALES = {
    "flow":              [261.63, 293.66, 329.63, 392.00, 523.25],  # C major pentatonic (bright)
    "stuck":             [220.00, 261.63, 293.66, 329.63, 392.00],  # A minor pentatonic (somber)
    "debugging":         [293.66, 329.63, 369.99, 440.00, 493.88],  # D major pentatonic (focused)
    "reviewing":         [174.61, 196.00, 220.00, 261.63, 293.66],  # F major pentatonic (low drone)
    "context_switching": [196.00, 220.00, 246.94, 293.66, 329.63],  # G major pentatonic (open)
}

# Drum patterns per state (16 steps, 1 = hit, 0 = rest)
# Format: {"kick": [...], "snare": [...], "hihat": [...]}
DRUM_PATTERNS = {
    "flow": {
        # Steady, driving 4/4 pattern - classic productivity beat
        "kick":  [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hihat": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
    },
    "stuck": {
        # Sparse, glitchy - reflecting uncertainty
        "kick":  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        "snare": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "hihat": [0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0],
    },
    "debugging": {
        # Syncopated, analytical - like problem-solving rhythm
        "kick":  [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
        "hihat": [1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1],
    },
    "reviewing": {
        # Minimal, meditative - background focus
        "kick":  [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
        "snare": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "hihat": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
    },
    "context_switching": {
        # Busy, shifting - reflecting mental juggling
        "kick":  [1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0],
        "snare": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
        "hihat": [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0],
    },
}

# BPM per state (affects energy)
STATE_BPM = {
    "flow": 90,
    "stuck": 60,
    "debugging": 100,
    "reviewing": 70,
    "context_switching": 110,
}

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
    class DrumSynth:
        """Synthesizes drum sounds from scratch using pure Python/numpy."""
        
        def __init__(self, sample_rate: int = 44100):
            self.sample_rate = sample_rate
        
        def generate_kick(self, duration: float = 0.3) -> np.ndarray:
            """
            Synthesize a kick drum using a pitch-dropping sine wave.
            Classic 808-style kick: high pitch decays to low rumble.
            """
            samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, samples, False)
            
            # Pitch envelope: starts at 150Hz, drops to 50Hz
            freq_start = 150
            freq_end = 50
            freq = freq_end + (freq_start - freq_end) * np.exp(-t * 15)
            
            # Phase accumulation for smooth pitch bend
            phase = np.cumsum(freq / self.sample_rate) * 2 * np.pi
            wave = np.sin(phase)
            
            # Amplitude envelope: fast attack, medium decay
            amp_env = np.exp(-t * 8)
            
            # Add some punch with a click at the start
            click_samples = int(0.005 * self.sample_rate)
            click = np.zeros(samples)
            if click_samples > 0:
                click[:click_samples] = np.random.randn(click_samples) * 0.3
                click[:click_samples] *= np.linspace(1, 0, click_samples)
            
            kick = (wave * amp_env + click) * 0.7
            return kick
        
        def generate_snare(self, duration: float = 0.2) -> np.ndarray:
            """
            Synthesize a snare drum using sine waves + filtered noise.
            Softer, more electronic snare suitable for ambient.
            """
            samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, samples, False)
            
            # Tone component: two sine waves for body
            tone1 = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 20)
            tone2 = np.sin(2 * np.pi * 330 * t) * np.exp(-t * 25)
            tone = (tone1 + tone2 * 0.5) * 0.4
            
            # Noise component: filtered white noise for snap
            noise = np.random.randn(samples)
            # Simple low-pass filter via moving average
            kernel_size = 5
            noise = np.convolve(noise, np.ones(kernel_size)/kernel_size, mode='same')
            noise_env = np.exp(-t * 15)
            noise = noise * noise_env * 0.3
            
            snare = (tone + noise) * 0.5
            return snare
        
        def generate_hihat(self, duration: float = 0.1, open: bool = False) -> np.ndarray:
            """
            Synthesize a hi-hat using filtered noise + high-frequency content.
            """
            if open:
                duration = 0.25
            
            samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, samples, False)
            
            # High-frequency noise
            noise = np.random.randn(samples)
            
            # High-pass filter simulation: differentiate + scale
            hp_noise = np.diff(noise, prepend=noise[0]) * 2
            
            # Add some metallic tone
            metallic = np.sin(2 * np.pi * 6000 * t) * 0.1
            metallic += np.sin(2 * np.pi * 8000 * t) * 0.05
            
            # Envelope
            decay_rate = 10 if not open else 4
            env = np.exp(-t * decay_rate)
            
            hihat = (hp_noise * 0.3 + metallic) * env * 0.25
            return hihat
    
    class AudioEngine:
        def __init__(self, sample_rate: int = 44100, buffer_size: int = 1024):
            self.sample_rate = sample_rate
            self.buffer_size = buffer_size
            self.current_state = None
            self.current_sound = None
            self.is_playing = False
            self.crossfade_thread = None
            self._cleaned_up = False
            
            # Drum synth
            self.drum_synth = DrumSynth(sample_rate)
            self.drums_enabled = True
            self.drum_volume = 0.4  # Relative to melody
            
            # Pre-generate drum sounds
            self._kick_sample = self.drum_synth.generate_kick()
            self._snare_sample = self.drum_synth.generate_snare()
            self._hihat_sample = self.drum_synth.generate_hihat()

            # ADSR envelope: longer pad-like sound
            self.attack_time = 0.5
            self.decay_time = 0.3
            self.sustain_level = 0.7
            self.release_time = 1.0

            # Modulation parameters
            self.tremolo_freq = 0.5
            self.tremolo_depth = 0.03

            # Gentle rhythmic pulse (synced with drums when enabled)
            self.pulse_freq = 72.0 / 60.0  # 1.2 Hz default
            self.pulse_depth = 0.04

            # Slow stereo panning LFO
            self.pan_lfo_freq = 0.1
            self.pan_lfo_depth = 0.25

            # Initialize pygame mixer
            pygame.mixer.pre_init(
                frequency=self.sample_rate,
                size=-16,
                channels=2,
                buffer=self.buffer_size
            )
            pygame.mixer.init()
            self._mixer_initialized = True

        def _mix_drums_into_buffer(
            self, 
            buffer: np.ndarray, 
            state: str, 
            duration: float
        ) -> np.ndarray:
            """Mix drum pattern into the audio buffer."""
            if not self.drums_enabled:
                return buffer
            
            pattern = DRUM_PATTERNS.get(state, DRUM_PATTERNS["reviewing"])
            bpm = STATE_BPM.get(state, 80)
            
            samples = buffer.shape[0]
            
            # Calculate timing: 16 steps per 4 beats (16th notes)
            beat_duration = 60.0 / bpm  # seconds per beat
            step_duration = beat_duration / 4  # 16th note duration
            step_samples = int(step_duration * self.sample_rate)
            
            # Calculate how many full patterns fit in the buffer
            pattern_length = 16
            pattern_samples = step_samples * pattern_length
            num_patterns = int(samples / pattern_samples) + 1
            
            # Mix drums
            for pattern_idx in range(num_patterns):
                for step in range(pattern_length):
                    step_start = pattern_idx * pattern_samples + step * step_samples
                    if step_start >= samples:
                        break
                    
                    # Kick
                    if pattern["kick"][step]:
                        self._overlay_sample(buffer, self._kick_sample, step_start)
                    
                    # Snare
                    if pattern["snare"][step]:
                        self._overlay_sample(buffer, self._snare_sample, step_start)
                    
                    # Hi-hat
                    if pattern["hihat"][step]:
                        self._overlay_sample(buffer, self._hihat_sample, step_start)
            
            return buffer
        
        def _overlay_sample(
            self, 
            buffer: np.ndarray, 
            sample: np.ndarray, 
            start_pos: int
        ):
            """Overlay a mono sample onto stereo buffer at given position."""
            end_pos = min(start_pos + len(sample), buffer.shape[0])
            actual_length = end_pos - start_pos
            
            if actual_length <= 0:
                return
            
            # Mix as centered stereo (mono to both channels)
            drum_chunk = sample[:actual_length] * self.drum_volume * VOLUME
            buffer[start_pos:end_pos, 0] += drum_chunk
            buffer[start_pos:end_pos, 1] += drum_chunk

        def generate_chord_buffer(self, frequencies: List[float], state: str, duration: float = 4.0):
            """Generate a stereo audio buffer for a chord with layered oscillators, ADSR, drums, and modulations."""
            samples = int(duration * self.sample_rate)
            time_array = np.linspace(0, duration, samples, False)
            
            # Sync pulse with drum BPM
            bpm = STATE_BPM.get(state, 80)
            self.pulse_freq = bpm / 60.0

            # Initialize stereo buffer
            buffer = np.zeros((samples, 2))

            # Static stereo spread for notes
            n_notes = len(frequencies)
            if n_notes > 1:
                pans = np.linspace(-0.3, 0.3, n_notes)
            else:
                pans = [0.0]

            # Global modulations
            envelope = self._create_adsr_envelope(samples)
            tremolo = self._create_tremolo(time_array)
            pulse = self._create_pulse(time_array)
            pan_lfo = self.pan_lfo_depth * np.sin(2 * np.pi * self.pan_lfo_freq * time_array)

            # Generate each frequency in the chord
            for i, freq in enumerate(frequencies):
                # Layered oscillators
                wave = np.zeros(samples)

                # Primary sine wave
                wave += np.sin(2 * np.pi * freq * time_array)

                # Soft triangle wave for warmth (amplitude 0.3)
                tri = 2.0 * np.arcsin(np.sin(2 * np.pi * freq * time_array)) / np.pi
                wave += 0.3 * tri

                # Harmonic overtone: octave (+12 semitones) at 30% volume
                wave += 0.3 * np.sin(2 * np.pi * freq * 2.0 * time_array)

                # Harmonic overtone: perfect fifth (+7 semitones) at 30% volume
                fifth_freq = freq * (2.0 ** (7.0 / 12.0))
                wave += 0.3 * np.sin(2 * np.pi * fifth_freq * time_array)

                # Sub-bass sine at root/2 for warmth (lowest note only)
                if i == 0:
                    wave += 0.3 * np.sin(2 * np.pi * (freq / 2.0) * time_array)

                # Apply ADSR envelope
                wave *= envelope

                # Apply tremolo and rhythmic pulse
                wave *= tremolo * pulse

                # Stereo panning: static spread + slow LFO movement
                total_pan = pans[i] + pan_lfo
                total_pan = np.clip(total_pan, -0.9, 0.9)

                left_gain = 1.0 - total_pan
                right_gain = 1.0 + total_pan

                buffer[:, 0] += wave * left_gain
                buffer[:, 1] += wave * right_gain

            # Normalize melody to prevent clipping before adding drums
            max_val = np.max(np.abs(buffer))
            if max_val > 0:
                buffer = buffer / max_val * 0.7  # Leave headroom for drums

            # Mix in drums
            buffer = self._mix_drums_into_buffer(buffer, state, duration)

            # Final normalization
            max_val = np.max(np.abs(buffer))
            if max_val > 0:
                buffer = buffer / max_val

            # Apply master volume
            buffer *= VOLUME

            # Convert to 16-bit integers for pygame
            buffer = np.clip(buffer, -1.0, 1.0)
            buffer = (buffer * 32767).astype(np.int16)

            return buffer

        def _create_adsr_envelope(self, samples: int):
            """Create ADSR envelope for smooth attack and release."""
            envelope = np.ones(samples)

            attack_samples = min(int(self.attack_time * self.sample_rate), samples)
            decay_samples = min(int(self.decay_time * self.sample_rate), max(0, samples - attack_samples))
            release_samples = min(int(self.release_time * self.sample_rate), max(0, samples - attack_samples - decay_samples))

            # Attack
            if attack_samples > 0:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

            # Decay
            if decay_samples > 0:
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

        def _create_tremolo(self, time_array):
            """Create tremolo LFO array."""
            return 1 + self.tremolo_depth * np.sin(2 * np.pi * self.tremolo_freq * time_array)

        def _create_pulse(self, time_array):
            """Create gentle rhythmic pulse LFO array."""
            return 1 + self.pulse_depth * np.sin(2 * np.pi * self.pulse_freq * time_array)

        def create_sound_from_state(self, state: str):
            """Create a pygame Sound object for a given cognitive state."""
            if state not in SCALES:
                state = "reviewing"  # Fallback

            frequencies = SCALES[state]
            buffer = self.generate_chord_buffer(frequencies, state)

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
            try:
                # Start new sound at low volume
                new_sound.set_volume(0.0)
                new_sound.play(-1)

                # Crossfade over CROSSFADE_SECONDS
                steps = 50
                step_time = CROSSFADE_SECONDS / steps

                for i in range(steps + 1):
                    if not self.is_playing:
                        return  # Abort if stopped
                    progress = i / steps

                    # Fade out old sound
                    if self.current_sound:
                        old_volume = VOLUME * (1 - progress)
                        try:
                            self.current_sound.set_volume(old_volume)
                        except pygame.error:
                            pass  # Mixer may have been shut down

                    # Fade in new sound
                    new_volume = VOLUME * progress
                    try:
                        new_sound.set_volume(new_volume)
                    except pygame.error:
                        return  # Mixer shut down

                    time.sleep(step_time)

                # Stop old sound and update current
                if self.current_sound:
                    try:
                        self.current_sound.stop()
                    except pygame.error:
                        pass

                self.current_sound = new_sound
                try:
                    new_sound.set_volume(VOLUME)
                except pygame.error:
                    pass
            except pygame.error:
                pass  # Mixer may have been quit

        def stop(self):
            """Stop all audio playback."""
            if self.current_sound:
                self.current_sound.stop()
            self.is_playing = False
            pygame.mixer.stop()

        def cleanup(self):
            """Clean up audio resources."""
            self.stop()
            # Wait for crossfade thread to finish
            if self.crossfade_thread and self.crossfade_thread.is_alive():
                self.crossfade_thread.join(timeout=1.0)
            pygame.mixer.quit()
        
        def set_drums_enabled(self, enabled: bool):
            """Enable or disable drum beats."""
            self.drums_enabled = enabled
        
        def set_drum_volume(self, volume: float):
            """Set drum volume relative to melody (0.0 - 1.0)."""
            self.drum_volume = max(0.0, min(1.0, volume))

else:
    class AudioEngine:
        """Mock audio engine that prints to terminal when pygame/numpy are unavailable."""

        def __init__(self, sample_rate: int = 44100, buffer_size: int = 1024):
            self.sample_rate = sample_rate
            self.buffer_size = buffer_size
            self.current_state = None
            self.is_playing = False
            self.drums_enabled = True
            self.drum_volume = 0.4
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
            scale = SCALES.get(state, [])
            bpm = STATE_BPM.get(state, 80)
            drums = "ON" if self.drums_enabled else "OFF"
            print(f"[AUDIO MOCK] Playing state: {state} | BPM: {bpm} | drums: {drums} | scale: {scale}")

        def stop(self):
            """Stop mock playback."""
            self.is_playing = False
            print("[AUDIO MOCK] Stopped audio playback")

        def cleanup(self):
            """Clean up mock audio resources."""
            self.stop()
        
        def set_drums_enabled(self, enabled: bool):
            """Enable or disable drum beats."""
            self.drums_enabled = enabled
        
        def set_drum_volume(self, volume: float):
            """Set drum volume relative to melody (0.0 - 1.0)."""
            self.drum_volume = max(0.0, min(1.0, volume))

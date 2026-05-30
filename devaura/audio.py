"""
Procedural Audio Engine for DevAura

Generates ambient music based on cognitive states using pure Python synthesis.
Features smooth transitions, ADSR envelopes, and crossfading.
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
            
            # Audio parameters
            self.attack_time = 0.3
            self.decay_time = 0.2
            self.sustain_level = 0.8
            self.release_time = 0.5
            self.tremolo_freq = 0.5
            self.tremolo_depth = 0.05
            
            # Initialize pygame mixer
            pygame.mixer.pre_init(
                frequency=self.sample_rate,
                size=-16,
                channels=2,
                buffer=self.buffer_size
            )
            pygame.mixer.init()
            
        def generate_chord_buffer(self, frequencies: List[float], duration: float = 3.0):
            """Generate a stereo audio buffer for a chord with ADSR and tremolo."""
            samples = int(duration * self.sample_rate)
            time_array = np.linspace(0, duration, samples, False)
            
            # Initialize stereo buffer
            buffer = np.zeros((samples, 2))
            
            # Generate each frequency in the chord
            for freq in frequencies:
                # Generate sine wave
                wave = np.sin(2 * np.pi * freq * time_array)
                
                # Add sub-bass (root/2) for warmth
                if freq == frequencies[0]:  # Root note
                    sub_bass = 0.3 * np.sin(2 * np.pi * (freq / 2) * time_array)
                    wave += sub_bass
                
                # Apply ADSR envelope
                envelope = self._create_adsr_envelope(samples)
                wave *= envelope
                
                # Apply tremolo
                tremolo = self._create_tremolo(time_array)
                wave *= tremolo
                
                # Add to stereo buffer (slight panning for depth)
                pan = 0.1 * (freq / frequencies[0] - 1)  # Slight stereo spread
                left_gain = 1 - max(0, pan)
                right_gain = 1 + min(0, pan)
                
                buffer[:, 0] += wave * left_gain
                buffer[:, 1] += wave * right_gain
            
            # Normalize to prevent clipping
            max_val = np.max(np.abs(buffer))
            if max_val > 0:
                buffer = buffer / max_val
            
            # Apply master volume
            buffer *= VOLUME
            
            # Convert to 16-bit integers for pygame
            buffer = (buffer * 32767).astype(np.int16)
            
            return buffer
        
        def _create_adsr_envelope(self, samples: int):
            """Create ADSR envelope for smooth attack and release."""
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
            
            # Sustain (already set to sustain_level by default)
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
            print("[AUDIO MOCK] pygame/numpy not available — audio playback disabled")

        def play_state(self, state: str):
            """Print the requested state instead of playing audio."""
            if state == self.current_state and self.is_playing:
                return
            self.current_state = state
            self.is_playing = True
            chord = CHORDS.get(state, [])
            print(f"[AUDIO MOCK] Playing state: {state} | chord: {chord}")

        def stop(self):
            """Stop mock playback."""
            self.is_playing = False
            print("[AUDIO MOCK] Stopped audio playback")

        def cleanup(self):
            """Clean up mock audio resources."""
            self.stop()
            print("[AUDIO MOCK] Cleaned up audio resources")

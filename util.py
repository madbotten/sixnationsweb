"""
Utility helpers for the Alignments game.
Provides robust cached image loading from the 'hexes' folder and a sound playback manager.
Includes high-fidelity synthetic fallbacks for both images and sounds if files are missing.
"""

import os
import pygame
import math
import array

# Globals for asset caching
_image_cache = {}
_sound_cache = {}

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEXES_DIR = os.path.join(BASE_DIR, "hexes")
CHAMPIONS_DIR = os.path.join(BASE_DIR, "champions")
ARMIES_DIR = os.path.join(BASE_DIR, "armies")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

# ---------------------------------------------------------------------------
# Image loading helpers
# ---------------------------------------------------------------------------

_tinted_cache = {}   # (path, r, g, b, w, h) -> Surface


def load_image(filename, size=None, alpha=False):
    """Load an image from the images/ directory, optionally scaling it.

    Args:
        filename: File name relative to images/.
        size:     (width, height) tuple to scale to, or None for original.
        alpha:    If True, use convert_alpha() to preserve transparency.
    Returns:
        pygame.Surface (cached by filename+size).
    """
    key = (filename, size, alpha)
    if key in _image_cache:
        return _image_cache[key]

    path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        img = pygame.image.load(path)
        img = img.convert_alpha() if alpha else img.convert()
        if size is not None:
            img = pygame.transform.smoothscale(img, size)
        _image_cache[key] = img
        return img
    except pygame.error as e:
        print(f"[Util Warning] Could not load {filename}: {e}")
        return None


def load_tinted_sprite(filename, color, width, height):
    """Load a white-on-transparent PNG and tint it to *color*.

    Uses BLEND_RGB_MULT so white pixels become *color* and transparent
    pixels stay transparent.  Results are cached by (file, color, size).

    Args:
        filename: File name relative to images/.
        color:    (r, g, b) nation color tuple.
        width:    Target sprite width in pixels.
        height:   Target sprite height in pixels.
    Returns:
        pygame.Surface with per-pixel alpha, or None on error.
    """
    key = (filename, color[0], color[1], color[2], width, height)
    if key in _tinted_cache:
        return _tinted_cache[key]

    # Load or retrieve the base template at this size
    base = load_image(filename, size=(width, height), alpha=True)
    if base is None:
        return None

    tinted = base.copy()
    tinted.fill(color, special_flags=pygame.BLEND_RGB_MULT)
    _tinted_cache[key] = tinted
    return tinted

def get_font(size, bold=False):
    """
    Returns a pygame.font.Font object using Orbitron from fonts/ directory.
    Falls back to SysFont Courier if the font file does not exist.
    """
    try:
        font_name = "Orbitron-Bold.ttf" if bold else "orbitron.ttf"
        font_path = os.path.join(BASE_DIR, "fonts", font_name)
        if os.path.exists(font_path):
            return pygame.font.Font(font_path, size)
    except Exception as e:
        print(f"[Util Warning] Failed to load Orbitron font: {e}")
    return pygame.font.SysFont("Courier", size, bold=bold)

def play_sound(filename, volume=1.0, pitch_hz=440.0, duration_ms=150):
    """
    Plays a sound file. If the file is missing or Pygame mixer is not initialized,
    it automatically synthesizes a beautiful, clean sci-fi sine wave tone using the audio buffer,
    providing complete functional sound design without requiring physical files!
    """
    # Check if mixer is initialized
    if not pygame.mixer or not pygame.mixer.get_init():
        return None

    # Try playing physical file if cached/exists
    if filename:
        if filename in _sound_cache:
            sound = _sound_cache[filename]
            if sound:
                sound.set_volume(volume)
                sound.play()
                return sound

        # Check in local sfx/ folder if exists
        sfx_path = os.path.join(BASE_DIR, "sfx", filename)
        if os.path.exists(sfx_path):
            try:
                sound = pygame.mixer.Sound(sfx_path)
                sound.set_volume(volume)
                sound.play()
                _sound_cache[filename] = sound
                return sound
            except pygame.error as e:
                print(f"[Util Warning] Error playing sound file {filename}: {e}")
        
    # Synthetic default sound generator (Sci-fi synthesized bleep)
    # Cache based on pitch and duration
    synth_key = f"synth_{pitch_hz}_{duration_ms}"
    if synth_key in _sound_cache:
        sound = _sound_cache[synth_key]
        if sound:
            sound.set_volume(volume)
            sound.play()
            return sound

    try:
        # Synthesize a pure sine wave with smooth attack/decay envelope (so it sounds pleasant, not clicky)
        sample_rate = pygame.mixer.get_init()[0]
        num_samples = int(sample_rate * (duration_ms / 1000.0))
        
        # Audio sample buffer (16-bit signed integer format)
        buffer = array.array('h', [0] * num_samples)
        
        for i in range(num_samples):
            # Sine wave phase math
            t = float(i) / sample_rate
            sine_val = math.sin(2.0 * math.pi * pitch_hz * t)
            
            # Linear decay envelope to prevent popping/clicking at the end of the sound
            envelope = 1.0
            attack_samples = int(num_samples * 0.1)
            decay_samples = int(num_samples * 0.7)
            
            if i < attack_samples:
                envelope = float(i) / attack_samples
            elif i > (num_samples - decay_samples):
                envelope = float(num_samples - i) / decay_samples
                
            sample = int(sine_val * envelope * 16384) # 50% max amplitude for safety
            buffer[i] = sample
            
        sound = pygame.mixer.Sound(buffer)
        sound.set_volume(volume)
        sound.play()
        
        _sound_cache[synth_key] = sound
        return sound
    except Exception as e:
        print(f"[Util Warning] Could not synthesize sound: {e}")
        return None





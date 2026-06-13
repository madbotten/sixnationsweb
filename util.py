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

# Dictionary mapping lowercase keys to exact capitalized filenames on disk to ensure cross-platform case-sensitivity
DISK_CASING = {
    "woods": "Woods",
    "swamp": "Swamps",
    "mountains": "Mountains",
    "plains": "Plains",
    "desert": "Desert",
    "hills": "Hills",
    "coastal": "Coastal",
    "subterranean": "Subterranean",
    "barrens": "Barrens",
    "jungle": "Jungles",
    "echoingcaverns": "EchoingCaverns",
    "elmany": "Elmany",
    "fungaljungle": "FungalJungle",
    "goldencanyon": "GoldenCanyon",
    "gonce": "Gonce",
    "limbo": "Limbo",
    "petrifiedforest": "PetrifiedForest",
    "pitofdespair": "PitofDespair",
    "sunkencanopy": "SunkenCanopy",
    "tanelorn": "Tanelorn",
    "templeofevil": "TempleofEvil",
    "thedark": "TheDark",
    "thewilds": "TheWilds",
    "tileronde": "Tileronde",
    "towerofjustice": "TowerofJustice",
    "obsidianwastes": "ObsidianWastes",
    "stormtundra": "StormTundra"
}

def load_terrain_image(terrain_name, alpha=True, color_fallback=(0, 243, 255), size=(220, 120)):
    """
    Loads a terrain artwork image (e.g. 'Woods.jpg') from the 'hexes' folder with caching.
    If the image is missing, it dynamically generates a premium squashed neon hex placeholder.
    """
    # Convert input to lowercase to look up in DISK_CASING
    lookup_key = terrain_name.replace(".png", "").replace(".jpg", "").lower()
    clean_name = DISK_CASING.get(lookup_key, terrain_name)
    
    cache_key = (clean_name, alpha, size)
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    # Resolve full file path using .jpg extension and exact casing
    file_path = os.path.join(HEXES_DIR, f"{clean_name}.jpg")
    
    # Check if file exists and load
    if os.path.exists(file_path):
        try:
            # 1. Load the original rectangular JPG image
            original_surf = pygame.image.load(file_path)
            # Resize image to requested aspect size
            original_surf = pygame.transform.smoothscale(original_surf, size)
            original_surf = original_surf.convert_alpha() if alpha else original_surf.convert()
            
            # 2. Create a fully transparent destination surface with alpha channel
            W, H = size
            masked_surf = pygame.Surface(size, pygame.SRCALPHA)
            
            # 3. Draw a solid white interlocking squashed hex shape onto the transparent surface
            vertices = [
                (W, H / 2.0),
                (3.0 * W / 4.0, H),
                (W / 4.0, H),
                (0.0, H / 2.0),
                (W / 4.0, 0.0),
                (3.0 * W / 4.0, 0.0)
            ]
            pygame.draw.polygon(masked_surf, (255, 255, 255, 255), vertices)
            
            # 4. Blit the original image onto the hex shape using BLEND_RGBA_MIN
            # This masks out the rectangular corners, making them perfectly transparent
            masked_surf.blit(original_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            
            # Cache and return
            _image_cache[cache_key] = masked_surf
            return masked_surf
        except pygame.error as e:
            print(f"[Util Warning] Failed to load image {clean_name}.jpg: {e}. Creating placeholder.")
    else:
        # We don't want to spam warnings, but let the dev know
        print(f"[Util Warning] Image path not found: {file_path}. Creating placeholder.")

    # Create dynamic aesthetic placeholder
    # Creates a transparent surface with a glowing neon border and a cross pattern to represent a hexagon/node
    fallback_surf = pygame.Surface(size, pygame.SRCALPHA)
    W, H = size
    
    # Draw a beautiful squashed flat-topped hex outline for the placeholder
    vertices = [
        (W, H // 2),
        (3 * W // 4, H),
        (W // 4, H),
        (0, H // 2),
        (W // 4, 0),
        (3 * W // 4, 0)
    ]
    pygame.draw.polygon(fallback_surf, (*color_fallback, 40), vertices, 0) # Fill glow
    pygame.draw.polygon(fallback_surf, color_fallback, vertices, 2)       # Border outline
    
    # Draw simple text label of the file name on the placeholder
    try:
        font = get_font(12, bold=True)
        text_surf = font.render(clean_name.upper(), True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(W // 2, H // 2))
        
        # Draw background shadow for readability
        shadow_surf = font.render(clean_name.upper(), True, (11, 14, 20))
        fallback_surf.blit(shadow_surf, text_rect.move(1, 1))
        fallback_surf.blit(text_surf, text_rect)
    except:
        pass # If font system is not yet initialized
        
    _image_cache[cache_key] = fallback_surf
    return fallback_surf

def load_champion_image(faction_race, alpha=True, color_fallback=(189, 0, 255), size=(100, 100), mask_type="circle"):
    """
    Loads a champion unit artwork image based on faction race (e.g. 'elfchampion.jpg') from the 'champions' folder with caching.
    Supports 'circle', 'hex', or 'square' mask types.
    """
    race = faction_race.lower()
    if race == "dwarves":
        race_singular = "dwarf"
    elif race == "elves":
        race_singular = "elf"
    elif race == "giants":
        race_singular = "giant"
    elif race == "nomads":
        race_singular = "nomad"
    elif race == "barbarians":
        race_singular = "barbarian"
    elif race == "pirates":
        race_singular = "pirate"
    else:
        race_singular = race
    clean_name = f"{race_singular}champion"
    
    cache_key = ("champion_" + clean_name, alpha, size, mask_type)
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    file_path = os.path.join(CHAMPIONS_DIR, f"{clean_name}.jpg")
    
    if os.path.exists(file_path):
        try:
            original_surf = pygame.image.load(file_path)
            original_surf = pygame.transform.smoothscale(original_surf, size)
            original_surf = original_surf.convert_alpha() if alpha else original_surf.convert()
            
            W, H = size
            masked_surf = pygame.Surface(size, pygame.SRCALPHA)
            
            if mask_type == "hex":
                vertices = [
                    (W, H / 2.0),
                    (3.0 * W / 4.0, H),
                    (W / 4.0, H),
                    (0.0, H / 2.0),
                    (W / 4.0, 0.0),
                    (3.0 * W / 4.0, 0.0)
                ]
                pygame.draw.polygon(masked_surf, (255, 255, 255, 255), vertices)
            elif mask_type == "square":
                pygame.draw.rect(masked_surf, (255, 255, 255, 255), (0, 0, W, H))
            else:
                pygame.draw.circle(masked_surf, (255, 255, 255, 255), (W // 2, H // 2), min(W, H) // 2)
            
            masked_surf.blit(original_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            _image_cache[cache_key] = masked_surf
            return masked_surf
        except pygame.error as e:
            print(f"[Util Warning] Failed to load champion image {clean_name}.jpg: {e}. Creating placeholder.")
    else:
        print(f"[Util Warning] Champion image path not found: {file_path}. Creating placeholder.")

    # Create dynamic aesthetic placeholder
    fallback_surf = pygame.Surface(size, pygame.SRCALPHA)
    W, H = size
    
    if mask_type == "hex":
        vertices = [
            (W, H // 2),
            (3 * W // 4, H),
            (W // 4, H),
            (0, H // 2),
            (W // 4, 0),
            (3 * W // 4, 0)
        ]
        pygame.draw.polygon(fallback_surf, (*color_fallback, 40), vertices, 0)
        pygame.draw.polygon(fallback_surf, color_fallback, vertices, 2)
    elif mask_type == "square":
        pygame.draw.rect(fallback_surf, (*color_fallback, 40), (0, 0, W, H), 0)
        pygame.draw.rect(fallback_surf, color_fallback, (0, 0, W, H), 2)
    else:
        pygame.draw.circle(fallback_surf, (*color_fallback, 40), (W // 2, H // 2), min(W, H) // 2, 0)
        pygame.draw.circle(fallback_surf, color_fallback, (W // 2, H // 2), min(W, H) // 2, 2)
    
    try:
        font_size = max(6, min(10, W // 4))
        font = get_font(font_size, bold=True)
        abbr_len = max(3, W // 10)
        label_text = clean_name[:abbr_len].upper()
        
        text_surf = font.render(label_text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(W // 2, H // 2))
        
        shadow_surf = font.render(label_text, True, (11, 14, 20))
        fallback_surf.blit(shadow_surf, text_rect.move(1, 1))
        fallback_surf.blit(text_surf, text_rect)
    except:
        pass
        
    _image_cache[cache_key] = fallback_surf
    return fallback_surf

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

def format_location_name(terrain_type):
    """
    Formats CamelCase/PascalCase terrain names cleanly with spaces (e.g. "PitofDespair" -> "Pit of Despair").
    """
    # Replace "of" case-insensitively with spaces around it
    temp = terrain_type
    for target in ["of", "Of", "OF", "oF"]:
        temp = temp.replace(target, " of ")
        
    # Insert spaces before uppercase letters
    formatted = ""
    for i, char in enumerate(temp):
        if i > 0 and char.isupper():
            if temp[i-1] != ' ' and not temp[i-1].isupper():
                formatted += " " + char
                continue
        formatted += char
        
    # Collapse double spaces and strip
    parts = [p for p in formatted.split(" ") if p]
    return " ".join(parts)


def load_army_image(faction_race, alpha=True, color_fallback=(189, 0, 255), size=(100, 100), mask_type="circle"):
    """
    Loads an army unit artwork image based on faction race (e.g. 'elf.jpg') from the 'armies' folder with caching.
    Supports 'circle', 'hex', or 'square' mask types.
    """
    race = faction_race.lower()
    if race == "dwarves":
        race_singular = "dwarf"
    elif race == "elves":
        race_singular = "elf"
    elif race == "giants":
        race_singular = "giant"
    elif race == "nomads":
        race_singular = "nomad"
    elif race == "barbarians":
        race_singular = "barbarian"
    elif race == "pirates":
        race_singular = "pirate"
    elif race == "kuotoa":
        race_singular = "kuotoa"
    elif race == "humans":
        race_singular = "human"
    elif race == "lizardfolk":
        race_singular = "lizard"
    else:
        race_singular = race
    clean_name = race_singular
    
    cache_key = ("army_" + clean_name, alpha, size, mask_type)
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    file_path = os.path.join(ARMIES_DIR, f"{clean_name}.jpg")
    
    if os.path.exists(file_path):
        try:
            original_surf = pygame.image.load(file_path)
            original_surf = pygame.transform.smoothscale(original_surf, size)
            original_surf = original_surf.convert_alpha() if alpha else original_surf.convert()
            
            W, H = size
            masked_surf = pygame.Surface(size, pygame.SRCALPHA)
            
            if mask_type == "hex":
                vertices = [
                    (W, H / 2.0),
                    (3.0 * W / 4.0, H),
                    (W / 4.0, H),
                    (0.0, H / 2.0),
                    (W / 4.0, 0.0),
                    (3.0 * W / 4.0, 0.0)
                ]
                pygame.draw.polygon(masked_surf, (255, 255, 255, 255), vertices)
            elif mask_type == "square":
                pygame.draw.rect(masked_surf, (255, 255, 255, 255), (0, 0, W, H))
            else:
                pygame.draw.circle(masked_surf, (255, 255, 255, 255), (W // 2, H // 2), min(W, H) // 2)
            
            masked_surf.blit(original_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            _image_cache[cache_key] = masked_surf
            return masked_surf
        except pygame.error as e:
            print(f"[Util Warning] Failed to load army image {clean_name}.jpg: {e}. Creating placeholder.")
    else:
        print(f"[Util Warning] Army image path not found: {file_path}. Creating placeholder.")

    # Create dynamic aesthetic placeholder
    fallback_surf = pygame.Surface(size, pygame.SRCALPHA)
    W, H = size
    
    if mask_type == "hex":
        vertices = [
            (W, H // 2),
            (3 * W // 4, H),
            (W // 4, H),
            (0, H // 2),
            (W // 4, 0),
            (3 * W // 4, 0)
        ]
        pygame.draw.polygon(fallback_surf, (20, 24, 33, 200), vertices)
        pygame.draw.polygon(fallback_surf, color_fallback, vertices, 2)
    elif mask_type == "square":
        pygame.draw.rect(fallback_surf, (20, 24, 33, 200), (0, 0, W, H))
        pygame.draw.rect(fallback_surf, color_fallback, (0, 0, W, H), 2)
    else:
        pygame.draw.circle(fallback_surf, (20, 24, 33, 200), (W // 2, H // 2), min(W, H) // 2)
        pygame.draw.circle(fallback_surf, color_fallback, (W // 2, H // 2), min(W, H) // 2, 2)
        
    # Draw label letter
    try:
        font = get_font(int(14 * (W / 36.0)), bold=True)
        lbl = f"A:{clean_name[0].upper()}"
        text_surf = font.render(lbl, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(W // 2, H // 2))
        fallback_surf.blit(text_surf, text_rect)
    except:
        pass
        
    _image_cache[cache_key] = fallback_surf
    return fallback_surf


def load_artifact_image(image_filename, alpha=True, color_fallback=(255, 0, 127), size=(100, 100), mask_type="square"):
    """
    Loads an artifact image based on its filename (e.g. 'flamesword.jpg') from the 'artifacts' folder with caching.
    Supports 'circle', 'hex', or 'square' mask types.
    """
    clean_name = os.path.splitext(image_filename)[0].lower()
    
    cache_key = ("artifact_" + clean_name, alpha, size, mask_type)
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    file_path = os.path.join(ARTIFACTS_DIR, image_filename)
    
    if os.path.exists(file_path):
        try:
            original_surf = pygame.image.load(file_path)
            original_surf = pygame.transform.smoothscale(original_surf, size)
            original_surf = original_surf.convert_alpha() if alpha else original_surf.convert()
            
            W, H = size
            masked_surf = pygame.Surface(size, pygame.SRCALPHA)
            
            if mask_type == "hex":
                vertices = [
                    (W, H / 2.0),
                    (3.0 * W / 4.0, H),
                    (W / 4.0, H),
                    (0.0, H / 2.0),
                    (W / 4.0, 0.0),
                    (3.0 * W / 4.0, 0.0)
                ]
                pygame.draw.polygon(masked_surf, (255, 255, 255, 255), vertices)
            elif mask_type == "square":
                pygame.draw.rect(masked_surf, (255, 255, 255, 255), (0, 0, W, H))
            else:
                pygame.draw.circle(masked_surf, (255, 255, 255, 255), (W // 2, H // 2), min(W, H) // 2)
            
            masked_surf.blit(original_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            _image_cache[cache_key] = masked_surf
            return masked_surf
        except pygame.error as e:
            print(f"[Util Warning] Failed to load artifact image {image_filename}: {e}. Creating placeholder.")
    else:
        print(f"[Util Warning] Artifact image path not found: {file_path}. Creating placeholder.")

    # Create dynamic aesthetic placeholder
    fallback_surf = pygame.Surface(size, pygame.SRCALPHA)
    W, H = size
    
    if mask_type == "hex":
        vertices = [
            (W, H // 2),
            (3 * W // 4, H),
            (W // 4, H),
            (0, H // 2),
            (W // 4, 0),
            (3 * W // 4, 0)
        ]
        pygame.draw.polygon(fallback_surf, (20, 24, 33, 200), vertices)
        pygame.draw.polygon(fallback_surf, color_fallback, vertices, 2)
    elif mask_type == "square":
        pygame.draw.rect(fallback_surf, (20, 24, 33, 200), (0, 0, W, H))
        pygame.draw.rect(fallback_surf, color_fallback, (0, 0, W, H), 2)
    else:
        pygame.draw.circle(fallback_surf, (20, 24, 33, 200), (W // 2, H // 2), min(W, H) // 2)
        pygame.draw.circle(fallback_surf, color_fallback, (W // 2, H // 2), min(W, H) // 2, 2)
        
    # Draw label letter
    try:
        font = get_font(int(12 * (W / 36.0)), bold=True)
        lbl = f"Art:{clean_name[:4].upper()}"
        text_surf = font.render(lbl, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(W // 2, H // 2))
        fallback_surf.blit(text_surf, text_rect)
    except:
        pass
        
    _image_cache[cache_key] = fallback_surf
    return fallback_surf



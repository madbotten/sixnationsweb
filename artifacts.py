"""
Artifacts System - Alignments
Defines the Artifact class representing items that Champions can possess.
"""

import random
import util

class Artifact:
    def __init__(self, name, image_filename):
        """
        Initializes an Artifact instance.
        
        Args:
            name (str): The display name of the artifact (e.g. 'Flame Sword').
            image_filename (str): The filename of its artwork under artifacts/ (e.g. 'flamesword.jpg').
        """
        self.name = name
        self.image_filename = image_filename
        self.discovered = False

    def get_image(self, size=(100, 100)):
        """
        Loads and returns the cached, masked Pygame surface representing this artifact's image.
        """
        return util.load_artifact_image(self.image_filename, size=size)

    def __repr__(self):
        return f"Artifact(name='{self.name}', image_filename='{self.image_filename}', discovered={self.discovered})"


# Templates for various artifacts in the world.
# As requested, these currently map to existing flamesword.jpg and goldenaxe.jpg.
# This list can be expanded up to 10 or more unique items later.
ARTIFACT_TEMPLATES = [
    ("Flame Sword", "flamesword.jpg"),
    ("Golden Axe", "goldenaxe.jpg"),
    ("Sun Shield", "goldenaxe.jpg"),
    ("Dragon Blade", "flamesword.jpg"),
    ("Ice Amulet", "goldenaxe.jpg"),
    ("Storm Hammer", "goldenaxe.jpg"),
    ("Shadow Dagger", "flamesword.jpg"),
    ("Ring of Power", "flamesword.jpg"),
    ("Aegis Shield", "goldenaxe.jpg"),
    ("Cloak of Shadows", "flamesword.jpg")
]


def create_artifact_pool():
    """
    Creates and returns a list of 7 unique Artifact instances chosen randomly
    from the artifact templates pool.
    """
    templates = list(ARTIFACT_TEMPLATES)
    random.shuffle(templates)
    
    pool = []
    for i in range(min(7, len(templates))):
        name, filename = templates[i]
        pool.append(Artifact(name, filename))
    return pool

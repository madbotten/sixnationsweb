"""
Artifacts System - Alignments
Defines the Artifact class representing items that Champions can possess.
Each of the 7 artifacts maps exactly one-to-one with an image file and carries
a unique power tag that the game engine checks at runtime.

Power tags:
    FLAME_SWORD     - Champion adds +2 to the faction's combat strength (baseline bonus).
    GOLDEN_AXE      - Champion's winning side inflicts +1 extra loss (die roll + 1).
    AIR_SWORD       - Champion may move 2 hexes per turn instead of 1.
    ELVEN_ARMS      - One-time shield: absorbed on lethal hit, negates up to 3 damage;
                      remaining damage overflows to enemy stronghold if present.
    STAR_STAFF      - Holding faction earns +1 gold each income phase.
    TOXIC_CROSSBOW  - Opposing champions in the same hex fight at -1 strength (min 1).
    WALL_BREAKER    - +2 effective strength vs. strongholds (treat stronghold_strength as -2).
"""

import util


class Artifact:
    def __init__(self, name, image_filename, power):
        """
        Initializes an Artifact instance.

        Args:
            name (str): The display name of the artifact (e.g. 'Flame Sword').
            image_filename (str): Filename of its artwork under artifacts/ (e.g. 'flamesword.jpg').
            power (str): Power tag string identifying the artifact's special rule.
        """
        self.name = name
        self.image_filename = image_filename
        self.power = power
        self.discovered = False

    def get_image(self, size=(100, 100)):
        """
        Loads and returns the cached, masked Pygame surface representing this artifact's image.
        """
        return util.load_artifact_image(self.image_filename, size=size)

    def __repr__(self):
        return (
            f"Artifact(name='{self.name}', power='{self.power}', "
            f"image_filename='{self.image_filename}', discovered={self.discovered})"
        )


# Exactly 7 artifacts — one per image file — for the 7 center hexes.
# Order here does not matter; create_artifact_pool() shuffles before placement.
ARTIFACT_TEMPLATES = [
    ("Flame Sword",    "flamesword.jpg",     "FLAME_SWORD"),
    ("Golden Axe",     "goldenaxe.jpg",      "GOLDEN_AXE"),
    ("Air Sword",      "airsword.jpg",       "AIR_SWORD"),
    ("Elven Arms",     "elvenarms.jpg",      "ELVEN_ARMS"),
    ("Star Staff",     "starstaff.jpg",      "STAR_STAFF"),
    ("Toxic Crossbow", "toxiccrossbow.jpg",  "TOXIC_CROSSBOW"),
    ("Wall Breaker",   "wallbreaker.jpg",    "WALL_BREAKER"),
]


def create_artifact_pool():
    """
    Creates and returns a shuffled list of all 7 Artifact instances,
    one per center hex. Each artifact is unique.
    """
    import random
    templates = list(ARTIFACT_TEMPLATES)
    random.shuffle(templates)
    return [Artifact(name, filename, power) for name, filename, power in templates]

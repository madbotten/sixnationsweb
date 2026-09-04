"""
Nation System -- Six Nations
Six nations with dynamic diplomatic stances: ally, neutral, or enemy.
All nations start neutral to each other. Stances are symmetric.
"""
import settings


class Nation:
    """Represents one of the six nations."""

    def __init__(self, name: str):
        self.color_name  = name
        self.color_rgb   = settings.NATION_COLORS[name]
        self.color_light = settings.NATION_HEX_FILLS[name]
        self.is_ghost    = False   # True when this nation's sovereign is destroyed

        # Dynamic diplomatic lists (other Nation objects).
        # Populated by _init_diplomacy() after all nations exist.
        self.allies:   list = []
        self.neutrals: list = []
        self.enemies:  list = []

    def __eq__(self, other):
        if isinstance(other, Nation):
            return self.color_name == other.color_name
        return False

    def __hash__(self):
        return hash(self.color_name)

    # -------------------------------------------------------------------
    # Stance queries
    # -------------------------------------------------------------------

    def get_stance(self, other: "Nation") -> str:
        """Return the diplomatic stance toward *other*.

        Returns one of: 'self', 'ally', 'neutral', 'enemy'.
        """
        if other is self:
            return 'self'
        if other in self.allies:
            return 'ally'
        if other in self.enemies:
            return 'enemy'
        return 'neutral'

    def is_ally(self, other: "Nation") -> bool:
        """True when *other* is on this nation's ally list."""
        return self.get_stance(other) == 'ally'

    def is_enemy(self, other: "Nation") -> bool:
        """True when *other* is on this nation's enemy list."""
        return self.get_stance(other) == 'enemy'

    def enemy_nations(self, all_nations: "list[Nation]" = None) -> "list[Nation]":
        """Return the current list of enemy nations."""
        return list(self.enemies)

    def ally_nations(self, all_nations: "list[Nation]" = None) -> "list[Nation]":
        """Return the current list of ally nations."""
        return list(self.allies)

    # -------------------------------------------------------------------
    # Stance setters (symmetric -- always mirrors on the other nation)
    # -------------------------------------------------------------------

    def _remove_from_all(self, other: "Nation") -> None:
        """Remove *other* from all three lists (internal helper)."""
        for lst in (self.allies, self.neutrals, self.enemies):
            if other in lst:
                lst.remove(other)

    def set_ally(self, other: "Nation") -> None:
        """Declare *other* an ally. Mirrors symmetrically."""
        if other is self:
            return
        self._remove_from_all(other)
        self.allies.append(other)
        other._remove_from_all(self)
        if self not in other.allies:
            other.allies.append(self)

    def set_neutral(self, other: "Nation") -> None:
        """Set stance with *other* to neutral. Mirrors symmetrically."""
        if other is self:
            return
        self._remove_from_all(other)
        self.neutrals.append(other)
        other._remove_from_all(self)
        if self not in other.neutrals:
            other.neutrals.append(self)

    def set_enemy(self, other: "Nation") -> None:
        """Declare *other* an enemy. Mirrors symmetrically."""
        if other is self:
            return
        self._remove_from_all(other)
        self.enemies.append(other)
        other._remove_from_all(self)
        if self not in other.enemies:
            other.enemies.append(self)

    # -------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"Nation({self.color_name})"


# ---------------------------------------------------------------------------
# Module-level initialisation
# ---------------------------------------------------------------------------

def _init_diplomacy(nations: "list[Nation]") -> None:
    """Populate each nation's neutral list with all other nations.

    Called once after the full list of nations is created so that every
    nation object already exists when we cross-reference them.
    All pairs start as neutral.
    """
    for nation in nations:
        nation.allies   = []
        nation.neutrals = []
        nation.enemies  = []
    for nation in nations:
        for other in nations:
            if other is not nation and other not in nation.neutrals:
                nation.neutrals.append(other)


# The six predefined nation singletons, shared across the whole game.
NATIONS: list = [Nation(name) for name in settings.NATION_NAMES]
NATIONS_BY_NAME: dict = {n.color_name: n for n in NATIONS}
_init_diplomacy(NATIONS)


def create_nations() -> list:
    """Create an independent set of 6 Nation objects (not the shared singletons).

    Use this for headless / bot-vs-bot games so that mutable state (e.g.
    is_ghost, allies/neutrals/enemies) does not leak between concurrent
    game instances.
    """
    nations = [Nation(name) for name in settings.NATION_NAMES]
    _init_diplomacy(nations)
    return nations

"""
Player System -- Six Nations
Represents a human or bot player with prevail and defeat prediction goals.
"""


class Player:
    """
    A player in the game.

    Attributes:
        is_bot        : True if AI-controlled.
        player_id     : 'player1' or 'player2'.
        cooldown      : Color names of the last 2 nations this player moved
                        (most recent first).  A player cannot move a nation
                        that is in their cooldown list.
        prevail_picks : Up to 3 Nations the player predicts will survive
                        (sovereign still alive at game end).
        defeat_picks  : Up to 3 Nations the player predicts will be defeated
                        (sovereign destroyed at game end).
    """

    def __init__(self, is_bot: bool = False, player_id: str = 'player1'):
        self.is_bot         = is_bot
        self.player_id      = player_id    # 'player1' or 'player2'
        self.cooldown: list[str] = []      # at most 2 entries (color_name strings)
        self.prevail_picks: list = []      # list[Nation], max 3
        self.defeat_picks:  list = []      # list[Nation], max 3

    # -----------------------------------------------------------------------
    # Cooldown management
    # -----------------------------------------------------------------------

    def add_to_cooldown(self, nation):
        """Record that this player just moved nation; keep only last 2."""
        self.cooldown.insert(0, nation.color_name)
        if len(self.cooldown) > 2:
            self.cooldown.pop()

    def nation_on_cooldown(self, nation) -> bool:
        """True if this player is forbidden from moving the given nation."""
        return nation.color_name in self.cooldown

    # -----------------------------------------------------------------------
    # Prediction scoring
    # -----------------------------------------------------------------------

    def compute_score(self) -> int:
        """Score based on pre-game predictions at game end.

        Position weights (same for both PREVAIL and DEFEAT boxes):
          slot 0 (top / placed first)  : 3 pts if correct
          slot 1                       : 2 pts if correct
          slot 2 (bottom / placed last): 1 pt  if correct
        Maximum 12 points total (6 per box).
        """
        _weights = (3, 2, 1)
        score  = sum(w for w, n in zip(_weights, self.prevail_picks) if not n.is_ghost)
        score += sum(w for w, n in zip(_weights, self.defeat_picks)  if n.is_ghost)
        return score

    # -----------------------------------------------------------------------
    # Win / loss helpers
    # -----------------------------------------------------------------------

    def get_enemies(self, all_nations):
        """Enemies based on defeat picks."""
        if self.defeat_picks:
            return list(self.defeat_picks)
        return []

    def __repr__(self) -> str:
        kind = "Bot" if self.is_bot else "Human"
        return f"Player({kind}, id={self.player_id})"

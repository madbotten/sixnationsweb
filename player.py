"""
Player System -- Six Nations
Represents a human or bot player holding a secret nation assignment.
"""


class Player:
    """
    A player in the game.

    Attributes:
        secret_nation : The Nation this player is secretly rooting for.
        is_bot        : True if AI-controlled.
        cooldown      : Ring indices of the last 2 nations this player moved
                        (most recent first).  A player cannot move a nation
                        that is in their cooldown list.
    """

    def __init__(self, secret_nation, is_bot: bool = False, player_id: str = 'player1'):
        self.secret_nation = secret_nation
        self.is_bot        = is_bot
        self.player_id     = player_id    # 'player1' or 'player2'
        self.cooldown: list[int] = []     # at most 2 entries

    # -----------------------------------------------------------------------
    # Cooldown management
    # -----------------------------------------------------------------------

    def add_to_cooldown(self, nation):
        """Record that this player just moved nation; keep only last 2."""
        self.cooldown.insert(0, nation.ring_index)
        if len(self.cooldown) > 2:
            self.cooldown.pop()

    def nation_on_cooldown(self, nation) -> bool:
        """True if this player is forbidden from moving the given nation."""
        return nation.ring_index in self.cooldown

    # -----------------------------------------------------------------------
    # Win / loss helpers
    # -----------------------------------------------------------------------

    def get_enemies(self, all_nations):
        """The 3 nations that are enemies of this player's secret nation."""
        return self.secret_nation.enemy_nations(all_nations)

    def __repr__(self) -> str:
        kind = "Bot" if self.is_bot else "Human"
        return f"Player({kind}, secret={self.secret_nation.color_name})"

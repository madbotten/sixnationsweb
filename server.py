"""
Six Nations — WebSocket Match Server

Lightweight server for matching two players and relaying moves between them.
Run with: python server.py

Players connect via WebSocket and send:
    {"my_name": "Alice", "opponent_name": "Bob"}

The server matches them when both sides have connected, assigns roles
(player1 / player2) and secret nations, then relays move dicts between them.
"""

import asyncio
import json
import random
import websockets

HOST = "0.0.0.0"
PORT = 8765

# Nation ring indices 0-5; names for debug logging
NATION_NAMES = ["Yellow", "Green", "Sky Blue", "Cobalt", "Magenta", "Crimson"]

# Pending connections waiting to be matched:  key = frozenset({nameA, nameB})
# value = {"players": {name: websocket}, "ready": set of names}
pending_matches = {}


async def handler(websocket):
    """Handle one WebSocket connection from a player."""
    player_name = None
    match_key = None

    try:
        # First message must be the matchmaking payload
        raw = await websocket.recv()
        data = json.loads(raw)
        my_name  = data["my_name"].strip()
        opp_name = data["opponent_name"].strip()
        player_name = my_name
        match_key   = frozenset({my_name, opp_name})

        print(f"[Connect] {my_name} wants to play {opp_name}")

        # Register in pending_matches
        if match_key not in pending_matches:
            pending_matches[match_key] = {"players": {}, "started": False}

        match = pending_matches[match_key]

        if my_name in match["players"]:
            await websocket.send(json.dumps({
                "type": "ERROR", "msg": f"'{my_name}' is already connected."}))
            return

        match["players"][my_name] = websocket

        # If only one player so far, tell them to wait
        if len(match["players"]) < 2:
            await websocket.send(json.dumps({
                "type": "WAITING",
                "msg": f"Waiting for {opp_name} to join…"}))
        # else: both players connected — but let the second joiner fall through

        # Wait until both sides are present
        while len(match["players"]) < 2:
            await asyncio.sleep(0.3)

        # Both connected — assign roles & nations (only once)
        if not match["started"]:
            match["started"] = True
            names = sorted(match["players"].keys())

            # Random unique secret nations
            ri1, ri2 = random.sample(range(6), 2)

            match["roles"] = {
                names[0]: {"role": "player1", "nation_ri": ri1},
                names[1]: {"role": "player2", "nation_ri": ri2},
            }
            match["names"] = names

            print(f"[Match] {names[0]} (player1, {NATION_NAMES[ri1]}) vs "
                  f"{names[1]} (player2, {NATION_NAMES[ri2]})")

            # Send START to both players
            for name in names:
                ws = match["players"][name]
                info = match["roles"][name]
                opp  = [n for n in names if n != name][0]
                await ws.send(json.dumps({
                    "type":      "START",
                    "role":      info["role"],
                    "nation_ri": info["nation_ri"],
                    "opp_name":  opp,
                    "your_turn": info["role"] == "player1",
                }))

        # Relay loop — forward every message to the opponent
        other_name = [n for n in match["names"] if n != my_name][0]
        async for raw_msg in websocket:
            msg = json.loads(raw_msg)
            msg["_from"] = my_name  # tag for debugging
            other_ws = match["players"].get(other_name)
            if other_ws:
                await other_ws.send(json.dumps(msg))
                print(f"[Relay] {my_name} → {other_name}: {msg.get('type', '?')}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[Disconnect] {player_name or '?'}")
    except Exception as e:
        print(f"[Error] {player_name or '?'}: {e}")
    finally:
        # Clean up
        if match_key and match_key in pending_matches:
            match = pending_matches[match_key]
            if player_name and player_name in match["players"]:
                del match["players"][player_name]
            # Notify remaining player
            for name, ws in match["players"].items():
                try:
                    await ws.send(json.dumps({
                        "type": "DISCONNECT",
                        "msg": f"{player_name} disconnected."}))
                except Exception:
                    pass
            if not match["players"]:
                del pending_matches[match_key]


async def start_server():
    print(f"Six Nations server listening on ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(start_server())

import asyncio, json, os, websockets

rooms = {}
PORT = int(os.environ.get("PORT", 8080))

async def handler(ws):
    path = ws.path
    room_id = path.strip("/")
    if not room_id or "/" in room_id:
        await ws.close(1008, "invalid room")
        return

    if room_id not in rooms:
        rooms[room_id] = {"a": None, "b": None}
    room = rooms[room_id]

    if room["a"] is None:
        room["a"] = ws; role = "a"
    elif room["b"] is None:
        room["b"] = ws; role = "b"
        await room["a"].send(json.dumps({"t": "peer_on"}))
    else:
        await ws.close(1008, "room full")
        return

    await ws.send(json.dumps({"t": "role", "role": role}))

    try:
        async for msg in ws:
            peer = room["b"] if role == "a" else room["a"]
            if peer:
                await peer.send(msg)
    except:
        pass
    finally:
        if role == "a":
            room["a"] = None
            if room["b"]:
                await room["b"].send(json.dumps({"t": "peer_off"}))
        else:
            room["b"] = None
            if room["a"]:
                await room["a"].send(json.dumps({"t": "peer_off"}))
        if room["a"] is None and room["b"] is None:
            rooms.pop(room_id, None)

async def main():
    print(f"relay listening :{PORT}")
    async with websockets.serve(handler, "0.0.0.0", PORT):
        await asyncio.Future()

asyncio.run(main())

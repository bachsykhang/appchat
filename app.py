from __future__ import annotations

import random
import string
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Tuple

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, join_room


@dataclass
class ChatRoom:
    code: str
    owner_id: str
    members: Dict[str, dict] = field(default_factory=dict)
    messages: List[dict] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)


def make_app() -> Tuple[Flask, SocketIO]:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "chat-online-secret-change-me"
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    rooms: Dict[str, ChatRoom] = {}
    room_lock = Lock()

    def ensure_user_id() -> str:
        if "user_id" not in session:
            session["user_id"] = str(uuid.uuid4())
        return session["user_id"]

    def sanitize_name(name: str) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            return "Guest"
        return cleaned[:24]

    def sanitize_code(code: str) -> str:
        return "".join(ch for ch in (code or "").upper().strip() if ch.isalnum())[:6]

    def make_room_code(length: int = 6) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))

    def add_system_message(room: ChatRoom, text: str) -> None:
        room.messages.append(
            {
                "sender": "System",
                "sender_id": "system",
                "text": text[:200],
                "ts": int(time.time()),
            }
        )
        room.messages = room.messages[-120:]
        room.updated_at = time.time()

    def add_user_message(room: ChatRoom, user_id: str, text: str) -> None:
        sender_name = room.members.get(user_id, {}).get("name", "Guest")
        room.messages.append(
            {
                "sender": sender_name,
                "sender_id": user_id,
                "text": text[:400],
                "ts": int(time.time()),
            }
        )
        room.messages = room.messages[-120:]
        room.updated_at = time.time()

    def room_snapshot(room: ChatRoom, current_user_id: str) -> dict:
        member_list = sorted(
            room.members.values(),
            key=lambda item: (item["name"].lower(), item["id"]),
        )
        return {
            "code": room.code,
            "owner_id": room.owner_id,
            "current_user_id": current_user_id,
            "member_count": len(member_list),
            "members": member_list,
            "messages": room.messages,
        }

    def emit_room_state(code: str) -> None:
        with room_lock:
            room = rooms.get(code)
            if not room:
                return
            snapshots = {
                user_id: room_snapshot(room, user_id)
                for user_id in room.members.keys()
            }
        for user_id, snapshot in snapshots.items():
            socketio.emit("state_update", snapshot, to=f"user:{user_id}")

    @app.get("/")
    def home() -> str:
        ensure_user_id()
        return render_template("index.html")

    @app.post("/enter")
    def enter_room():
        user_id = ensure_user_id()
        user_name = sanitize_name(request.form.get("name", ""))
        requested_code = sanitize_code(request.form.get("code", ""))
        action = (request.form.get("action", "") or "").strip().lower()

        with room_lock:
            if action == "join":
                if not requested_code or requested_code not in rooms:
                    return redirect(url_for("home"))
                room = rooms[requested_code]
                code = requested_code
            else:
                code = make_room_code()
                while code in rooms:
                    code = make_room_code()
                room = ChatRoom(code=code, owner_id=user_id)
                rooms[code] = room

            is_new_member = user_id not in room.members
            room.members[user_id] = {
                "id": user_id,
                "name": user_name,
                "joined_at": int(time.time()),
            }

            if action == "create":
                add_system_message(room, f"{user_name} da tao phong chat.")
            elif is_new_member:
                add_system_message(room, f"{user_name} da vao phong.")

        session["user_name"] = user_name
        session["room_code"] = code
        emit_room_state(code)
        return redirect(url_for("chat_room_page", code=code))

    @app.post("/api/mobile/create")
    def mobile_create_room():
        user_id = ensure_user_id()
        payload = request.get_json(silent=True) or {}
        user_name = sanitize_name(payload.get("name", ""))

        with room_lock:
            code = make_room_code()
            while code in rooms:
                code = make_room_code()
            room = ChatRoom(code=code, owner_id=user_id)
            room.members[user_id] = {
                "id": user_id,
                "name": user_name,
                "joined_at": int(time.time()),
            }
            rooms[code] = room
            add_system_message(room, f"{user_name} da tao phong chat.")

        session["user_name"] = user_name
        session["room_code"] = code
        emit_room_state(code)
        return jsonify({"ok": True, "room_code": code})

    @app.post("/api/mobile/join")
    def mobile_join_room():
        user_id = ensure_user_id()
        payload = request.get_json(silent=True) or {}
        user_name = sanitize_name(payload.get("name", ""))
        room_code = sanitize_code(payload.get("code", ""))
        if not room_code:
            return jsonify({"error": "Room code is required"}), 400

        with room_lock:
            room = rooms.get(room_code)
            if not room:
                return jsonify({"error": "Room not found"}), 404

            is_new_member = user_id not in room.members
            room.members[user_id] = {
                "id": user_id,
                "name": user_name,
                "joined_at": int(time.time()),
            }
            if is_new_member:
                add_system_message(room, f"{user_name} da vao phong.")

        session["user_name"] = user_name
        session["room_code"] = room_code
        emit_room_state(room_code)
        return jsonify({"ok": True, "room_code": room_code})

    @app.get("/chat/<code>")
    def chat_room_page(code: str):
        user_id = ensure_user_id()
        room_code = sanitize_code(code)

        with room_lock:
            room = rooms.get(room_code)
            if not room:
                return redirect(url_for("home"))
            if user_id not in room.members:
                fallback_name = sanitize_name(session.get("user_name", "Guest"))
                room.members[user_id] = {
                    "id": user_id,
                    "name": fallback_name,
                    "joined_at": int(time.time()),
                }
                add_system_message(room, f"{fallback_name} da ket noi lai.")

        return render_template("chat.html", room_code=room_code)

    @app.get("/api/room/<code>/state")
    def room_state_api(code: str):
        user_id = ensure_user_id()
        room_code = sanitize_code(code)

        with room_lock:
            room = rooms.get(room_code)
            if not room:
                return jsonify({"error": "Room not found"}), 404

            if user_id not in room.members:
                fallback_name = sanitize_name(session.get("user_name", "Guest"))
                room.members[user_id] = {
                    "id": user_id,
                    "name": fallback_name,
                    "joined_at": int(time.time()),
                }
                add_system_message(room, f"{fallback_name} da ket noi lai.")

            return jsonify(room_snapshot(room, user_id))

    @app.post("/api/room/<code>/message")
    def send_message_api(code: str):
        user_id = ensure_user_id()
        room_code = sanitize_code(code)
        payload = request.get_json(silent=True) or {}
        text = (str(payload.get("text", "")) or "").strip()

        if not text:
            return jsonify({"error": "Message is empty"}), 400

        with room_lock:
            room = rooms.get(room_code)
            if not room:
                return jsonify({"error": "Room not found"}), 404
            if user_id not in room.members:
                return jsonify({"error": "User not in room"}), 403
            add_user_message(room, user_id, text)

        emit_room_state(room_code)
        return jsonify({"ok": True})

    @socketio.on("join_room")
    def join_room_socket(data):
        user_id = ensure_user_id()
        room_code = sanitize_code(str((data or {}).get("code", "")))
        if not room_code:
            socketio.emit("room_error", {"error": "Missing room code"}, to=request.sid)
            return

        with room_lock:
            room = rooms.get(room_code)
            if not room:
                socketio.emit("room_error", {"error": "Room not found"}, to=request.sid)
                return

            if user_id not in room.members:
                fallback_name = sanitize_name(session.get("user_name", "Guest"))
                room.members[user_id] = {
                    "id": user_id,
                    "name": fallback_name,
                    "joined_at": int(time.time()),
                }
                add_system_message(room, f"{fallback_name} da ket noi websocket.")

        join_room(f"user:{user_id}")
        join_room(f"room:{room_code}")
        emit_room_state(room_code)

    return app, socketio


app, socketio = make_app()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)

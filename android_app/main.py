from __future__ import annotations

import threading
from typing import Dict, List

import requests
import socketio
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout


KV = """
<RootUI>:
    orientation: "vertical"
    padding: "12dp"
    spacing: "10dp"

    BoxLayout:
        orientation: "vertical"
        size_hint_y: None
        height: "230dp"
        spacing: "8dp"

        Label:
            text: "Python Chat Mobile"
            bold: True
            font_size: "22sp"
            size_hint_y: None
            height: "34dp"

        Label:
            text: root.status_text
            size_hint_y: None
            height: "24dp"
            color: (0.7, 0.9, 0.8, 1)

        TextInput:
            id: base_url
            hint_text: "Server URL, vd: http://192.168.1.10:5000"
            text: "http://127.0.0.1:5000"
            multiline: False
            size_hint_y: None
            height: "40dp"

        TextInput:
            id: name_input
            hint_text: "Ten cua ban"
            multiline: False
            size_hint_y: None
            height: "40dp"

        BoxLayout:
            spacing: "8dp"
            size_hint_y: None
            height: "40dp"

            Button:
                text: "Tao room"
                on_release: root.create_room()

            TextInput:
                id: room_input
                hint_text: "Ma room"
                multiline: False

            Button:
                text: "Join room"
                on_release: root.join_room()

    Label:
        text: root.room_text
        size_hint_y: None
        height: "24dp"

    ScrollView:
        do_scroll_x: False
        Label:
            id: chat_label
            text: root.chat_text
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
            valign: "top"

    BoxLayout:
        spacing: "8dp"
        size_hint_y: None
        height: "90dp"

        TextInput:
            id: msg_input
            hint_text: "Nhap tin nhan"
            multiline: True

        BoxLayout:
            orientation: "vertical"
            size_hint_x: None
            width: "120dp"
            spacing: "6dp"

            Button:
                text: "Gui"
                on_release: root.send_message()
            Button:
                text: "Refresh"
                on_release: root.fetch_state()
"""


class RootUI(BoxLayout):
    status_text = StringProperty("Nhap thong tin va tao/join room.")
    room_text = StringProperty("Room: -")
    chat_text = StringProperty("Chua co tin nhan.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.http = requests.Session()
        self.sio = socketio.Client(reconnection=True, logger=False, engineio_logger=False)
        self.current_room = ""
        self.current_user = ""
        self.base_url = ""
        self.members: List[Dict] = []
        self._bind_socket_events()

    def _bind_socket_events(self) -> None:
        @self.sio.on("state_update")
        def on_state_update(data):
            Clock.schedule_once(lambda _: self._apply_state(data), 0)

        @self.sio.on("room_error")
        def on_room_error(data):
            message = (data or {}).get("error", "Room error")
            Clock.schedule_once(lambda _: self._set_status(message), 0)

        @self.sio.on("disconnect")
        def on_disconnect():
            Clock.schedule_once(lambda _: self._set_status("WebSocket disconnected"), 0)

    def _set_status(self, text: str) -> None:
        self.status_text = text

    def _normalize_base(self) -> str:
        text = self.ids.base_url.text.strip()
        return text.rstrip("/")

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.http.cookies.get_dict().items())

    def _to_ws_url(self, base_url: str) -> str:
        if base_url.startswith("https://"):
            return "wss://" + base_url[8:]
        if base_url.startswith("http://"):
            return "ws://" + base_url[7:]
        return base_url

    def create_room(self) -> None:
        self._enter_room(action="create")

    def join_room(self) -> None:
        self._enter_room(action="join")

    def _enter_room(self, action: str) -> None:
        name = self.ids.name_input.text.strip()
        code = self.ids.room_input.text.strip().upper()
        base = self._normalize_base()
        if not name:
            self._set_status("Ban can nhap ten.")
            return
        if action == "join" and not code:
            self._set_status("Nhap ma room de join.")
            return
        if not base:
            self._set_status("Nhap server URL.")
            return

        self._set_status("Dang ket noi server...")
        threading.Thread(
            target=self._enter_room_worker,
            args=(base, name, code, action),
            daemon=True,
        ).start()

    def _enter_room_worker(self, base: str, name: str, code: str, action: str) -> None:
        try:
            endpoint = "/api/mobile/create" if action == "create" else "/api/mobile/join"
            payload = {"name": name}
            if action == "join":
                payload["code"] = code
            resp = self.http.post(f"{base}{endpoint}", json=payload, timeout=12)
            if resp.status_code != 200:
                detail = resp.json().get("error", f"HTTP {resp.status_code}")
                Clock.schedule_once(lambda _: self._set_status(f"Loi: {detail}"), 0)
                return
            data = resp.json()
            room_code = data["room_code"]
            Clock.schedule_once(lambda _: self._on_room_entered(base, room_code), 0)
        except Exception as exc:  # noqa: BLE001
            Clock.schedule_once(lambda _: self._set_status(f"Ket noi that bai: {exc}"), 0)

    def _on_room_entered(self, base: str, room_code: str) -> None:
        self.base_url = base
        self.current_room = room_code
        self.room_text = f"Room: {room_code}"
        self._set_status("Da vao room. Dang mo websocket...")
        self._connect_socket()
        self.fetch_state()

    def _connect_socket(self) -> None:
        try:
            if self.sio.connected:
                self.sio.disconnect()
            cookie = self._cookie_header()
            headers = {"Cookie": cookie} if cookie else {}
            self.sio.connect(
                self.base_url,
                headers=headers,
                transports=["websocket", "polling"],
                wait_timeout=10,
            )
            self.sio.emit("join_room", {"code": self.current_room})
            self._set_status("Dang online.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"WebSocket loi: {exc}")

    def fetch_state(self) -> None:
        if not self.current_room or not self.base_url:
            return
        threading.Thread(target=self._fetch_state_worker, daemon=True).start()

    def _fetch_state_worker(self) -> None:
        try:
            resp = self.http.get(f"{self.base_url}/api/room/{self.current_room}/state", timeout=10)
            if resp.status_code != 200:
                return
            data = resp.json()
            Clock.schedule_once(lambda _: self._apply_state(data), 0)
        except Exception:
            return

    def _apply_state(self, state: Dict) -> None:
        self.current_user = state.get("current_user_id", "")
        self.members = state.get("members", [])
        members_txt = ", ".join(m["name"] for m in self.members) or "-"

        lines = [f"[Members] {members_txt}", ""]
        for item in state.get("messages", []):
            sender = item.get("sender", "?")
            text = item.get("text", "")
            lines.append(f"{sender}: {text}")
        self.chat_text = "\n".join(lines) if lines else "Chua co tin nhan."
        self._set_status(f"Online - {len(self.members)} members")

    def send_message(self) -> None:
        text = self.ids.msg_input.text.strip()
        if not text:
            return
        if not self.current_room or not self.base_url:
            self._set_status("Chua vao room.")
            return
        self.ids.msg_input.text = ""
        threading.Thread(target=self._send_message_worker, args=(text,), daemon=True).start()

    def _send_message_worker(self, text: str) -> None:
        try:
            resp = self.http.post(
                f"{self.base_url}/api/room/{self.current_room}/message",
                json={"text": text},
                timeout=10,
            )
            if resp.status_code != 200:
                detail = resp.json().get("error", f"HTTP {resp.status_code}")
                Clock.schedule_once(lambda _: self._set_status(f"Gui that bai: {detail}"), 0)
        except Exception as exc:  # noqa: BLE001
            Clock.schedule_once(lambda _: self._set_status(f"Gui that bai: {exc}"), 0)


class ChatMobileApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootUI()


if __name__ == "__main__":
    ChatMobileApp().run()

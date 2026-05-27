PRESET_DEFS = {
    "wave": {"name": "wave", "motion_id": 1002, "area_id": 2, "label": "右手挥手"},
    "wave_left": {"name": "wave_left", "motion_id": 1002, "area_id": 1, "label": "左手挥手"},
    "handshake": {"name": "handshake", "motion_id": 1003, "area_id": 2, "label": "右手握手"},
    "handshake_left": {
        "name": "handshake_left",
        "motion_id": 1003,
        "area_id": 1,
        "label": "左手握手",
    },
    "raise_hand": {"name": "raise_hand", "motion_id": 1001, "area_id": 2, "label": "右手举手"},
    "raise_hand_left": {
        "name": "raise_hand_left",
        "motion_id": 1001,
        "area_id": 1,
        "label": "左手举手",
    },
    "kiss": {"name": "kiss", "motion_id": 1004, "area_id": 2, "label": "右手飞吻"},
    "kiss_left": {"name": "kiss_left", "motion_id": 1004, "area_id": 1, "label": "左手飞吻"},
    "salute": {"name": "salute", "motion_id": 1013, "area_id": 2, "label": "右手敬礼"},
    "salute_left": {"name": "salute_left", "motion_id": 1013, "area_id": 1, "label": "左手敬礼"},
    "clap": {"name": "clap", "motion_id": 3017, "area_id": 11, "label": "鼓掌"},
    "cheer": {"name": "cheer", "motion_id": 3011, "area_id": 11, "label": "加油"},
    "bow": {"name": "bow", "motion_id": 3001, "area_id": 11, "label": "鞠躬"},
    "dance": {"name": "dance", "motion_id": 3007, "area_id": 11, "label": "动感光波"},
}

ACTION_ALIASES = {
    "start_dance": "preset.run",
    "start_dancing": "preset.run",
    "dance_start": "preset.run",
    "tts": "voice.tts",
    "say": "voice.tts",
    "speak": "voice.tts",
    "说话": "voice.tts",
    "播报": "voice.tts",
    "move": "motion.move",
    "move_forward": "motion.move",
    "move_backward": "motion.move",
    "turn_left": "motion.move",
    "turn_right": "motion.move",
    "前进": "motion.move",
    "后退": "motion.move",
    "左转": "motion.move",
    "右转": "motion.move",
    "走一步": "motion.move",
    "快走一步": "motion.move",
    "半步": "motion.move",
    "后退一步": "motion.move",
    "后退半步": "motion.move",
    "左移一步": "motion.move",
    "右移一步": "motion.move",
    "左移半步": "motion.move",
    "右移半步": "motion.move",
    "左转15": "motion.move",
    "右转15": "motion.move",
    "左转15°": "motion.move",
    "右转15°": "motion.move",
    "左转30": "motion.move",
    "右转30": "motion.move",
    "左转30°": "motion.move",
    "右转30°": "motion.move",
    "左转90": "motion.move",
    "右转90": "motion.move",
    "左转90°": "motion.move",
    "右转90°": "motion.move",
    "stop": "motion.stop",
    "halt": "motion.stop",
    "停止": "motion.stop",
    "刹车": "motion.stop",
    "wave": "preset.run",
    "handshake": "preset.run",
    "raise_hand": "preset.run",
    "kiss": "preset.run",
    "salute": "preset.run",
    "clap": "preset.run",
    "cheer": "preset.run",
    "bow": "preset.run",
    "dance": "preset.run",
    "wave_left": "preset.run",
    "handshake_left": "preset.run",
    "raise_hand_left": "preset.run",
    "kiss_left": "preset.run",
    "salute_left": "preset.run",
    "挥手": "preset.run",
    "握手": "preset.run",
    "举手": "preset.run",
    "飞吻": "preset.run",
    "敬礼": "preset.run",
    "鼓掌": "preset.run",
    "加油": "preset.run",
    "鞠躬": "preset.run",
    "跳舞": "preset.run",
    "左手挥手": "preset.run",
    "左手握手": "preset.run",
    "左手举手": "preset.run",
    "左手飞吻": "preset.run",
    "左手敬礼": "preset.run",
    "右手挥手": "preset.run",
    "右手握手": "preset.run",
    "右手举手": "preset.run",
    "右手飞吻": "preset.run",
    "右手敬礼": "preset.run",
}

PRESET_ALIASES = {
    "wave": "wave",
    "挥手": "wave",
    "右手挥手": "wave",
    "wave_left": "wave_left",
    "left_wave": "wave_left",
    "左手挥手": "wave_left",
    "handshake": "handshake",
    "握手": "handshake",
    "右手握手": "handshake",
    "handshake_left": "handshake_left",
    "left_handshake": "handshake_left",
    "左手握手": "handshake_left",
    "raise_hand": "raise_hand",
    "举手": "raise_hand",
    "右手举手": "raise_hand",
    "raise_hand_left": "raise_hand_left",
    "left_raise_hand": "raise_hand_left",
    "左手举手": "raise_hand_left",
    "kiss": "kiss",
    "飞吻": "kiss",
    "右手飞吻": "kiss",
    "kiss_left": "kiss_left",
    "left_kiss": "kiss_left",
    "左手飞吻": "kiss_left",
    "salute": "salute",
    "敬礼": "salute",
    "右手敬礼": "salute",
    "salute_left": "salute_left",
    "left_salute": "salute_left",
    "左手敬礼": "salute_left",
    "clap": "clap",
    "鼓掌": "clap",
    "cheer": "cheer",
    "加油": "cheer",
    "bow": "bow",
    "鞠躬": "bow",
    "dance": "dance",
    "start_dance": "dance",
    "start_dancing": "dance",
    "dance_start": "dance",
    "跳舞": "dance",
}


def canonical_action(action: str) -> str:
    value = str(action or "").strip()
    return ACTION_ALIASES.get(value, value)


def to_int(value):
    try:
        if value in ("", None):
            return None
        return int(value)
    except Exception:
        return None


def to_bool(value, default: bool = False) -> bool:
    if value in ("", None):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_preset(action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    motion_id = to_int(payload.get("motion_id"))
    area_id = to_int(payload.get("area_id"))
    interrupt = to_bool(payload.get("interrupt"), False)
    name = str(
        payload.get("name")
        or payload.get("preset")
        or payload.get("action_name")
        or payload.get("keyword")
        or action
        or ""
    ).strip()
    if motion_id is not None and area_id is not None:
        return {
            "name": name or "custom",
            "motion_id": motion_id,
            "area_id": area_id,
            "interrupt": interrupt,
            "label": name or "custom",
        }
    preset_name = PRESET_ALIASES.get(name)
    if not preset_name:
        return None
    preset = PRESET_DEFS[preset_name]
    return {**preset, "interrupt": interrupt}

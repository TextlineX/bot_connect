import math


MOTION_PRESETS: dict[str, dict] = {
    # 步态/微动（开环：速度 + 时长）
    "step_fast": {"label": "快走一步", "linear": 0.35, "lateral": 0.0, "angular": 0.0, "duration": 0.45, "pause_after": 0.15},
    "step": {"label": "走一步", "linear": 0.25, "lateral": 0.0, "angular": 0.0, "duration": 0.55, "pause_after": 0.15},
    "half_step": {"label": "半步", "linear": 0.25, "lateral": 0.0, "angular": 0.0, "duration": 0.28, "pause_after": 0.12},
    "step_back": {"label": "后退一步", "linear": -0.22, "lateral": 0.0, "angular": 0.0, "duration": 0.55, "pause_after": 0.15},
    "half_step_back": {"label": "后退半步", "linear": -0.22, "lateral": 0.0, "angular": 0.0, "duration": 0.28, "pause_after": 0.12},
    "strafe_left_step": {"label": "左移一步", "linear": 0.0, "lateral": 0.25, "angular": 0.0, "duration": 0.55, "pause_after": 0.12},
    "strafe_right_step": {"label": "右移一步", "linear": 0.0, "lateral": -0.25, "angular": 0.0, "duration": 0.55, "pause_after": 0.12},
    "strafe_left_half": {"label": "左移半步", "linear": 0.0, "lateral": 0.25, "angular": 0.0, "duration": 0.28, "pause_after": 0.10},
    "strafe_right_half": {"label": "右移半步", "linear": 0.0, "lateral": -0.25, "angular": 0.0, "duration": 0.28, "pause_after": 0.10},
    # 原地小角度转向（开环：角速度 + 角度）
    "turn_left_15": {"label": "左转15°", "linear": 0.0, "lateral": 0.0, "angular": 0.9, "angle_deg": 15, "pause_after": 0.15},
    "turn_right_15": {"label": "右转15°", "linear": 0.0, "lateral": 0.0, "angular": -0.9, "angle_deg": 15, "pause_after": 0.15},
    "turn_left_30": {"label": "左转30°", "linear": 0.0, "lateral": 0.0, "angular": 0.9, "angle_deg": 30, "pause_after": 0.15},
    "turn_right_30": {"label": "右转30°", "linear": 0.0, "lateral": 0.0, "angular": -0.9, "angle_deg": 30, "pause_after": 0.15},
    "turn_left_90": {"label": "左转90°", "linear": 0.0, "lateral": 0.0, "angular": 1.0, "angle_deg": 90, "pause_after": 0.20},
    "turn_right_90": {"label": "右转90°", "linear": 0.0, "lateral": 0.0, "angular": -1.0, "angle_deg": 90, "pause_after": 0.20},
}


MOTION_PRESET_ALIASES: dict[str, str] = {
    "走一步": "step",
    "快走一步": "step_fast",
    "半步": "half_step",
    "后退一步": "step_back",
    "后退半步": "half_step_back",
    "左移一步": "strafe_left_step",
    "右移一步": "strafe_right_step",
    "左移半步": "strafe_left_half",
    "右移半步": "strafe_right_half",
    "左转15": "turn_left_15",
    "右转15": "turn_right_15",
    "左转30": "turn_left_30",
    "右转30": "turn_right_30",
    "左转90": "turn_left_90",
    "右转90": "turn_right_90",
    "左小转": "turn_left_15",
    "右小转": "turn_right_15",
}


def _to_float(value, default: float | None = None) -> float | None:
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value, default: int | None = None) -> int | None:
    try:
        if value in ("", None):
            return default
        return int(value)
    except Exception:
        return default


def resolve_motion_preset_name(value: str | None) -> str | None:
    name = str(value or "").strip()
    if not name:
        return None
    if name in MOTION_PRESETS:
        return name
    return MOTION_PRESET_ALIASES.get(name)


def _compute_duration(
    *,
    duration: float | None,
    distance_m: float | None,
    linear: float,
    angle_rad: float | None,
    angular: float,
) -> float | None:
    if duration and duration > 0:
        return float(duration)
    if distance_m is not None and abs(linear) > 1e-6:
        return float(abs(distance_m) / abs(linear))
    if angle_rad is not None and abs(angular) > 1e-6:
        return float(abs(angle_rad) / abs(angular))
    return None


def resolve_motion_command(payload: dict | None) -> dict:
    """
    将前端/WS payload 解析成统一的移动指令：
    - linear/lateral/angular (m/s, m/s, rad/s)
    - duration (sec，可空；空表示持续速度控制)
    - label/preset (可选，用于 UI/日志)
    """
    payload = payload or {}

    # 直接脚本（高级用法）：[{linear,lateral,angular,duration,preset}, ...]
    raw_script = payload.get("script")
    if isinstance(raw_script, list):
        script = []
        for raw in raw_script:
            if not isinstance(raw, dict):
                continue
            seg = dict(raw)
            seg.pop("script", None)
            seg_cmd = resolve_motion_command(seg)
            seg_duration = seg_cmd.get("duration")
            if seg_duration is None:
                seg_duration = _to_float(seg.get("duration"), 0.0) or 0.0
            script.append(
                {
                    "linear": float(seg_cmd.get("linear") or 0.0),
                    "lateral": float(seg_cmd.get("lateral") or 0.0),
                    "angular": float(seg_cmd.get("angular") or 0.0),
                    "duration": float(seg_duration),
                    "label": seg_cmd.get("label") or seg.get("label"),
                }
            )
        return {
            "linear": 0.0,
            "lateral": 0.0,
            "angular": 0.0,
            "duration": None,
            "preset": None,
            "label": payload.get("label"),
            "raw_preset": None,
            "script": script,
        }

    preset_raw = (
        payload.get("motion_preset")
        or payload.get("preset")
        or payload.get("macro")
        or payload.get("pattern")
    )
    preset_name = resolve_motion_preset_name(preset_raw)

    # 兼容：有人可能会用 name 字段传 motion preset
    if not preset_name:
        maybe_name = payload.get("name")
        if maybe_name and str(maybe_name).strip() in MOTION_PRESETS and payload.get("motion_id") in (None, ""):
            preset_name = str(maybe_name).strip()

    preset = MOTION_PRESETS.get(preset_name) if preset_name else None

    # 基础速度（payload 显式值优先）
    linear = _to_float(payload.get("linear"), None)
    lateral = _to_float(payload.get("lateral"), None)
    angular = _to_float(payload.get("angular"), None)
    if preset:
        if linear is None:
            linear = float(preset.get("linear", 0.0))
        if lateral is None:
            lateral = float(preset.get("lateral", 0.0))
        if angular is None:
            angular = float(preset.get("angular", 0.0))
    linear = float(linear or 0.0)
    lateral = float(lateral or 0.0)
    angular = float(angular or 0.0)

    # 持续/定时控制
    duration = _to_float(payload.get("duration"), None)
    if duration is None:
        duration = _to_float(payload.get("duration_sec"), None)

    distance_m = _to_float(payload.get("distance_m"), None)
    if distance_m is None:
        distance_m = _to_float(payload.get("distance"), None)

    angle_deg = _to_float(payload.get("angle_deg"), None)
    angle_rad = _to_float(payload.get("angle_rad"), None)
    if angle_rad is None and angle_deg is not None:
        angle_rad = float(angle_deg) * math.pi / 180.0

    if preset and angle_rad is None and preset.get("angle_deg") is not None:
        angle_rad = float(preset["angle_deg"]) * math.pi / 180.0
    if preset and duration is None and preset.get("duration") is not None:
        duration = _to_float(preset.get("duration"), None)

    duration = _compute_duration(
        duration=duration,
        distance_m=distance_m,
        linear=linear,
        angle_rad=angle_rad,
        angular=angular,
    )

    repeat = _to_int(payload.get("repeat"), None)
    if repeat is None:
        repeat = _to_int(payload.get("times"), None)
    repeat = int(repeat or 1)
    if repeat < 1:
        repeat = 1
    pause_after = _to_float(payload.get("pause_after"), None)
    if pause_after is None and preset and preset.get("pause_after") is not None:
        pause_after = _to_float(preset.get("pause_after"), None)

    script = None
    if duration is not None and pause_after is not None and pause_after > 0:
        script = []
        for _ in range(repeat):
            script.append(
                {
                    "linear": float(linear),
                    "lateral": float(lateral),
                    "angular": float(angular),
                    "duration": float(duration),
                    "angle_rad": float(angle_rad) if angle_rad is not None else None,
                    "label": (preset.get("label") if preset else None) or "move",
                }
            )
            script.append(
                {
                    "linear": 0.0,
                    "lateral": 0.0,
                    "angular": 0.0,
                    "duration": float(pause_after),
                    "angle_rad": None,
                    "label": "pause",
                }
            )
    elif duration is not None and repeat > 1:
        duration = float(duration) * repeat

    label = None
    if preset:
        label = preset.get("label") or preset_name

    return {
        "linear": float(linear),
        "lateral": float(lateral),
        "angular": float(angular),
        "duration": float(duration) if duration is not None else None,
        "angle_rad": float(angle_rad) if angle_rad is not None else None,
        "preset": preset_name,
        "label": label,
        "raw_preset": str(preset_raw).strip() if preset_raw not in (None, "") else None,
        "script": script,
    }

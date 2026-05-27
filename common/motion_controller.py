import os
import threading
import time
from typing import Any


def _to_float(value, default: float) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def _to_str(value, default: str) -> str:
    if value in ("", None):
        return default
    return str(value)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _clamp_abs(value: float, max_abs: float) -> float:
    return _clamp(float(value), -abs(max_abs), abs(max_abs))


def _step_towards(current: float, target: float, max_delta: float) -> float:
    delta = target - current
    if delta > max_delta:
        return current + max_delta
    if delta < -max_delta:
        return current - max_delta
    return target


def _wrap_pi(angle: float) -> float:
    while angle > 3.141592653589793:
        angle -= 2.0 * 3.141592653589793
    while angle < -3.141592653589793:
        angle += 2.0 * 3.141592653589793
    return angle


def _quat_to_yaw(x: float, y: float, z: float, w: float) -> float:
    # yaw (z-axis rotation) from quaternion
    # Reference: standard conversion (roll/pitch/yaw), yaw = atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
    import math

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class MotionController:
    """
    统一“运动输出”模块：
    - `cmd_vel`：geometry_msgs/Twist -> /cmd_vel
    - `mc_locomotion`：aimdk_msgs/McLocomotionVelocity -> /aima/mc/locomotion/velocity（含输入源注册）

    核心能力：
    - 定频发布（解决只发一次导致底层超时停止/抖动的问题）
    - deadman 超时自动刹停
    - 速度限幅 + 加速度斜坡（避免突变）
    - 定时动作（duration）自动停止，可被新指令/stop 打断
    """

    def __init__(self, robot_id: str, sim_mode: bool = False):
        self.robot_id = str(robot_id or "robot").strip() or "robot"
        self.sim_mode = bool(sim_mode)

        transport = str(os.getenv("MOTION_TRANSPORT", "cmd_vel")).strip().lower()
        if transport in {"mc", "mc_locomotion", "aimdk", "aimdk_mc"}:
            transport = "mc_locomotion"
        if transport not in {"cmd_vel", "mc_locomotion"}:
            transport = "cmd_vel"
        self.transport = transport

        self.pub_hz = _to_float(os.getenv("MOTION_PUB_HZ"), 0.0)
        if self.pub_hz <= 0:
            self.pub_hz = 50.0 if self.transport == "mc_locomotion" else 20.0

        self.command_timeout_sec = _to_float(os.getenv("MOTION_CMD_TIMEOUT_SEC"), 1.0)

        self.max_linear = _to_float(os.getenv("MOTION_MAX_LINEAR"), 0.8)
        self.max_lateral = _to_float(os.getenv("MOTION_MAX_LATERAL"), 0.6)
        self.max_angular = _to_float(os.getenv("MOTION_MAX_ANGULAR"), 1.5)

        self.max_accel_linear = _to_float(os.getenv("MOTION_MAX_ACCEL_LINEAR"), 1.0)  # m/s^2
        self.max_accel_lateral = _to_float(os.getenv("MOTION_MAX_ACCEL_LATERAL"), 1.2)  # m/s^2
        self.max_accel_angular = _to_float(os.getenv("MOTION_MAX_ACCEL_ANGULAR"), 2.8)  # rad/s^2

        self.mc_source = str(os.getenv("MC_SOURCE_NAME") or f"bot_connect_{self.robot_id}").strip()
        self.mc_priority = int(_to_float(os.getenv("MC_SOURCE_PRIORITY"), 40))
        self.mc_timeout_ms = int(_to_float(os.getenv("MC_SOURCE_TIMEOUT_MS"), 1000))
        self.mc_auto_stand = str(os.getenv("MC_AUTO_SET_STAND", "0")).strip().lower() in {"1", "true", "yes", "on"}

        self.closed_loop_turn = str(os.getenv("MOTION_CLOSED_LOOP_TURN", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.imu_topic = str(os.getenv("MOTION_IMU_TOPIC", "/aima/hal/imu/torso/state")).strip()
        self.imu_qos_reliability = _to_str(os.getenv("MOTION_IMU_QOS_RELIABILITY"), "reliable").strip().lower()
        self.imu_qos_durability = _to_str(os.getenv("MOTION_IMU_QOS_DURABILITY"), "volatile").strip().lower()
        self.imu_qos_depth = int(_to_float(os.getenv("MOTION_IMU_QOS_DEPTH"), 10))
        if self.imu_qos_depth < 1:
            self.imu_qos_depth = 10

        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None

        self._node = None
        self._pub = None
        self._imu_sub = None
        self._mc_registered = False
        self._mc_last_register_error: str | None = None

        self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
        self._current = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
        self._last_cmd_at: float | None = None
        self._active_until: float | None = None
        self._active_label: str | None = None

        self._last_publish_at: float | None = None
        self._script: list[dict[str, Any]] | None = None
        self._script_index: int = 0
        self._script_segment_end_at: float | None = None
        self._script_label: str | None = None
        self._yaw: float | None = None
        self._yaw_at: float | None = None
        self._seg_start_yaw: float | None = None
        self._seg_target_delta_yaw: float | None = None
        self._estop: bool = False
        self._estop_at: float | None = None
        self._estop_reason: str | None = None

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        if self.sim_mode:
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._loop, name="motion-pub", daemon=True)
            self._thread.start()
            return True

        if not self._init_ros():
            # 无 ROS 时也允许跑在 sim 模式（至少让 WS 侧不报错）
            self.sim_mode = True
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._loop, name="motion-pub", daemon=True)
            self._thread.start()
            return True

        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="motion-pub", daemon=True)
        self._thread.start()
        return True

    def close(self):
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=2.0)
            except Exception:
                pass
        self._thread = None
        self._pub = None
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                pass
        self._node = None
        self._imu_sub = None

    def stop(self):
        with self._lock:
            self._script = None
            self._script_index = 0
            self._script_segment_end_at = None
            self._script_label = None
        self.command(0.0, 0.0, 0.0, duration=None, label="stop")

    def estop(self, reason: str | None = None):
        now = time.time()
        with self._lock:
            self._estop = True
            self._estop_at = now
            self._estop_reason = str(reason or "").strip() or None
            # 清空一切运动状态
            self._script = None
            self._script_index = 0
            self._script_segment_end_at = None
            self._script_label = None
            self._active_until = None
            self._active_label = "estop"
            self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
            self._current = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
            self._last_cmd_at = now

    def clear_estop(self):
        now = time.time()
        with self._lock:
            self._estop = False
            self._estop_at = None
            self._estop_reason = None
            self._active_label = None
            self._active_until = None
            self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
            self._current = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
            self._last_cmd_at = now

    def is_estopped(self) -> bool:
        with self._lock:
            return bool(self._estop)

    def command(
        self,
        linear: float,
        angular: float,
        lateral: float = 0.0,
        *,
        duration: float | None = None,
        label: str | None = None,
    ):
        now = time.time()
        with self._lock:
            if self._estop:
                # 急停态下忽略一切运动指令（除 stop/clear_estop 由上层处理）
                return
            self._script = None
            self._script_index = 0
            self._script_segment_end_at = None
            self._script_label = None
            self._last_cmd_at = now
            self._target = {
                "linear": _clamp_abs(float(linear), self.max_linear),
                "lateral": _clamp_abs(float(lateral), self.max_lateral),
                "angular": _clamp_abs(float(angular), self.max_angular),
            }
            self._active_label = label
            if duration is not None and duration > 0:
                self._active_until = now + float(duration)
            else:
                self._active_until = None

    def run_script(self, segments: list[dict[str, Any]], *, label: str | None = None):
        now = time.time()
        norm = []
        for seg in segments or []:
            if not isinstance(seg, dict):
                continue
            duration = _to_float(seg.get("duration"), 0.0)
            if duration <= 0:
                continue
            angle_rad = seg.get("angle_rad")
            try:
                if angle_rad in ("", None):
                    angle_rad = None
                else:
                    angle_rad = float(angle_rad)
            except Exception:
                angle_rad = None
            norm.append(
                {
                    "linear": _clamp_abs(_to_float(seg.get("linear"), 0.0), self.max_linear),
                    "lateral": _clamp_abs(_to_float(seg.get("lateral"), 0.0), self.max_lateral),
                    "angular": _clamp_abs(_to_float(seg.get("angular"), 0.0), self.max_angular),
                    "duration": float(duration),
                    "angle_rad": angle_rad,
                    "label": seg.get("label"),
                }
            )
        with self._lock:
            if self._estop:
                return
            self._script = norm if norm else None
            self._script_index = 0
            self._script_label = label
            self._active_until = None
            self._active_label = label
            self._last_cmd_at = now
            if self._script:
                first = self._script[0]
                self._target = {
                    "linear": float(first["linear"]),
                    "lateral": float(first["lateral"]),
                    "angular": float(first["angular"]),
                }
                self._script_segment_end_at = now + float(first["duration"])
                self._prepare_segment_closed_loop(first)
            else:
                self._script_segment_end_at = None

    def command_from_payload(self, payload: dict) -> dict:
        linear = _to_float(payload.get("linear"), 0.0)
        angular = _to_float(payload.get("angular"), 0.0)
        lateral = _to_float(payload.get("lateral"), 0.0)
        duration = payload.get("duration")
        duration = _to_float(duration, 0.0) if duration not in (None, "") else None
        label = payload.get("label")
        self.command(linear, angular, lateral, duration=duration, label=str(label) if label else None)
        return {"linear": linear, "lateral": lateral, "angular": angular, "duration": duration, "label": label}

    def status(self) -> dict:
        with self._lock:
            ros_ready = bool(self._node is not None and self._pub is not None and not self.sim_mode)
            return {
                "sim_mode": bool(self.sim_mode),
                "transport": self.transport,
                "pub_hz": self.pub_hz,
                "deadman_timeout_sec": self.command_timeout_sec,
                "ros": {
                    "ready": ros_ready,
                    "node": bool(self._node is not None),
                    "publisher": bool(self._pub is not None),
                },
                "estop": {
                    "active": bool(self._estop),
                    "reason": self._estop_reason,
                    "age_sec": (time.time() - self._estop_at) if self._estop_at else None,
                },
                "mc": {
                    "source": self.mc_source,
                    "registered": bool(self._mc_registered),
                    "last_register_error": self._mc_last_register_error,
                },
                "target": dict(self._target),
                "current": dict(self._current),
                "last_command_age_sec": (time.time() - self._last_cmd_at) if self._last_cmd_at else None,
                "active_until_age_sec": (self._active_until - time.time()) if self._active_until else None,
                "active_label": self._active_label,
                "script": {
                    "active": bool(self._script),
                    "label": self._script_label,
                    "index": self._script_index,
                    "len": len(self._script) if self._script else 0,
                    "segment_remaining_sec": (self._script_segment_end_at - time.time())
                    if self._script_segment_end_at
                    else None,
                },
                "feedback": {
                    "imu_topic": self.imu_topic,
                    "imu_qos": {
                        "reliability": self.imu_qos_reliability,
                        "durability": self.imu_qos_durability,
                        "depth": self.imu_qos_depth,
                    },
                    "yaw": self._yaw,
                    "yaw_age_sec": (time.time() - self._yaw_at) if self._yaw_at else None,
                    "closed_loop_turn": self.closed_loop_turn,
                    "seg_target_delta_yaw": self._seg_target_delta_yaw,
                },
            }

    # ---------------- ROS 侧实现 ----------------

    def _init_ros(self) -> bool:
        try:
            import rclpy  # type: ignore
            from rclpy.node import Node  # type: ignore
        except Exception:
            return False

        try:
            if not rclpy.ok():
                rclpy.init(args=None)
        except Exception:
            # 有些环境中 rclpy.ok/init 会抛异常，直接视为不可用
            return False

        class _Node(Node):
            pass

        try:
            self._node = _Node(f"bot_connect_motion_{self.robot_id}".replace("-", "_"))
        except Exception:
            return False

        if self.transport == "mc_locomotion":
            if not self._init_mc_publisher():
                # 如果 AimDK 不可用，则回退 cmd_vel
                self.transport = "cmd_vel"
        if self.transport == "cmd_vel":
            if not self._init_cmd_vel_publisher():
                return False

        self._init_imu_subscription()
        return True

    def _init_imu_subscription(self):
        if not self.closed_loop_turn:
            return
        try:
            from sensor_msgs.msg import Imu  # type: ignore
        except Exception:
            return
        del Imu

        qos = None
        try:
            from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy  # type: ignore

            qos = QoSProfile(depth=int(self.imu_qos_depth))
            if self.imu_qos_reliability in {"best_effort", "besteffort", "be"}:
                qos.reliability = ReliabilityPolicy.BEST_EFFORT
            else:
                qos.reliability = ReliabilityPolicy.RELIABLE
            if self.imu_qos_durability in {"transient_local", "transient", "tl"}:
                qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
            else:
                qos.durability = DurabilityPolicy.VOLATILE
        except Exception:
            qos = int(self.imu_qos_depth)

        try:
            self._imu_sub = self._node.create_subscription(  # type: ignore[attr-defined]
                __import__("sensor_msgs.msg", fromlist=["Imu"]).Imu,
                self.imu_topic,
                self._on_imu,
                qos,
            )
        except Exception:
            self._imu_sub = None

    def _on_imu(self, msg):
        try:
            o = msg.orientation
            yaw = _quat_to_yaw(float(o.x), float(o.y), float(o.z), float(o.w))
        except Exception:
            return
        now = time.time()
        with self._lock:
            self._yaw = float(yaw)
            self._yaw_at = now

    def _init_cmd_vel_publisher(self) -> bool:
        try:
            from geometry_msgs.msg import Twist  # type: ignore
        except Exception:
            return False
        del Twist
        try:
            self._pub = self._node.create_publisher(  # type: ignore[attr-defined]
                __import__("geometry_msgs.msg", fromlist=["Twist"]).Twist,
                "/cmd_vel",
                10,
            )
            return True
        except Exception:
            return False

    def _init_mc_publisher(self) -> bool:
        try:
            from aimdk_msgs.msg import McLocomotionVelocity  # type: ignore
        except Exception:
            return False
        del McLocomotionVelocity
        try:
            self._pub = self._node.create_publisher(  # type: ignore[attr-defined]
                __import__("aimdk_msgs.msg", fromlist=["McLocomotionVelocity"]).McLocomotionVelocity,
                "/aima/mc/locomotion/velocity",
                10,
            )
        except Exception:
            return False

        self._try_register_mc_input_source()
        if self.mc_auto_stand:
            self._try_set_mc_action("STAND_DEFAULT")
        return True

    def _try_register_mc_input_source(self):
        self._mc_registered = False
        self._mc_last_register_error = None
        try:
            import rclpy  # type: ignore
            from aimdk_msgs.srv import SetMcInputSource  # type: ignore
        except Exception as exc:
            self._mc_last_register_error = f"import failed: {exc}"
            return

        try:
            client = self._node.create_client(SetMcInputSource, "/aimdk_5Fmsgs/srv/SetMcInputSource")  # type: ignore[attr-defined]
        except Exception as exc:
            self._mc_last_register_error = f"create_client failed: {exc}"
            return

        start = time.time()
        while not client.wait_for_service(timeout_sec=0.5):
            if time.time() - start > 8.0:
                self._mc_last_register_error = "wait_for_service timeout"
                return

        try:
            req = SetMcInputSource.Request()
            req.action.value = 1001  # ADD
            req.input_source.name = self.mc_source
            req.input_source.priority = int(self.mc_priority)
            req.input_source.timeout = int(self.mc_timeout_ms)
            ok = False
            for i in range(8):
                req.request.header.stamp = self._node.get_clock().now().to_msg()  # type: ignore[attr-defined]
                future = client.call_async(req)
                rclpy.spin_until_future_complete(self._node, future, timeout_sec=0.25)
                if future.done():
                    ok = True
                    break
                time.sleep(0.02)
            if not ok:
                self._mc_last_register_error = "service call timeout"
                return
            resp = future.result()
            code = getattr(getattr(resp, "response", None), "header", None)
            code = getattr(code, "code", None)
            if code == 0:
                self._mc_registered = True
                return
            self._mc_last_register_error = f"register failed code={code}"
        except Exception as exc:
            self._mc_last_register_error = f"register exception: {exc}"

    def _try_set_mc_action(self, action_desc: str):
        try:
            import rclpy  # type: ignore
            from aimdk_msgs.srv import SetMcAction  # type: ignore
            from aimdk_msgs.msg import McActionCommand, RequestHeader  # type: ignore
        except Exception:
            return

        try:
            client = self._node.create_client(SetMcAction, "/aimdk_5Fmsgs/srv/SetMcAction")  # type: ignore[attr-defined]
        except Exception:
            return

        start = time.time()
        while not client.wait_for_service(timeout_sec=0.5):
            if time.time() - start > 6.0:
                return

        try:
            req = SetMcAction.Request()
            req.header = RequestHeader()
            cmd = McActionCommand()
            cmd.action_desc = str(action_desc)
            req.command = cmd
            for _ in range(8):
                req.header.stamp = self._node.get_clock().now().to_msg()  # type: ignore[attr-defined]
                future = client.call_async(req)
                rclpy.spin_until_future_complete(self._node, future, timeout_sec=0.25)
                if future.done():
                    break
                time.sleep(0.02)
        except Exception:
            return

    # ---------------- 发布循环 ----------------

    def _prepare_segment_closed_loop(self, seg: dict[str, Any]):
        # 仅对“纯转向段”做闭环：存在 angle_rad 且 angular 非 0
        if not self.closed_loop_turn:
            self._seg_start_yaw = None
            self._seg_target_delta_yaw = None
            return
        angle_rad = seg.get("angle_rad")
        try:
            if angle_rad in ("", None):
                angle_rad = None
            else:
                angle_rad = float(angle_rad)
        except Exception:
            angle_rad = None
        angular = float(seg.get("angular") or 0.0)
        if angle_rad is None or abs(angular) < 1e-4:
            self._seg_start_yaw = None
            self._seg_target_delta_yaw = None
            return
        # 记录段开始时 yaw（可能尚未收到 IMU，则延迟到 loop 里第一次有 yaw 时再置）
        self._seg_start_yaw = None
        self._seg_target_delta_yaw = float(angle_rad)

    def _loop(self):
        period = 1.0 / max(1.0, float(self.pub_hz))
        max_delta_linear = abs(self.max_accel_linear) * period
        max_delta_lateral = abs(self.max_accel_lateral) * period
        max_delta_angular = abs(self.max_accel_angular) * period

        while not self._stop_evt.is_set():
            now = time.time()
            if not self.sim_mode and self._node is not None:
                try:
                    import rclpy  # type: ignore

                    rclpy.spin_once(self._node, timeout_sec=0.0)
                except Exception:
                    pass
            with self._lock:
                if self._estop:
                    # 急停：立即输出 0，不走斜坡/脚本/定时动作
                    self._script = None
                    self._script_index = 0
                    self._script_segment_end_at = None
                    self._script_label = None
                    self._active_until = None
                    self._active_label = "estop"
                    self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
                    self._current = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
                    self._last_publish_at = now
                    estop_now = True
                else:
                    estop_now = False
                if self._script:
                    # 闭环：如果是转向段，优先按 IMU yaw 达成条件切段
                    if self._seg_target_delta_yaw is not None and self._yaw is not None and self._yaw_at:
                        # 如果段刚开始还没记录 start_yaw，则在首次拿到 yaw 时记录
                        if self._seg_start_yaw is None:
                            self._seg_start_yaw = float(self._yaw)
                        else:
                            delta = _wrap_pi(float(self._yaw) - float(self._seg_start_yaw))
                            target = float(self._seg_target_delta_yaw)
                            reached = (delta >= target) if target > 0 else (delta <= target)
                            # IMU 长时间不更新时，不做闭环判断
                            if reached and (time.time() - self._yaw_at) < 0.5:
                                self._script_segment_end_at = now  # 触发立即切段

                    # 脚本段切换
                    if self._script_segment_end_at and now >= self._script_segment_end_at:
                        self._script_index += 1
                        if self._script_index >= len(self._script):
                            self._script = None
                            self._script_index = 0
                            self._script_segment_end_at = None
                            self._script_label = None
                            self._active_label = None
                            self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
                            self._seg_start_yaw = None
                            self._seg_target_delta_yaw = None
                        else:
                            seg = self._script[self._script_index]
                            self._target = {
                                "linear": float(seg["linear"]),
                                "lateral": float(seg["lateral"]),
                                "angular": float(seg["angular"]),
                            }
                            self._script_segment_end_at = now + float(seg["duration"])
                            self._prepare_segment_closed_loop(seg)

                # 定时动作结束
                if not self._script and self._active_until and now >= self._active_until:
                    self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}
                    self._active_until = None
                    self._active_label = None

                # deadman：长时间未收到指令 -> 刹停
                if (
                    not self._script
                    and self._last_cmd_at
                    and (now - self._last_cmd_at) > self.command_timeout_sec
                    and not self._active_until
                ):
                    self._target = {"linear": 0.0, "lateral": 0.0, "angular": 0.0}

                tgt = dict(self._target)
                cur = dict(self._current)

            if estop_now:
                self._publish(0.0, 0.0, 0.0)
                time.sleep(period)
                continue

            # 斜坡
            next_linear = _step_towards(cur["linear"], tgt["linear"], max_delta_linear)
            next_lateral = _step_towards(cur["lateral"], tgt["lateral"], max_delta_lateral)
            next_angular = _step_towards(cur["angular"], tgt["angular"], max_delta_angular)

            # 限幅（再次确保安全）
            next_linear = _clamp_abs(next_linear, self.max_linear)
            next_lateral = _clamp_abs(next_lateral, self.max_lateral)
            next_angular = _clamp_abs(next_angular, self.max_angular)

            with self._lock:
                self._current = {"linear": next_linear, "lateral": next_lateral, "angular": next_angular}
                self._last_publish_at = now

            self._publish(next_linear, next_lateral, next_angular)
            time.sleep(period)

        # 退出前尽力刹停
        self._publish(0.0, 0.0, 0.0)

    def _publish(self, linear: float, lateral: float, angular: float):
        if self.sim_mode or not self._pub or not self._node:
            return

        if self.transport == "cmd_vel":
            try:
                from geometry_msgs.msg import Twist  # type: ignore

                msg = Twist()
                msg.linear.x = float(linear)
                msg.linear.y = float(lateral)
                msg.angular.z = float(angular)
                self._pub.publish(msg)
            except Exception:
                return
            return

        if self.transport == "mc_locomotion":
            try:
                from aimdk_msgs.msg import McLocomotionVelocity, MessageHeader  # type: ignore

                msg = McLocomotionVelocity()
                msg.header = MessageHeader()
                msg.header.stamp = self._node.get_clock().now().to_msg()  # type: ignore[attr-defined]
                msg.source = self.mc_source
                msg.forward_velocity = float(linear)
                msg.lateral_velocity = float(lateral)
                msg.angular_velocity = float(angular)
                self._pub.publish(msg)
            except Exception:
                return

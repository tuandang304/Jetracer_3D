#!/usr/bin/env python3
"""
Giả lập tối thiểu `rospy` và các gói message ROS.

Mục đích: chạy được `main_speed_track.py` trên Windows (KHÔNG cần ROS, KHÔNG cần
Ubuntu/WSL) để tune bám line trong Donkey Sim.

CẢNH BÁO: File này chỉ dành cho môi trường mô phỏng trên laptop.
KHÔNG bao giờ dùng nó trên xe thật — trên xe phải là rospy thật của ROS Melodic.

Cách dùng: gọi install() TRƯỚC khi import bất kỳ module nào trong src/.
"""

import os
import sys
import time
import types
import threading

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ============================================================
# Ngoại lệ + trạng thái toàn cục
# ============================================================
class ROSInterruptException(Exception):
    pass


_shutdown = threading.Event()
_throttle_last = {}


# ============================================================
# Logging
# ============================================================
def force_utf8_console():
    """
    Console Windows mặc định dùng cp1252 → mọi log tiếng Việt sẽ ném
    UnicodeEncodeError và làm chết chương trình. Ép stdout/stderr sang UTF-8.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _emit(level, msg, args):
    if args:
        try:
            msg = msg % args
        except Exception:
            pass
    print("[%-5s] [%s] %s" % (level, time.strftime("%H:%M:%S"), msg))


def loginfo(msg, *args):
    _emit("INFO", msg, args)


def logwarn(msg, *args):
    _emit("WARN", msg, args)


def logerr(msg, *args):
    _emit("ERROR", msg, args)


def logdebug(msg, *args):
    pass


def _throttled(level, period, msg, args):
    key = (level, msg)
    now = time.time()
    if now - _throttle_last.get(key, 0.0) >= period:
        _throttle_last[key] = now
        _emit(level, msg, args)


def loginfo_throttle(period, msg, *args):
    _throttled("INFO", period, msg, args)


def logwarn_throttle(period, msg, *args):
    _throttled("WARN", period, msg, args)


def logerr_throttle(period, msg, *args):
    _throttled("ERROR", period, msg, args)


# ============================================================
# Vòng đời node
# ============================================================
def init_node(name, anonymous=False, **kwargs):
    loginfo("Khởi tạo node giả lập '%s' (chế độ Donkey Sim, không có ROS).", name)


def get_time():
    return time.time()


def is_shutdown():
    return _shutdown.is_set()


def signal_shutdown(reason=""):
    _shutdown.set()


def on_shutdown(callback):
    pass


def spin():
    while not is_shutdown():
        time.sleep(0.1)


class Rate(object):
    """Giữ nhịp vòng lặp giống rospy.Rate."""

    def __init__(self, hz):
        self.period = 1.0 / float(hz)
        self._next = time.time() + self.period

    def sleep(self):
        remaining = self._next - time.time()
        if remaining > 0:
            time.sleep(remaining)
            self._next += self.period
        else:
            # Đã trễ nhịp -> bỏ qua phần bù để không dồn nợ thời gian
            self._next = time.time() + self.period


# ============================================================
# Pub/Sub/Service giả (không làm gì — dữ liệu được bơm thẳng vào controller)
# ============================================================
class Subscriber(object):
    def __init__(self, topic, msg_type=None, callback=None, queue_size=None, **kwargs):
        self.topic = topic
        self.callback = callback

    def unregister(self):
        pass


class Publisher(object):
    def __init__(self, topic, msg_type=None, queue_size=None, **kwargs):
        self.topic = topic

    def publish(self, *args, **kwargs):
        pass

    def unregister(self):
        pass


class Service(object):
    def __init__(self, name, service_class=None, handler=None, **kwargs):
        self.name = name


class ServiceProxy(object):
    def __init__(self, name, service_class=None, **kwargs):
        self.name = name

    def __call__(self, *args, **kwargs):
        return None


class Time(object):
    @staticmethod
    def now():
        return get_time()


class Duration(object):
    def __init__(self, secs=0.0):
        self.secs = secs

    def to_sec(self):
        return self.secs


# ============================================================
# Message / Service classes tối giản
# ============================================================
class _Msg(object):
    _fields = {}

    def __init__(self, **kwargs):
        for name, default in self._fields.items():
            setattr(self, name, default() if callable(default) else default)
        for name, value in kwargs.items():
            setattr(self, name, value)


class LaserScan(_Msg):
    _fields = {
        "angle_min": 0.0, "angle_max": 0.0, "angle_increment": 0.0,
        "time_increment": 0.0, "scan_time": 0.0,
        "range_min": 0.0, "range_max": 0.0,
        "ranges": list, "intensities": list,
    }


class Image(_Msg):
    _fields = {
        "height": 0, "width": 0, "encoding": "bgr8",
        "is_bigendian": 0, "step": 0, "data": b"",
    }


class CompressedImage(_Msg):
    _fields = {"format": "jpeg", "data": b""}


class String(_Msg):
    _fields = {"data": ""}


class Bool(_Msg):
    _fields = {"data": False}


class SetBool(object):
    pass


class SetBoolResponse(_Msg):
    _fields = {"success": True, "message": ""}


# ============================================================
# Cài các module giả vào sys.modules
# ============================================================
def _make_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    # Gắn vào module cha để `import a.b.c as x` hoạt động
    if "." in name:
        parent_name, child_name = name.rsplit(".", 1)
        setattr(sys.modules[parent_name], child_name, module)
    return module


def _existing_rospy_is_real():
    """
    Phân biệt rospy thật của ROS với bản giả cũ nằm ngay trong repo
    (rospy.py ở thư mục gốc). Bản giả cũ sẽ bị thay thế, rospy thật thì không.
    """
    module = sys.modules.get("rospy")
    if module is None:
        try:
            import rospy as module  # noqa: F811
        except ImportError:
            return False
    path = os.path.abspath(getattr(module, "__file__", "") or "")
    return not path.startswith(REPO_ROOT)


def patch_cv2_findcontours():
    """
    Code viết cho OpenCV 3 (`_, contours, _ = cv2.findContours(...)`) — bắt buộc
    giữ nguyên vì xe thật chạy OpenCV 3.x. Trên laptop thường là OpenCV 4/5 chỉ
    trả 2 giá trị, nên ta bọc lại cho khớp thay vì sửa code chính.
    """
    import cv2
    if getattr(cv2.findContours, "_jetracer_compat", False):
        return
    original = cv2.findContours

    def find_contours_compat(*args, **kwargs):
        result = original(*args, **kwargs)
        if len(result) == 2:
            return None, result[0], result[1]
        return result

    find_contours_compat._jetracer_compat = True
    cv2.findContours = find_contours_compat


def install(quiet=False):
    """Cài rospy giả + các gói message. Trả về False nếu ROS thật đã có sẵn."""
    force_utf8_console()

    if _existing_rospy_is_real():
        return False

    patch_cv2_findcontours()

    rospy_module = types.ModuleType("rospy")
    for name in dir(sys.modules[__name__]):
        if not name.startswith("_"):
            setattr(rospy_module, name, getattr(sys.modules[__name__], name))
    sys.modules["rospy"] = rospy_module

    _make_module("sensor_msgs")
    _make_module("sensor_msgs.msg", LaserScan=LaserScan, Image=Image,
                 CompressedImage=CompressedImage)
    _make_module("std_msgs")
    _make_module("std_msgs.msg", String=String, Bool=Bool)
    _make_module("std_srvs")
    _make_module("std_srvs.srv", SetBool=SetBool, SetBoolResponse=SetBoolResponse)

    _install_optional_stubs()

    if not quiet:
        loginfo("Đã cài rospy giả lập — đang chạy ở chế độ mô phỏng, không có ROS.")
    return True


def _install_optional_stubs():
    """
    Thay thế các thư viện chỉ cần trên xe thật nếu máy chưa cài, để import
    main_speed_track.py không chết: onnxruntime, pyzbar, paho-mqtt, requests.
    """
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        class _NoSession(object):
            def __init__(self, *args, **kwargs):
                raise RuntimeError("onnxruntime chưa cài — bỏ qua YOLO trong sim.")
        _make_module("onnxruntime", InferenceSession=_NoSession)

    try:
        import pyzbar.pyzbar  # noqa: F401
    except ImportError:
        _make_module("pyzbar")
        _make_module("pyzbar.pyzbar", decode=lambda *a, **k: [])

    try:
        import paho.mqtt.client  # noqa: F401
    except ImportError:
        class _MqttClient(object):
            def __init__(self, *args, **kwargs):
                self.on_connect = None

            def connect(self, *args, **kwargs):
                raise RuntimeError("paho-mqtt chưa cài — bỏ qua MQTT trong sim.")

            def loop_start(self):
                pass

            def loop_stop(self):
                pass

            def disconnect(self):
                pass

            def publish(self, *args, **kwargs):
                pass
        _make_module("paho")
        _make_module("paho.mqtt")
        _make_module("paho.mqtt.client", Client=_MqttClient)

    try:
        import requests  # noqa: F401
    except ImportError:
        def _no_net(*args, **kwargs):
            raise RuntimeError("requests chưa cài — bỏ qua HTTP trong sim.")
        _make_module("requests", get=_no_net, post=_no_net)

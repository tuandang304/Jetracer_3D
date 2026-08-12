# -*- coding: utf-8 -*-
import os
import sys
import time
import cv2
import numpy as np
import onnxruntime as ort

def preprocess_onnx(cv_image):
    """
    Fast preprocessing for ONNX ResNet / JetRacer models.
    Converts BGR OpenCV image -> RGB float32 numpy array (1, 3, 224, 224) ImageNet normalized.
    """
    if cv_image.shape[:2] != (224, 224):
        cv_image = cv2.resize(cv_image, (224, 224))

    # BGR to RGB
    rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    
    # ImageNet Mean & Std
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    
    rgb = (rgb - mean) / std
    
    # HWC to CHW and add batch dimension
    tensor = rgb.transpose((2, 0, 1))[np.newaxis, ...]
    return tensor

def bgr8_to_jpeg(image, quality=75):
    """Helper to encode BGR image into JPEG bytes for HTML widget."""
    _, jpeg = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpeg.tobytes()

class JetRacerROSOnnxRunner(object):
    """
    ONNX Runtime accelerated ROS Runner for JetRacer Autonomous Road Following.
    Supports real-time ONNX inference, Stanley controller steering, dynamic throttle,
    FPS measurement, video recording, and Jupyter live UI callback.
    """
    def __init__(self, session, car, stanley=None,
                 k=2.5, throttle=0.20, brake_gain=0.10, bias=0.0, alpha=0.4,
                 video_path=None, video_fps=20.0, on_frame=None):
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.output_name = session.get_outputs()[0].name
        
        self.car = car
        self.stanley = stanley

        self.k_param = k
        self.throttle_param = throttle
        self.brake_gain_param = brake_gain
        self.bias_param = bias
        self.alpha_param = alpha

        self.running = False
        self.on_frame = on_frame

        # Performance / FPS tracking
        self.frame_count = 0
        self.last_time = time.time()
        self.fps = 0.0
        self.latency_ms = 0.0

        # Video recording setup
        self.video_path = video_path
        self.video_writer = None
        if video_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(video_path, fourcc, video_fps, (224, 224))

    def get_val(self, param):
        """Evaluate parameter if it is a lambda or return value directly."""
        return param() if callable(param) else param

    def image_callback(self, ros_image):
        """Callback executed for each ROS Camera frame."""
        t_start = time.time()
        
        # Convert ROS Image message to OpenCV BGR numpy array
        try:
            from cv_bridge import CvBridge
            bridge = CvBridge()
            cv_image = bridge.imgmsg_to_cv2(ros_image, desired_encoding='bgr8')
        except Exception:
            # Fallback direct buffer decoding if cv_bridge not available
            im_bytes = np.frombuffer(ros_image.data, dtype=np.uint8)
            cv_image = im_bytes.reshape((ros_image.height, ros_image.width, 3))

        if cv_image is None:
            return

        # Ensure image dimensions 224x224
        if cv_image.shape[:2] != (224, 224):
            cv_image = cv2.resize(cv_image, (224, 224))

        # Evaluate live dynamic slider values
        k_val = self.get_val(self.k_param)
        throttle_val = self.get_val(self.throttle_param)
        brake_gain_val = self.get_val(self.brake_gain_param)
        bias_val = self.get_val(self.bias_param)
        alpha_val = self.get_val(self.alpha_param)

        # 1. Fast ONNX Preprocessing & Inference
        input_tensor = preprocess_onnx(cv_image)
        outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
        coords = outputs[0][0]

        raw_x = float(coords[0])
        raw_y = float(coords[1]) if len(coords) > 1 else 0.0

        # 2. Control Output Calculation (Stanley or Proportional)
        smoothed_x = raw_x
        if self.stanley is not None:
            steering, dyn_throttle, smoothed_x = self.stanley.update(
                target_x=raw_x,
                target_y=raw_y,
                k=k_val,
                base_throttle=throttle_val,
                brake_gain=brake_gain_val,
                bias=bias_val,
                alpha=alpha_val
            )
        else:
            steering = float(np.clip(raw_x * k_val + bias_val, -1.0, 1.0))
            dyn_throttle = throttle_val

        # 3. Apply Steering & Throttle to JetRacer Hardware
        if self.running and self.car is not None:
            self.car.steering = steering
            self.car.throttle = dyn_throttle
        else:
            if self.car is not None:
                self.car.steering = 0.0
                self.car.throttle = 0.0

        # 4. Measure FPS & Latency
        t_end = time.time()
        self.latency_ms = (t_end - t_start) * 1000.0
        self.frame_count += 1
        if t_end - self.last_time >= 1.0:
            self.fps = self.frame_count / (t_end - self.last_time)
            self.frame_count = 0
            self.last_time = t_end

        # 5. Record Video Frame
        if self.video_writer is not None:
            self.video_writer.write(cv_image)

        # 6. Execute Live UI Callback
        if self.on_frame is not None:
            try:
                self.on_frame(
                    cv_image=cv_image,
                    raw_x=raw_x,
                    raw_y=raw_y,
                    smoothed_x=smoothed_x,
                    steering=steering,
                    dyn_throttle=dyn_throttle,
                    fps=self.fps,
                    latency_ms=self.latency_ms
                )
            except TypeError:
                self.on_frame(cv_image, raw_x, raw_y, smoothed_x, steering, dyn_throttle)

    def stop(self):
        """Stop car movement and release resources."""
        self.running = False
        if self.car is not None:
            self.car.throttle = 0.0
            self.car.steering = 0.0
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

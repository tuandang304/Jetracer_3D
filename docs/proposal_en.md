# RESEARCH PROPOSAL: EMBEDDED-OPTIMIZED AUTONOMOUS DRIVING SOLUTIONS FOR JETRACER MODELS IN SPEED TRACK AND SMART CITY CHALLENGES

**Project Title:** Real-time Autonomous Control System Integrating Deep Learning and Adaptive Control on NVIDIA Jetson Nano  
**Target Competition:** Jetson AI Racer Challenge 2026  
**Proposing Team Name:** AlphaRacer  

---

## Abstract
This research proposal presents a comprehensive autonomous driving software solution for the JetRacer model within the *Jetson AI Racer Challenge 2026*. Given the strict hardware constraints of the NVIDIA Jetson Nano processor (4GB LPDDR4, 128-core Maxwell GPU), balancing detection accuracy and real-time control frequency is the core challenge. The proposed solution implements a modular, optimized architecture: the Perception Module utilizes a lightweight, modified CNN (ResNet-18) for behavioral-cloning-based lane following combined with YOLOv8-nano for real-time traffic sign and traffic light detection. Both deep learning models are optimized using NVIDIA TensorRT at FP16 precision. The Decision Module utilizes a Finite State Machine (FSM) integrated with a temporal hysteresis filter to produce stable navigation commands at intersections. The Control Module deploys adaptive PID control loops to regulate steering angles and cruise speed. Experimental simulations and physical track tests are expected to achieve a minimum loop frequency of $25\text{ FPS}$ (control latency under $40\text{ ms}$) and an object detection accuracy mAP@0.5 above $93\%$, ensuring successful completion of both the Speed Track and Smart City challenges.

---

## 1. Introduction & Motivation

Autonomous driving (AD) is a highly active research area with rapid industrial expansion. Scaled experimental platforms, such as the NVIDIA JetRacer AI Kit, provide realistic testbeds for validating AI algorithms. In the context of the *Jetson AI Racer Challenge 2026*, teams must address two distinct challenges:
1. **Speed Track:** Requires high-speed lane keeping, sequential checkpoint validation, and dynamic obstacle avoidance.
2. **Smart City:** Requires accurate detection of mandatory turn signs, prohibited turns, and traffic light signals at urban-style intersections under a strict $\le 300\text{ ms}$ processing latency limit.

The main technical constraint is the **NVIDIA Jetson Nano** platform, which features a quad-core ARM A57 CPU and a 128-core Maxwell GPU sharing 4GB LPDDR4 memory. Running complex vision models simultaneously easily leads to Out-Of-Memory (OOM) errors, thermal throttling, and frame rate drops ($< 10\text{ FPS}$), causing catastrophic steering lag and lane departures. Consequently, optimizing software for real-time edge processing is critical. This proposal focuses on a TensorRT-accelerated pipeline combined with adaptive PID and robust state machines to achieve high-performance driving.

---

## 2. Problem Statement & Research Questions

### 2.1. Problem Statement
Design an autonomous control software pipeline using a single wide-angle front-facing camera to:
* Guide the JetRacer stably within lanes without departing from boundaries (lane departure penalties are $-10$ points and $+15$ seconds).
* Avoid collisions with obstacles (collision penalties are $-5$ points and $+10$ seconds).
* Correctly identify traffic signs and signals at intersections with total control latency $\le 300\text{ ms}$ (running a red light results in immediate disqualification).
* Achieve an average loop frequency $\ge 20\text{ FPS}$ to obtain the maximum performance bonus ($+10$ points).

### 2.2. Research Questions
This proposal addresses three key research questions (RQ):
* **RQ1:** How can we optimize and run both the lane-following and object detection models concurrently on the Jetson Nano GPU to achieve inference latency under $30\text{ ms}$ ($\ge 25\text{ FPS}$) without significant accuracy loss?
* **RQ2:** Which data augmentation and preprocessing techniques enable the behavioral cloning model to generalize to varying track lighting, reflections, and overhead shadows?
* **RQ3:** How can the decision logic be structured to remain resilient against transient object detection drops (e.g., traffic lights missed for 1-2 frames due to camera vibration) at critical intersection points?

---

## 3. Related Work

### 3.1. Lane Following
Autonomous lane-following approaches generally fall into two categories:
* **Traditional Computer Vision:** Methods using HSV filtering, Canny edge detection, perspective transformations (Bird's Eye View), and polynomial fitting [3]. Although computationally cheap, they fail under changing lighting and occlusion.
* **End-to-End Deep Learning:** Pioneered by NVIDIA's PilotNet [1], this approach maps camera images directly to steering outputs via behavioral cloning. While robust, it requires a diverse training set to avoid overfitting. Our method extends ResNet-18 [2] as the regression backbone due to its excellent spatial feature extraction.

### 3.2. Object Detection
For edge devices, YOLO (You Only Look Once) and SSD (Single Shot MultiBox Detector) are popular choices:
* SSD-MobileNet is fast but exhibits low accuracy on small, distant objects.
* **YOLOv8-nano (YOLOv8n)** [4] uses an anchor-free detection head, significantly reducing parameters while improving classification and localization metrics for small objects.

### 3.3. Embedded Optimization
PyTorch models run sequentially under CUDA on Maxwell GPUs rarely exceed $10\text{ FPS}$. By leveraging **NVIDIA TensorRT** [5], we can compile models with layer fusion and FP16 quantization, unlocking 3-5x acceleration on Maxwell GPUs with minimal accuracy drop.

---

## 4. Proposed Method

### 4.1. System Architecture
We propose a decoupled modular architecture to ensure independence and ease of optimization for each component:

```
                  ┌──────────────────────────────┐
                  │      CSI/USB Camera          │
                  └──────────────┬───────────────┘
                                 │ Frame (640x480)
                                 ▼
Perception        ┌──────────────────────────────┐
Layer             │       Image Preprocessing    │
                  └──────┬────────────────┬──────┘
                         │                │
                         ▼ (Resized)      ▼ (Resized)
                  ┌──────────────┐ ┌──────────────┐
                  │   LaneNet    │ │   SignNet    │
                  │ (ResNet-18)  │ │  (YOLOv8n)  │
                  └──────┬───────┘ └──────┬───────┘
                         │ Target (x,y)   │ Class, BBox, Conf
                         ▼            ┌───▼───────────┐
                         │            │ Filter &      │
                         │            │ Hysteresis    │
                         │            └───┬───────────┘
                         │                │ Tracked Objects
                         ▼                ▼
Decision          ┌──────────────────────────────┐
Layer             │    Finite State Machine      │
                  │     (FSM Decision Core)      │
                  └──────────────┬───────────────┘
                                 │ Control States & Modifiers
                                 ▼
Control           ┌──────────────────────────────┐
Layer             │ Adaptive PID Controllers     │
                  └──────────────┬───────────────┘
                                 │ Steering Angle & Throttle
                                 ▼
                  ┌──────────────────────────────┐
                  │      JetRacer Actuators      │
                  └──────────────────────────────┘
```

### 4.2. Perception Module

#### 4.2.1. Lane Keeping (LaneNet)
We use a modified ResNet-18 backbone network. Rather than predicting the raw steering angle directly (which heavily couples the steering output to the speed at which training data was collected), the model predicts the **coordinates of a path target $(x, y)$** located on the lane centerline ahead of the car.
* **Input:** Images from the wide-angle camera are cropped to a Region of Interest (ROI) to remove background noise above the horizon, then resized to $224 \times 224$ pixels.
* **Loss Function:** Mean Squared Error (MSE) is used to optimize the regression head:
$$\mathcal{L}_{lane} = \frac{1}{N} \sum_{i=1}^{N} \left[ (x_i - \hat{x}_i)^2 + (y_i - \hat{y}_i)^2 \right]$$
where $(x_i, y_i)$ represents the ground-truth coordinates of the lane centerline and $(\hat{x}_i, \hat{y}_i)$ denotes the coordinates predicted by the network.
* **Optimization:** The model is exported to ONNX format and compiled using TensorRT into an engine running at FP16 precision directly on the GPU.

#### 4.2.2. Traffic Sign & Light Detection (SignNet)
A YOLOv8-nano model is trained on 6 specific classes:
1. `TurnLeft` (Mandatory left turn sign).
2. `TurnRight` (Mandatory right turn sign).
3. `GoStraight` (Mandatory straight sign).
4. `Prohibited` (Prohibition sign).
5. `RedLight` (Red traffic signal).
6. `GreenLight` (Green traffic signal).

Input frames are resized to $320 \times 320$ pixels to ensure high-fidelity detection of small signs at a distance. The model is also compiled via TensorRT FP16 to keep inference latency under $20\text{ ms}$.

### 4.3. Decision Module
To ensure stability against transient detection drops (e.g., YOLO losing the traffic light for a single frame due to camera vibration when going over road bumps), the decision module implements a **temporal hysteresis filter** coupled with a **Finite State Machine (FSM)**.

#### 4.3.1. Hysteresis Filtering
An object is only confirmed as "lost" or "detected" if its status is consistent across $k$ consecutive frames ($k = 3$ for $25\text{ FPS}$ operations):
$$S_{filtered}(t) = \begin{cases} S(t) & \text{if } S(t) = S(t-1) = \dots = S(t-k+1) \\ S_{filtered}(t-1) & \text{otherwise} \end{cases}$$

#### 4.3.2. FSM States
The states and state transitions are detailed in Table 1:

**Table 1: FSM Operating States**

| State Name | Behavior Description | Transition Conditions |
| :--- | :--- | :--- |
| `LANE_FOLLOW` | Default state. Steers along center lane using LaneNet predictions at high base speed. | Transitions to stopping/turning states upon detecting traffic signals or intersections. |
| `OBSTACLE_AVOID` | Temporarily deviates from the lane centerline to bypass obstacles, then rejoins. | Triggered when an obstacle is detected within $D_{safe}$. Reverts to `LANE_FOLLOW` after clearance. |
| `TRAFFIC_LIGHT_STOP`| Slows down and stops before the stop line at an intersection. | Triggered by a confirmed `RedLight` detection. Transitions back to `LANE_FOLLOW` on `GreenLight`. |
| `INTERSECTION_TURN` | Applies a steering bias/override to navigate intersections according to sign directions. | Triggered at intersections with valid sign detections. Reverts to `LANE_FOLLOW` upon intersection exit. |

### 4.4. Control Module

#### 4.4.1. Steering Control
Steering angle is computed using a PID (Proportional-Integral-Derivative) controller acting on the lateral deviation error $e_x(t)$ between the predicted target $x_{pred}$ and the camera center $x_{center}$:
$$e_x(t) = x_{pred}(t) - x_{center}$$
The control variable $u_{steer}(t)$ is defined as:
$$u_{steer}(t) = K_p e_x(t) + K_i \int_{0}^{t} e_x(\tau) d\tau + K_d \frac{de_x(t)}{dt}$$
Parameters $K_p$, $K_i$, and $K_d$ are tuned experimentally to eliminate overshoot when cornering.

#### 4.4.2. Throttle Control (Adaptive Speed)
To avoid losing traction during sharp turns or colliding with obstacles, vehicle throttle is adjusted dynamically based on steering magnitude and obstacle distance $D_{obstacle}$:
$$u_{throttle}(t) = v_{base} \cdot \left(1 - \alpha \cdot |u_{steer}(t)|\right) - \beta \cdot \frac{1}{D_{obstacle}(t)}$$
where:
* $v_{base}$ is the straight-line cruising throttle.
* $\alpha$ is a scaling coefficient to reduce speed during turns ($\alpha \approx 0.4$).
* $\beta$ is a braking coefficient as the car approaches obstacles or traffic lights.

---

## 5. Experimental Plan

### 5.1. Dataset Collection & Augmentation
* **Lane-Following Dataset:** Approximately $5,000$ images are collected by manually driving the vehicle under varied lighting (toggled ambient lights, directional spots). Augmentations include random brightness, contrast adjustments, Gaussian noise, and synthetic shadow masking to improve LaneNet robustness.
* **Object Detection Dataset:** Approximately $3,000$ images annotated using LabelImg/Roboflow. Mosaic and Mixup techniques are applied to improve mAP on small objects.

### 5.2. Evaluation Metrics
1. **Model Accuracy:**
   * LaneNet: Mean Squared Error (MSE) on the validation set.
   * SignNet: mAP@0.5 on the test set (target: $\ge 93\%$).
2. **Computational Performance:**
   * Average processing frame rate (FPS) on the Jetson Nano.
   * Inference latency (ms) per model and total control loop latency (target: $< 40\text{ ms}$).
3. **Driving Benchmarks:**
   * Mean lane departures per run (target: 0).
   * Collisions per run (target: 0).
   * Average lap completion time.

### 5.3. Operational Logging (System Log)
Real-time diagnostic metrics are output to `.csv` or `.txt` format for post-run telemetry analysis, as described in Table 2:

**Table 2: Log File Schema**

| Attribute | Data Type | Meaning and Examples |
| :--- | :--- | :--- |
| `timestamp` | Float | System epoch time in seconds. e.g., `17856345.123` |
| `fps` | Float | Real-time loop frequency. e.g., `26.4` |
| `detected_object` | String | Confirmed detected class. e.g., `TurnLeft` or `None` |
| `confidence` | Float | Detection confidence score (0.0 - 1.0). e.g., `0.92` |
| `decision` | String | Current FSM operating state. e.g., `INTERSECTION_TURN` |
| `latency_ms` | Float | Total end-to-end frame processing time. e.g., `34.5` |
| `control_output` | List | Actuator signals sent as `[steering, throttle]`. e.g., `[-0.35, 0.5]` |
| `event` | String | Special triggers. e.g., `PASS_CHECKPOINT_1`, `COLLISION`, `LAP_COMPLETED` |

---

## 6. Implementation Plan & Risk Management

### 6.1. Timeline
* **Weeks 1 - 2 (Setup & Data Collection):** Establish development workspace on Jetson Nano. Gather and label lane-following and sign-detection image sets.
* **Weeks 3 - 4 (Training & Optimization):** Train models on GPU workstations. Export models to TensorRT FP16 format and benchmark inference speeds.
* **Weeks 5 - 6 (Logic & Control Development):** Code the FSM decision logic, hysteresis filters, and PID controllers. Test in simulation environments.
* **Weeks 7 (Physical Integration & Tuning):** Deploy software onto the JetRacer model. Tune PID coefficients and adaptive throttle behavior on a physical test track.
* **Week 8 (Validation & Technical Paper):** Run continuous reliability tests, log telemetry data, and compile findings into the Technical Paper.

### 6.2. Technical Risks & Mitigations

1. **Risk 1: Hardware Thermal Throttling on Jetson Nano.**
   * *Impact:* CPU/GPU clocks are forced down when core temperature exceeds $75^\circ\text{C}$, dropping loop speed to $< 10\text{ FPS}$.
   * *Mitigation:* Maximize fan speed before runs using `sudo jetson_clocks --fan 255`. Leverage TensorRT optimizations to reduce computational footprint.
2. **Risk 2: Sign Recognition Failures Under Varied Illumination.**
   * *Impact:* Bright spotlights or dark shadows reduce YOLO confidence scores below the FSM threshold.
   * *Mitigation:* Employ extensive color space (HSV) jittering and shadow-mask augmentation during training. Integrate temporal hysteresis to retain states during short drops.
3. **Risk 3: YOLO Inference Latency Blocking Control Updates.**
   * *Impact:* A single-threaded pipeline waits for YOLO to finish before steering, causing lag and lane departures at high speeds.
   * *Mitigation:* Implement a multi-threaded architecture: the steering and camera grab run on a high-priority thread ($30\text{ Hz}$), while YOLO inference runs on a lower-priority worker thread ($15\text{ - }20\text{ Hz}$).

---

## 7. Expected Outcomes & Limitations

### 7.1. Expected Outcomes
* **Control Loop Frequency:** Steady performance at $\ge 25\text{ FPS}$ on the Jetson Nano.
* **Control Latency:** Total latency from image grab to PWM output $\le 40\text{ ms}$.
* **Sign Detection:** mAP@0.5 $\ge 93\%$ with intersection decision time $\le 50\text{ ms}$.
* **Reliability:** $100\%$ lap completion rate under test runs.

### 7.2. Limitations
* Heavily reliant on visible lane markings. Performance degrades under extreme lane fading or occlusion ($> 30\text{ cm}$).
* Susceptible to novel sign designs not represented in the training set.

---

## 8. References

[1] Bojarski, M., Del Testa, D., Dworakowski, D., Firner, B., Flepp, B., Goyal, P., Jackel, L. D., Monfort, M., Muller, U., Zhang, J., & others. (2016). End to end learning for self-driving cars. *arXiv preprint arXiv:1604.07316*.

[2] He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition. In *Proceedings of the IEEE conference on computer vision and pattern recognition* (pp. 770-778).

[3] Åström, K. J., & Hägglund, T. (2006). *Advanced PID Control*. Research Triangle Park, NC: ISA - The Instrumentation, Systems, and Automation Society. ISBN: 978-1-55617-942-6.

[4] Jocher, G., Chaurasia, A., & Qiu, J. (2023). *Ultralytics YOLOv8* (Version 8.0.0). [Software]. Available from: https://github.com/ultralytics/ultralytics.

[5] NVIDIA Corporation. (2025). *NVIDIA TensorRT Developer Guide: High-Performance Deep Learning Inference*. Available from: https://developer.nvidia.com/tensorrt.

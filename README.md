# 🚁 Autonomous Surveillance Drone - Simulation Workspace

This work was made by 3 persons:
-Nicolas Consalvi (Hardware setup / Simulation building & setup / SLAM 3D)
-Adrien Waeles-Devaux (Design of an EKF)
-Youssef Miri (AI : Computer vision YOLOv11 / Vocal Commands with LLM / reinforcement learning with MuJoCo)

This repository contains: 
-The complete **ROS 2 workspace** for the Autonomous Surveillance Drone project. It integrates **PX4 Autopilot (SITL)** with **Gazebo Garden/Harmonic**, a custom **TF tree**, and **RTAB-Map** for 3D SLAM.
-The **reinforcement_learning.zip**, which contains our reinforcement learning project : landing on a moving platform thanks to PPO algorithm.
-The Computer_vision (**computer_vision.zip**) & vocal commands (**final_alexa_agent.py**) codes.

> **Note for the simulation:** All source codes/packages for TF management (`my_tf2_package`) and SLAM configuration (`rtabmap_slam_pkg`) are already included in this repository in the /src directory. You simply need to copy the repository into a ros2 workspace, build and launch them.

**#SETUP OF THE SIMULATION**

## 📋 Prerequisites & Base Setup

### 1. Base Installation (PX4 & ROS 2)

Before using this workspace, ensure you have a working installation of **ROS 2 Humble** and **PX4 Autopilot** on Ubuntu 22.04.
👉 **[Click here for the complete PX4 + ROS 2 + Gazebo Installation Guide](https://kuat-telegenov.notion.site/How-to-setup-PX4-SITL-with-ROS2-and-XRCE-DDS-Gazebo-simulation-on-Ubuntu-22-e963004b701a4fb2a133245d96c4a247)**

### 2. Additional Dependencies

Install **QGroundControl** to monitor the drone:

* [Download QGroundControl AppImage](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html)

Fix Python compatibility for ROS 2 builds:

```bash
pip3 uninstall setuptools empy
pip3 install --user "setuptools>=30.3.0,<80" "empy<4"

```

Install the specific Gazebo bridge for ROS 2 Humble:

```bash
sudo apt remove --purge ros-humble-ros-gz*
sudo apt autoremove && sudo apt update
sudo apt install ros-humble-ros-gzharmonic

```

---

## 🛠️ Build the Workspace

Since the packages are already in `src/`, simply build the workspace:

```bash
cd ~/ws_ros2
colcon build
source install/setup.bash

```

---

## 🚀 Launching the Simulation

You need **3 separate terminals** to run the full simulation loop.

### Terminal 1: PX4 SITL (The Drone)

Starts the physics simulation in Gazebo with the depth camera model.

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500_depth

```

### Terminal 2: MicroXRCE Agent (Communication)

Bridges MAVLink (PX4) to DDS (ROS 2).

```bash
MicroXRCEAgent udp4 -p 8888

```

### Terminal 3: ROS-GZ Bridge (Sensors)

Exposes Gazebo sensors (IMU, Odom, Camera, Depth) to ROS 2.

```bash
ros2 run ros_gz_bridge parameter_bridge \
/clock@rosgraph_msgs/msg/Clock@gz.msgs.Clock \
/world/default/model/x500_depth_0/link/base_link/sensor/imu_sensor/imu@sensor_msgs/msg/Imu@gz.msgs.IMU \
/world/default/model/x500_depth_0/link/base_link/sensor/magnetometer_sensor/magnetometer@sensor_msgs/msg/MagneticField@gz.msgs.Magnetometer \
/model/x500_depth_0/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry \
/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image@sensor_msgs/msg/Image@ignition.msgs.Image \
/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo \
/depth_camera/points@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked

```

---

## 📡 Running ROS 2 Nodes (TFs & SLAM)

Once the simulation is running properly, open new terminals to launch the onboard logic included in this repo (you can copy the packages of this repo into your ros2 workspace and build them).

### 1. Launch TFs (Coordinate Frames)

Publishes the static transform between the drone body and the camera.

```bash
source ~/ws_ros2/install/setup.bash
ros2 launch my_tf2_package tf_launch.py

```

### 2. Launch RTAB-Map (3D Mapping)

Starts the SLAM algorithm using the configured parameters in `src/rtabmap_slam_pkg/params`.

```bash
source ~/ws_ros2/install/setup.bash
ros2 launch rtabmap_slam_pkg rtabmap_slam.launch.py params_file:=$(ros2 pkg prefix rtabmap_slam_pkg)/share/rtabmap_slam_pkg/params/rtabmap_params.yaml

```

---

## 📊 Visualization & Analysis

### RViz2 Setup

Launch `rviz2` to visualize the drone and the map.

* **Fixed Frame:** Set to `camera_link`
* **Add Topic:** `/depth_camera/points` (Live 3D view)
* **Add Topic:** `/rtabmap/mapData` (Global Map)

### Debugging Topics

* **Motor Commands:** `ros2 run ros_gz_bridge parameter_bridge /x500_depth_0/command/motor_speed@actuator_msgs/msg/Actuators[gz.msgs.Actuators`
* **Ground Truth Odom:** `/world/default/model/x500_depth_0/odometry_with_covariance`

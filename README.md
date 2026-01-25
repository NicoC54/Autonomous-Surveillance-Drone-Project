# 🚁 Autonomous Drone Simulation: Complete Setup Guide

This tutorial provides a step-by-step guide to setting up a **PX4 SITL (Software In The Loop)** simulation environment with **ROS 2 Humble**, **Gazebo**, and **RTAB-Map** for 3D SLAM.


## 1. Environment Setup

### 1.1 Python Dependencies Fix

Before installing ROS packages, we need to ensure compatibility with Python `setuptools`. Run the following to prevent build errors:

```bash
pip3 uninstall setuptools empy
pip3 install --user "setuptools>=30.3.0,<80" "empy<4"

```

### 1.2 Install QGroundControl

QGroundControl (QGC) is required to monitor the drone's flight status and mode.

1. Download the AppImage from the [official documentation](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html).
2. Make it executable and run it:
```bash
chmod +x QGroundControl.AppImage
./QGroundControl.AppImage

```



### 1.3 Install ROS-Gazebo Bridge

We use the `ros-gz-bridge` to communicate between ROS 2 (DDS) and Gazebo (Garden/Harmonic). We must ensure we have the correct version (`harmonic`) installed.

```bash
# Remove potential conflicting versions
sudo apt remove --purge ros-humble-ros-gz*
sudo apt autoremove && sudo apt update

# Install the correct Harmonic bridge
sudo apt install ros-humble-ros-gzharmonic

```

---

## 2. Launching the Simulation

To run the full simulation, you need to open **3 separate terminals**.

### 🖥️ Terminal 1: PX4 SITL & Gazebo

This launches the drone physics model (`x500_depth`) and the Gazebo environment.

```bash
# Navigate to your PX4-Autopilot directory
cd ~/PX4-Autopilot
make px4_sitl gz_x500_depth

```

### 🖥️ Terminal 2: MicroXRCE Agent

The agent acts as the middleware to translate MAVLink messages (PX4) into DDS messages (ROS 2).

```bash
MicroXRCEAgent udp4 -p 8888

```

### 🖥️ Terminal 3: The ROS-GZ Bridge

This command creates the bridge for specific sensors. It allows ROS 2 to "see" the Gazebo topics (IMU, Magnetometer, Odometry, and Depth Camera).

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

## 3. Setting up Transforms (TF)

The drone needs a TF Tree (Coordinate Frames) to locate sensors relative to the body.

### 3.1 Create the Package

First, install the necessary TF tools and create a new Python package.

```bash
sudo apt install ros-humble-tf2-tools ros-humble-rqt-tf-tree
cd ~/ws_ros2/src
ros2 pkg create --build-type ament_python my_tf2_package

```

### 3.2 Add Source Files

Place your Python scripts inside the package structure as follows:

```text
my_tf2_package/
├── package.xml
├── setup.py
└── my_tf2_package/
    ├── __init__.py
    ├── drone_tf_publisher.py  <-- (Your TF Logic)
    └── launch/
        └── tf_launch.py       <-- (Your Launch File)

```

### 3.3 Build and Launch

Make the script executable, build the workspace, and launch the node.

```bash
# Make executable
chmod +x ~/ws_ros2/src/my_tf2_package/my_tf2_package/drone_tf_publisher.py

# Build
cd ~/ws_ros2
colcon build --packages-select my_tf2_package
source install/setup.bash

# Launch
ros2 launch my_tf2_package tf_launch.py

```

---

## 4. 3D Mapping (RTAB-Map)

We use RTAB-Map to perform SLAM (Simultaneous Localization and Mapping) using the simulated depth camera.

### 4.1 Install & Create Package

```bash
sudo apt install ros-humble-rtabmap-ros
cd ~/ws_ros2/src
ros2 pkg create --build-type ament_python rtabmap_slam_pkg

```

### 4.2 Configuration (YAML)

We need to tell RTAB-Map which topics to listen to.

1. Create a `params` directory: `mkdir -p ~/ws_ros2/src/rtabmap_slam_pkg/params`
2. Create a file named `rtabmap_params.yaml` inside it with the following content:

```yaml
/rtabmap:
  ros__parameters:
    use_sim_time: true
    subscribe_depth: false
    subscribe_rgb: true
    rgb_topic: "/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image"
    camera_info_topic: "/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/camera_info"
    subscribe_scan_cloud: true
    scan_cloud_topic: "/depth_camera/points"
    approx_sync: true
    topic_queue_size: 50
    sync_queue_size: 50
    qos_image: 1
    qos_camera_info: 1

```

### 4.3 Build and Launch SLAM

Rebuild the workspace to include the new package and parameters.

```bash
cd ~/ws_ros2
colcon build --packages-select rtabmap_slam_pkg
source install/setup.bash

# Launch RTAB-Map with the custom parameters
ros2 launch rtabmap_slam_pkg rtabmap_slam.launch.py params_file:=$(ros2 pkg prefix rtabmap_slam_pkg)/share/rtabmap_slam_pkg/params/rtabmap_params.yaml

```

---

## 5. Visualization & Analysis

### 5.1 RViz2 Setup

To visualize the map and drone, open `rviz2` in a new terminal.

* **Fixed Frame:** Set to `camera_link`.
* **Add Topic:** `/depth_camera/points` (To see what the drone sees).
* **Add Topic:** `/rtabmap/mapData` (To see the 3D map being built).

### 5.2 Analyzing Motor Commands

To debug actuator outputs (motors U2, U3, U4), use this bridge command:

```bash
ros2 run ros_gz_bridge parameter_bridge /x500_depth_0/command/motor_speed@actuator_msgs/msg/Actuators[gz.msgs.Actuators

```

### 5.3 Ground Truth Comparison

For Kalman filter validation, compare these topics:

* **Real Position (Gazebo):** `/world/default/model/x500_depth_0/odometry_with_covariance`
* **IMU Data:** `/world/default/model/x500_depth_0/link/base_link/sensor/imu_sensor/imu`

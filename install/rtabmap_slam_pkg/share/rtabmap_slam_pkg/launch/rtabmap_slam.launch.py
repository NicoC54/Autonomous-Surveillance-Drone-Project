import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    # Arguments configurables
    frame_id = LaunchConfiguration('frame_id', default='base_link')
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    database_path = LaunchConfiguration('database_path', default=os.path.expanduser('~/.ros/rtabmap.db'))

    declare_frame_id = DeclareLaunchArgument(
        'frame_id',
        default_value='base_link',
        description='Frame de rÃ©fÃ©rence du drone'
    )
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Utiliser le temps de simulation Gazebo'
    )
    declare_database_path = DeclareLaunchArgument(
        'database_path',
        default_value=os.path.expanduser('~/.ros/rtabmap.db'),
        description='Chemin vers la base de donnÃ©es RTAB-Map'
    )

    # Fichier de paramÃ¨tres RTAB-Map
    pkg_share = get_package_share_directory('rtabmap_slam_pkg')
    params_file = os.path.join(pkg_share, 'params', 'rtabmap_params.yaml')

    # NÅ“ud RTAB-Map
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time, 'frame_id': frame_id}],
        remappings=[
            ('/rgb/image', '/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image'),
            ('/rgb/camera_info', '/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/camera_info'),
            ('/scan_cloud', '/depth_camera/points'),
            ('/odom', '/model/x500_depth_0/odometry')
        ]
    )

    # NÅ“ud RTAB-Map Viz pour afficher le SLAM
    rtabmap_viz = Node(
        package='rtabmap_viz',
        executable='rtabmap_viz',
        name='rtabmap_viz',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time, 'frame_id': frame_id}],
        remappings=[
            ('/rgb/image', '/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image'),
            ('/rgb/camera_info', '/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/camera_info'),
            ('/scan_cloud', '/depth_camera/points'),
            ('/odom', '/model/x500_depth_0/odometry')
        ]
    )

    return LaunchDescription([
        declare_frame_id,
        declare_use_sim_time,
        declare_database_path,
        rtabmap_node,
        rtabmap_viz
    ])

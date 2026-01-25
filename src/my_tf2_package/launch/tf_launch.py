from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='my_tf2_package',
            executable='drone_tf_node',
            name='drone_tf_pub',
            output='screen',
            parameters=[{'use_sim_time': True}],
        ),

        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='camera_to_base_link',
            arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'camera_link'],
            parameters=[{'use_sim_time': True}],
        ),
    ])

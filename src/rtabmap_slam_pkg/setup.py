from setuptools import setup

package_name = 'rtabmap_slam_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/rtabmap_slam.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='nicolas',
    maintainer_email='nicolas.consalvipro@gmail.com',
    description='Package pour lancer RTAB-Map SLAM avec PX4 + Gazebo',
    license='MIT',
    entry_points={
        'console_scripts': [
            'rtabmap_node = rtabmap_slam_pkg.rtabmap_node:main',
            'rtabmap_viz_node = rtabmap_slam_pkg.rtabmap_viz_node:main',
        ],
    },
)

from setuptools import setup

package_name = 'my_tf2_package'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/tf_launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='nicolas',
    maintainer_email='nicolas.consalvipro@gmail.com',
    description='Publie les TF dynamiques du drone (map <-> base_link <-> camera_link)',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'drone_tf_node = my_tf2_package.drone_tf_publisher:main',
        ],
    },
)

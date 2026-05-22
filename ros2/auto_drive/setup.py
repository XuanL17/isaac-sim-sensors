import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'auto_drive'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'waypoints'),
         glob('waypoints/*.json')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='XuanL17',
    maintainer_email='116825511+XuanL17@users.noreply.github.com',
    description='Lane follow, GPS waypoint follow, and camera/GPS command arbiter for AV4EV Isaac Sim.',
    license='MIT',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'lane_follow_node = auto_drive.lane_follow_node:main',
            'gps_waypoint_follower = auto_drive.gps_waypoint_follower:main',
            'cmd_arbiter = auto_drive.cmd_arbiter:main',
        ],
    },
)

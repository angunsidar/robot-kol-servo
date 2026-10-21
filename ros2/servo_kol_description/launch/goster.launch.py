"""Kolu RViz'de göster.
    ros2 launch servo_kol_description goster.launch.py                  # kaydırıcılı eklem penceresiyle
    ros2 launch servo_kol_description goster.launch.py gercek_kol:=true # eklemleri pc/ros2_kopru.py yayınlar
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pay = get_package_share_directory("servo_kol_description")
    with open(os.path.join(pay, "urdf", "servo_kol.urdf"), encoding="utf-8") as f:
        urdf = f.read()
    gercek = LaunchConfiguration("gercek_kol")
    return LaunchDescription([
        DeclareLaunchArgument("gercek_kol", default_value="false",
                              description="true: /joint_states'i gerçek kol (ros2_kopru.py) yayınlar"),
        Node(package="robot_state_publisher", executable="robot_state_publisher",
             parameters=[{"robot_description": urdf}]),
        Node(package="joint_state_publisher_gui", executable="joint_state_publisher_gui",
             condition=UnlessCondition(gercek)),
        Node(package="rviz2", executable="rviz2", arguments=["-d", os.path.join(pay, "rviz", "servo_kol.rviz")]),
    ])

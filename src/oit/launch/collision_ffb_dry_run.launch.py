"""Launch the collision-warning FFB adapter without hardware access."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Create a launch description that explicitly selects dry-run mode."""
    package_share = get_package_share_directory("oit")
    config_path = os.path.join(
        package_share,
        "config",
        "collision_ffb.yaml",
    )
    return LaunchDescription([
        Node(
            package="oit",
            executable="collision_ffb_node",
            name="collision_ffb_node",
            output="screen",
            parameters=[config_path, {"output_mode": "dry_run"}],
        ),
    ])

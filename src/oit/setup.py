from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'oit'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',['resource/' + package_name]),
        ('share/' + package_name,['package.xml']),
        (os.path.join('share', package_name, 'launch'),glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
        (os.path.join('share', package_name, 'config'),glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hsr',
    maintainer_email='kurehiro1009@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    
    entry_points={
        'console_scripts': [
            'handle = oit.handle:main',
            'square_node = oit.square_node:main',
            'ffb_test = oit.ffb_test:main',
            'ffb_follow = oit.ffb_follow:main',
            'spring = oit.spring_test:main',
            'periodic = oit.periodic_test:main',
            'spin = oit.spin_node:main',
        ],
    },
)

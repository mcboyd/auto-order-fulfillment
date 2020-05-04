#!/usr/bin/env python

"""
Original Author: Pavel Piliptchak
Contact: pavel.piliptchak@nist.gov

This software was developed by employees of the National Institute of
Standards and Technology (NIST), an agency of the Federal Government and is
being made available as a public service. Pursuant to title 17
United States Code Section 105, works of NIST employees are not subject to
copyright protection in the United States.  This software may be subject to
foreign copyright.  Permission in the United States and in foreign countries,
to the extent that NIST may hold copyright, to use, copy, modify, create
derivative works, and distribute this software and its documentation without
fee is hereby granted on a non-exclusive basis, provided that this notice and
disclaimer of warranty appears in all copies.

THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE.  IN NO EVENT
SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM, OR
IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON WARRANTY,
CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED BY PERSONS
OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED FROM, OR AROSE
OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES PROVIDED HEREUNDER.
"""
"""
Significantly modified by: Matthew Boyd
Contact: mcboyd@bu.edu

Modified to read parts from sensors, correlate part coordinates to shelf or bin location, 
determine path to shelf or bin, use waypoints to reach far locations, and pick and place 
parts to fulfill orders. 
"""
import rospy
import tf2_ros
import moveit_commander as mc

from geometry_msgs.msg import TransformStamped
from nist_gear.msg import Order, Model, LogicalCameraImage, VacuumGripperState

from std_srvs.srv import Trigger
from nist_gear.srv import AGVControl, GetMaterialLocations, VacuumGripperControl

import sys
import copy
import yaml
import re
from math import pi, sqrt


def start_competition():
    rospy.wait_for_service('/ariac/start_competition')
    rospy.ServiceProxy('/ariac/start_competition', Trigger)()


def end_competition():
    rospy.wait_for_service('/ariac/end_competition')
    rospy.ServiceProxy('/ariac/end_competition', Trigger)()


def submit_shipment(agv, name):
    rospy.wait_for_service('/ariac/' + agv)
    rospy.ServiceProxy('/ariac/' + agv, AGVControl)(name)


def get_order():
    order = rospy.wait_for_message('/ariac/orders', Order)
    return order


# def get_part_type_location(part):
#     rospy.wait_for_service('/ariac/material_locations')
#     response = rospy.ServiceProxy('/ariac/material_locations',
#                                   GetMaterialLocations)(part.type)
#     reachable_location = None
#     for loc in response.storage_units:
#         if 'shelf' in loc.unit_id or 'bin' in loc.unit_id:
#             reachable_location = loc.unit_id
#             break
#     assert(reachable_location), "This implementation only reaches shelves/bins"
#     return reachable_location


def get_part_type_location_cameras(part):
    x = part.pose.position.x
    y = part.pose.position.y
    reachable_location = None
    waypoint = None
    if x > 0 and y > 0:
        # Front left quadrant, Shelf 1 and Bins 1-8
        if y < 1.63 and y > 0:
            if x > 4.815793:
                reachable_location = 'bin4'
            elif x > 3.874991:
                reachable_location = 'bin3'
            elif x > 2.934189:
                reachable_location = 'bin2'
            else:
                reachable_location = 'bin1'
        elif y < 2.5 and y > 0:
            if x > 4.815793:
                reachable_location = 'bin8'
            elif x > 3.874991:
                reachable_location = 'bin7'
            elif x > 2.934189:
                reachable_location = 'bin6'
            else:
                reachable_location = 'bin5'
        elif y < 3.6 and y > 0:
            if x > 3.874991:
                reachable_location = 'shelf1_3_r'
            else:
                reachable_location = 'shelf1_1_r'
        elif y >= 3.6:
            if x > 3.874991:
                reachable_location = 'shelf1_3_l'
                waypoint = 'waypointleft'
            else:
                reachable_location = 'shelf1_1_l'
                waypoint = 'waypointleft'
    elif x > 0 and y < 0:
        # Front right quadrant, Shelf 3 and Bins 9-16
        if y > -1.63 and y < 0:
            if x > 4.815793:
                reachable_location = 'bin12'
            elif x > 3.874991:
                reachable_location = 'bin11'
            elif x > 2.934189:
                reachable_location = 'bin10'
            else:
                reachable_location = 'bin9'
        elif y > -2.5 and y < 0:
            if x > 4.815793:
                reachable_location = 'bin16'
            elif x > 3.874991:
                reachable_location = 'bin15'
            elif x > 2.934189:
                reachable_location = 'bin14'
            else:
                reachable_location = 'bin13'
        elif y > -3.6 and y < 0:
            if x > 3.874991:
                reachable_location = 'shelf2_3_l'
            else:
                reachable_location = 'shelf2_1_l'
        elif y <= -3.6:
            if x > 3.874991:
                reachable_location = 'shelf2_3_r'
                waypoint = 'waypointright'
            else:
                reachable_location = 'shelf2_1_r'
                waypoint = 'waypointright'
    elif x < 0 and y > 1.5:
        # Back left third, Shelf 5
        if y > 1.5 and y < 3:
            if x > -14.6:
                reachable_location = 'shelf5_3_r'
                waypoint = 'waypoints5right'
            else:
                reachable_location = 'shelf5_1_r'
                waypoint = 'waypoints5right'
        elif y > 3:
            if x > -14.6:
                reachable_location = 'shelf5_3_l'
                waypoint = 'waypointleft'
            else:
                reachable_location = 'shelf5_1_l'
                waypoint = 'waypointleft'
    elif x < 0 and y < 1.5 and y > -1.6:
        # Back middle third, Shelf 8
        if y > 0:
            if x > -14.6:
                reachable_location = 'shelf8_3_l'
                waypoint = 'waypoints8left'
            else:
                reachable_location = 'shelf8_1_l'
                waypoint = 'waypoints8left'
        else:
            if x > -14.6:
                reachable_location = 'shelf8_3_r'
                waypoint = 'waypoints8right'
            else:
                reachable_location = 'shelf8_1_r'
                waypoint = 'waypoints8right'
    else:
        # Back right third, Shelf 11
        if y > -3:
            if x > -14.6:
                reachable_location = 'shelf11_3_l'
                waypoint = 'waypoints11left'
            else:
                reachable_location = 'shelf11_1_l'
                waypoint = 'waypoints11left'
        else:
            if x > -14.6:
                reachable_location = 'shelf11_3_r'
                waypoint = 'waypointright'
            else:
                reachable_location = 'shelf11_1_r'
                waypoint = 'waypointright'

    print(reachable_location)
    return reachable_location, waypoint


def get_parts_from_cameras():
    tf_buffer = tf2_ros.Buffer()
    tf_listener = tf2_ros.TransformListener(tf_buffer)

    # wait for all cameras to be broadcasting
    all_topics = rospy.get_published_topics()
    camera_topics = [t for t, _ in all_topics if '/ariac/logical_camera' in t]
    for topic in camera_topics:
        rospy.wait_for_message(topic, LogicalCameraImage)

    camera_frame_format = r"logical_camera_[0-9]+_(\w+)_[0-9]+_frame"
    all_frames = yaml.safe_load(tf_buffer.all_frames_as_yaml()).keys()
    part_frames = [f for f in all_frames if re.match(camera_frame_format, f)]

    objects = []
    for frame in part_frames:
        try:
            world_tf = tf_buffer.lookup_transform(
                'world',
                frame,
                rospy.Time(),
                rospy.Duration(0.1)
            )
            ee_tf = tf_buffer.lookup_transform(
                frame,
                'left_ee_link',
                rospy.Time(),
                rospy.Duration(0.1)
            )
        except (tf2_ros.LookupException, tf2_ros.ExtrapolationException) as e:
            continue

        # remove stale transforms
        tf_time = rospy.Time(
            world_tf.header.stamp.secs,
            world_tf.header.stamp.nsecs
        )
        if rospy.Time.now() - tf_time > rospy.Duration(1.0):
            continue

        model = Model()
        model.type = re.match(camera_frame_format, frame).group(1)
        model.pose.position = world_tf.transform.translation
        model.pose.orientation = ee_tf.transform.rotation
        objects.append(model)
    return objects


def get_target_world_pose(target, agv):
    tf_buffer = tf2_ros.Buffer()
    tf_listener = tf2_ros.TransformListener(tf_buffer)
    tf_broadcaster = tf2_ros.StaticTransformBroadcaster()

    tf_msg = TransformStamped()
    tf_msg.header.frame_id = 'kit_tray_1' if agv == 'agv1' else 'kit_tray_2'
    tf_msg.header.stamp = rospy.Time()
    tf_msg.child_frame_id = 'target_frame'
    tf_msg.transform.translation = target.pose.position
    tf_msg.transform.rotation = target.pose.orientation

    for _ in range(5):
        tf_broadcaster.sendTransform(tf_msg)

    # tf lookup fails occasionally, this automatically retries the lookup
    MAX_ATTEMPTS = 10
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        try:
            world_target_tf = tf_buffer.lookup_transform(
                'world',
                'target_frame',
                rospy.Time(),
                rospy.Duration(0.1)
            )
            ee_target_tf = tf_buffer.lookup_transform(
                'target_frame',
                'left_ee_link',
                rospy.Time(),
                rospy.Duration(0.1)
            )
            break
        except:
            continue

    world_target = copy.deepcopy(target)
    world_target.pose.position = world_target_tf.transform.translation
    world_target.pose.orientation = ee_target_tf.transform.rotation
    return world_target


class MoveitRunner():
    def __init__(self, group_names, node_name='ariac_moveit_example',
                 ns='', robot_description='robot_description'):

        mc.roscpp_initialize(sys.argv)
        rospy.init_node(node_name, anonymous=True)

        self.robot = mc.RobotCommander(ns+'/'+robot_description, ns)
        self.scene = mc.PlanningSceneInterface(ns)
        self.groups = {}
        for group_name in group_names:
            group = mc.MoveGroupCommander(
                group_name,
                robot_description=ns+'/'+robot_description,
                ns=ns
            )
            group.set_goal_tolerance(0.05)
            self.groups[group_name] = group

        self.define_preset_locations()
        self.goto_preset_location('start')

    def define_preset_locations(self):
        locations = {}

        name = 'start'
        gantry = [0, 0, 0]
        left = [0.0, -pi/4, pi/2, -pi/4, pi/2, 0]
        right = [pi, -pi/4, pi/2, -pi/4, pi/2, 0]
        locations[name] = (gantry, left, right)

        name = 'standby'
        gantry = None
        left = [0.0, -pi/4, pi/2, -pi/4, pi/2, 0]
        right = [pi, -pi/4, pi/2, -pi/4, pi/2, 0]
        locations[name] = (gantry, left, right)

        name = 'agv1'
        gantry = [-0.6, -6.9, 0]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'agv2'
        gantry = [0.6, 6.9, pi]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin1'
        gantry = [2.0, -1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin2'
        gantry = [3.0, -1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin3'
        gantry = [4.0, -1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin4'
        gantry = [5.0, -1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin5'
        gantry = [2.0, -2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin6'
        gantry = [3.0, -2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin7'
        gantry = [4.0, -2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin8'
        gantry = [5.0, -2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf1_1_r'
        gantry = [2.5, -2.3, 0.]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf1_3_r'
        gantry = [4.5, -2.3, 0.]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf1_1_l'
        gantry = [2.5, -4.95, 0.]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf1_3_l'
        gantry = [4.5, -4.95, 0.]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'waypointleft'
        gantry = [0, -5.5, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin9'
        gantry = [2.0, 1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin10'
        gantry = [3.0, 1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin11'
        gantry = [4.0, 1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin12'
        gantry = [5.0, 1.1, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin13'
        gantry = [2.0, 2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin14'
        gantry = [3.0, 2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin15'
        gantry = [4.0, 2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'bin16'
        gantry = [5.0, 2.3, 0.]
        left = [0.0, 0.0, pi/4, 0, pi/2, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf2_1_l'
        gantry = [2.5, 2.3, 0.]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf2_3_l'
        gantry = [4.5, 2.3, 0.]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf2_1_r'
        gantry = [2.5, 4.95, 0.]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf2_3_r'
        gantry = [4.5, 4.95, 0.]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'waypointright'
        gantry = [0, 5.5, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf5_1_r'
        gantry = [-16.06, -1.72, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf5_3_r'
        gantry = [-14.06, -1.72, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf5_1_l'
        gantry = [-16.06, -4.37, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf5_3_l'
        gantry = [-14.06, -4.37, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'waypoints5right'
        gantry = [0, -1.5, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf8_1_r'
        gantry = [-16.06, 1.38, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf8_3_r'
        gantry = [-14.06, 1.38, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf8_1_l'
        gantry = [-16.06, -1.27, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf8_3_l'
        gantry = [-14.06, -1.27, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'waypoints8left'
        gantry = [0, -1.5, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'waypoints8right'
        gantry = [0, 1.6, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf11_1_r'
        gantry = [-16.06, 4.35, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf11_3_r'
        gantry = [-14.06, 4.35, 0]
        left = [-pi/2, -pi, -pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf11_1_l'
        gantry = [-16.06, 1.7, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'shelf11_3_l'
        gantry = [-14.06, 1.7, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        name = 'waypoints11left'
        gantry = [0, 1.6, 0]
        left = [-pi/2, 0, pi/2, -pi/2, 0, 0]
        right = None
        locations[name] = (gantry, left, right)

        self.locations = locations

    def goto_preset_location(self, location_name):
        group = self.groups['Full_Robot']
        gantry, left, right = self.locations[location_name]
        location_pose = group.get_current_joint_values()

        if gantry:
            location_pose[:3] = gantry
        if left:
            location_pose[3:-6] = left
        if right:
            location_pose[-6:] = right

        # If the robot controller reports a path tolerance violation,
        # this will automatically re-attempt the motion
        MAX_ATTEMPTS = 5
        attempts = 0
        while not group.go(location_pose, wait=True):
            attempts += 1
            assert(attempts < MAX_ATTEMPTS)

    def move_part(self, part, target, part_location, part_waypoint, agv):
        # This example only uses the left arm
        group = self.groups['Left_Arm']
        gm = GripperManager(ns='/ariac/gantry/left_arm/gripper/')

        near_pick_pose = copy.deepcopy(part.pose)
        pick_pose = copy.deepcopy(part.pose)
        place_pose = copy.deepcopy(target.pose)

        near_pick_pose.position.z += 0.1
        pick_pose.position.z += 0.015
        place_pose.position.z += 0.1

        if part_waypoint:
            self.goto_preset_location(part_waypoint)

        self.goto_preset_location(part_location)
        gm.activate_gripper()

        path = [near_pick_pose, pick_pose]
        self.cartesian_move(group, path)

        num_attempts = 0
        MAX_ATTEMPTS = 20
        while not gm.is_object_attached() and num_attempts < MAX_ATTEMPTS:
            num_attempts += 1
            rospy.sleep(0.1)

        if not gm.is_object_attached():
            self.goto_preset_location(part_location)
            if part_waypoint:
                self.goto_preset_location(part_waypoint)
            self.goto_preset_location('standby')
            self.goto_preset_location('start')
            return False

        if 'shelf' in part_location:
            self.goto_preset_location(part_location)
        if part_waypoint:
            self.goto_preset_location(part_waypoint)
        self.goto_preset_location('standby')
        if not part_waypoint:
            self.goto_preset_location('start')
        self.goto_preset_location(agv)

        path = [place_pose]
        self.cartesian_move(group, path)

        gm.deactivate_gripper()

        self.goto_preset_location('standby')
        self.goto_preset_location('start')
        return True

    def cartesian_move(self, group, waypoints):
        (plan, fraction) = group.compute_cartesian_path(waypoints, 0.01, 0.0)
        group.execute(plan, wait=True)


class GripperManager():
    def __init__(self, ns):
        self.ns = ns

    def activate_gripper(self):
        rospy.wait_for_service(self.ns + 'control')
        rospy.ServiceProxy(self.ns + 'control', VacuumGripperControl)(True)

    def deactivate_gripper(self):
        rospy.wait_for_service(self.ns + 'control')
        rospy.ServiceProxy(self.ns + 'control', VacuumGripperControl)(False)

    def is_object_attached(self):
        status = rospy.wait_for_message(self.ns + 'state', VacuumGripperState)
        return status.attached


if __name__ == '__main__':

    group_names = ['Full_Robot', 'Left_Arm', 'Right_Arm', 'Gantry']
    moveit_runner = MoveitRunner(group_names, ns='/ariac/gantry')

    start_competition()
    order = get_order()
    agv_states = {'agv1': [], 'agv2': []}

    all_known_parts = get_parts_from_cameras()

    for shipment in order.shipments:
        active_agv = 'agv1' if shipment.agv_id == 'agv1' else 'agv2'
        agv_state = agv_states[active_agv]

        while True:

            valid_products = []
            for product in shipment.products:
                if product not in agv_state:
                    valid_products.append(product)

            candidate_moves = []
            for part in all_known_parts:
                for product in valid_products:
                    if part.type == product.type:
                        candidate_moves.append((part, product))

            if candidate_moves:
                part, target = candidate_moves[0]

                world_target = get_target_world_pose(target, active_agv)
                # part_location = get_part_type_location(part)
                part_location, part_waypoint = get_part_type_location_cameras(part)

                move_successful = moveit_runner.move_part(
                    part,
                    world_target,
                    part_location,
                    part_waypoint,
                    active_agv
                )
                if move_successful:
                    all_known_parts.remove(part)
                    agv_state.append(target)
            else:
                break

        submit_shipment(active_agv, shipment.shipment_type)
        agv_states[active_agv] = []

    end_competition()
    print('Done')

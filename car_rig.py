# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import bpy
import math
import bpy_extras
import mathutils
import re

DEF_BONE_LAYER = 15
MCH_BONE_EXTENSION_LAYER = 14
MCH_BONE_LAYER = 31


def deselect_edit_bones(ob):
    for b in ob.data.edit_bones:
        b.select = False
        b.select_head = False
        b.select_tail = False


def create_constraint_influence_driver(ob, cns, driver_data_path, base_influence=1.0):
    fcurve = cns.driver_add('influence')
    drv = fcurve.driver
    drv.type = 'AVERAGE'
    var = drv.variables.new()
    var.name = 'influence'
    var.type = 'SINGLE_PROP'

    targ = var.targets[0]
    targ.id_type = 'OBJECT'
    targ.id = ob
    targ.data_path = driver_data_path

    if base_influence != 1.0:
        fmod = fcurve.modifiers[0]
        fmod.mode = 'POLYNOMIAL'
        fmod.poly_order = 1
        fmod.coefficients = (0, base_influence)


def create_rotation_euler_x_driver(ob, bone, driver_data_path):
    fcurve = bone.driver_add('rotation_euler', 0)
    drv = fcurve.driver
    drv.type = 'AVERAGE'
    var = drv.variables.new()
    var.name = 'rotationAngle'
    var.type = 'SINGLE_PROP'

    targ = var.targets[0]
    targ.id_type = 'OBJECT'
    targ.id = ob
    targ.data_path = driver_data_path


def create_translation_x_driver(ob, bone, driver_data_path):
    fcurve = bone.driver_add('location', 0)
    drv = fcurve.driver
    drv.type = 'AVERAGE'
    var = drv.variables.new()
    var.name = 'rotationAngle'
    var.type = 'SINGLE_PROP'

    targ = var.targets[0]
    targ.id_type = 'OBJECT'
    targ.id = ob
    targ.data_path = driver_data_path


def create_bone_group(pose, group_name, color_set, bone_names):
    group = pose.bone_groups.new(group_name)
    group.color_set = color_set
    for bone_name in bone_names:
        bone = pose.bones.get(bone_name)
        if bone is not None:
            bone.bone_group = group


def name_range(prefix, nb=1000):
    if nb > 0:
        yield prefix
        for i in range(1, nb):
            yield '%s.%03d' % (prefix, i)


def dispatch_bones_to_armature_layers(ob):
    re_mch_bone = re.compile('^MCH-Wheel(Brake)?.(Ft|Bk).[LR](.\d+)?$')
    default_visible_layers = [False] * 32

    for b in ob.data.bones:
        layers = [False] * 32
        if b.name.startswith('DEF-'):
            layers[DEF_BONE_LAYER] = True
        elif b.name.startswith('MCH-'):
            layers[MCH_BONE_LAYER] = True
            if b.name == 'MCH-Body' or re_mch_bone.match(b.name):
                layers[MCH_BONE_EXTENSION_LAYER] = True
        else:
            layer_num = ob.pose.bones[b.name].bone_group_index
            layers[layer_num] = True
            default_visible_layers[layer_num] = True
        b.layers = layers

    ob.data.layers = default_visible_layers


class WheelDimension():

    def __init__(self, armature, position, side_position, default_pos):
        self.position = position
        self.side_position = side_position

        wheels = (armature.edit_bones.get(name) for name in name_range('DEF-Wheel.%s.%s' % (position, side_position)))
        nb_wheels = 0
        min_wheel = default_pos.copy()
        max_wheel = default_pos.copy()
        max_width = 0
        for wheel in wheels:
            if wheel is None:
                break
            if nb_wheels == 0 or min_wheel.y > wheel.head.y:
                min_wheel = wheel.head.copy()
            if nb_wheels == 0 or max_wheel.y < wheel.head.y:
                max_wheel = wheel.head.copy()
            max_width = max(max_width, abs(wheel.head.x))
            nb_wheels += 1

        self.min_position = min_wheel
        self.max_position = max_wheel
        self.max_width = max_width
        self.nb = nb_wheels

    @property
    def medium_position(self):
        if self.nb == 0:
            return self.min_position
        else:
            return (self.min_position + self.max_position) / 2.0


class CarDimension():

    def __init__(self, armature):
        body = armature.edit_bones['DEF-Body']

        self.wheels_front_left = WheelDimension(armature, 'Ft', 'L', body.head)
        self.wheels_front_right = WheelDimension(armature, 'Ft', 'R', body.head)
        self.wheels_back_left = WheelDimension(armature, 'Bk', 'L', body.tail)
        self.wheels_back_right = WheelDimension(armature, 'Bk', 'R', body.tail)

        if self.has_wheels:
            self.width = max(self.wheels_front_left.max_width, self.wheels_front_right.max_width, self.wheels_back_left.max_width, self.wheels_back_right.max_width)
        else:
            self.width = min(1, body.length)

        if self.has_front_wheels:
            self.length = max(body.length, self.width)
            self.center = body.head
        else:
            self.length = max(body.length * .6, self.width)
            self.center = body.head.lerp(body.tail, .5)

        self.height = min(self.width, self.length) * 2.0
        self.height = max(self.height, body.head.z * 4.0)

    @property
    def wheels_front_position(self):
        return (self.wheels_front_left.min_position + self.wheels_front_right.min_position) / 2

    @property
    def wheels_back_position(self):
        return (self.wheels_back_left.max_position + self.wheels_back_right.max_position) / 2

    @property
    def suspension_front_position(self):
        return (self.wheels_front_left.medium_position + self.wheels_front_right.medium_position) / 2

    @property
    def suspension_back_position(self):
        return (self.wheels_back_left.medium_position + self.wheels_back_right.medium_position) / 2

    @property
    def has_wheels(self):
        return self.has_front_wheels or self.has_back_wheels

    @property
    def has_front_wheels(self):
        return self.nb_front_wheels > 0

    @property
    def has_back_wheels(self):
        return self.nb_back_wheels > 0

    @property
    def nb_front_wheels(self):
        return max(self.wheels_front_left.nb, self.wheels_front_right.nb)

    @property
    def nb_back_wheels(self):
        return max(self.wheels_back_left.nb, self.wheels_back_right.nb)

    def wheels(self, position, side_position):
        if position == 'Ft':
            return self.wheels_front_left if side_position == 'L' else self.wheels_front_right
        else:
            return self.wheels_back_left if side_position == 'L' else self.wheels_back_right


class ArmatureGenerator(object):

    def __init__(self, ob):
        self.ob = ob

    def generate(self):
        from . import widgets
        widgets.create()

        self.ob['wheels_on_y_axis'] = False
        self.ob['suspension_factor'] = .5
        self.ob['suspension_rolling_factor'] = .5

        bpy.ops.object.mode_set(mode='EDIT')
        self.dimension = CarDimension(self.ob.data)

        self.generate_animation_rig()
        self.ob.data['Car Rig'] = True
        deselect_edit_bones(self.ob)

        bpy.ops.object.mode_set(mode='POSE')
        self.generate_constraints_on_rig()
        self.ob.draw_type = 'WIRE'

        self.generate_bone_groups()
        dispatch_bones_to_armature_layers(self.ob)

    def generate_animation_rig(self):
        amt = self.ob.data

        body = amt.edit_bones['DEF-Body']
        root = amt.edit_bones.new('Root')
        root.head = (self.dimension.wheels_back_position.x, self.dimension.wheels_back_position.y, 0)
        root.tail = (self.dimension.wheels_back_position.x, self.dimension.wheels_back_position.y + self.dimension.length, 0)
        root.use_deform = False

        shapeRoot = amt.edit_bones.new('SHP-Root')
        shapeRoot.head = (self.dimension.center.x, self.dimension.center.y, 0.01)
        shapeRoot.tail = (self.dimension.center.x, self.dimension.center.y + self.dimension.length, 0.01)
        shapeRoot.use_deform = False
        shapeRoot.parent = root

        drift = amt.edit_bones.new('Drift')
        drift.head = self.dimension.wheels_front_position
        drift.tail = self.dimension.wheels_front_position
        drift.tail.y -= self.dimension.length
        drift.head.z = self.dimension.wheels_back_position.z
        drift.tail.z = self.dimension.wheels_back_position.z
        drift.roll = math.pi
        drift.use_deform = False
        drift.parent = root

        shapeDrift = amt.edit_bones.new('SHP-Drift')
        shapeDrift.head = (self.dimension.center.x, self.dimension.center.y + self.dimension.length * 1.05, drift.head.z)
        shapeDrift.tail = shapeDrift.head
        shapeDrift.tail.y += 1
        shapeDrift.use_deform = False
        shapeDrift.parent = drift

        if self.dimension.has_front_wheels:
            for name in name_range('Ft.L', self.dimension.nb_front_wheels):
                self.generate_animation_wheel_bones(name, drift)
            self.generate_wheel_damper('Ft', 'L', drift)
            for name in name_range('Ft.R', self.dimension.nb_front_wheels):
                self.generate_animation_wheel_bones(name, drift)
            self.generate_wheel_damper('Ft', 'R', drift)

            wheelFtR = amt.edit_bones.get('DEF-Wheel.Ft.R')
            wheelFtL = amt.edit_bones.get('DEF-Wheel.Ft.L')

            wheels = amt.edit_bones.new('Front Wheels')
            wheels.head = wheelFtL.head
            wheels.tail = wheelFtL.tail
            wheels.head.x = math.copysign(wheelFtL.head.x + 1.1 * wheelFtL.head.z, wheels.head.x)
            wheels.tail.x = math.copysign(wheelFtL.tail.x + 1.1 * wheelFtL.head.z, wheels.tail.x)
            wheels.tail.y = wheels.head.y + wheels.head.z - (wheels.head.z / 10)
            wheels.use_deform = False
            wheels.parent = amt.edit_bones['GroundSensor.Ft.L']

            axisFt = amt.edit_bones.new('MCH-Axis.Ft')
            axisFt.head = wheelFtR.head
            axisFt.tail = wheelFtL.head
            axisFt.use_deform = False
            axisFt.parent = drift

            mchSteering = amt.edit_bones.new('MCH-Steering')
            mchSteering.head = self.dimension.wheels_front_position
            mchSteering.tail = self.dimension.wheels_front_position
            mchSteering.tail.y += self.dimension.length / 2
            mchSteering.use_deform = False
            mchSteering.parent = root

            steeringRotation = amt.edit_bones.new('MCH-Steering.rotation')
            steeringRotation.head = mchSteering.head
            steeringRotation.tail = mchSteering.head
            steeringRotation.tail.y += 1
            steeringRotation.use_deform = False

            steering = amt.edit_bones.new('Steering')
            steering.head = steeringRotation.head
            steering.tail = steeringRotation.tail
            steering.head.y -= self.dimension.length
            steering.tail.y -= self.dimension.length
            steering.use_deform = False
            steering.parent = steeringRotation

        if self.dimension.has_back_wheels:
            for name in name_range('Bk.L', self.dimension.nb_back_wheels):
                self.generate_animation_wheel_bones(name, drift)
            self.generate_wheel_damper('Bk', 'L', drift)
            for name in name_range('Bk.R', self.dimension.nb_back_wheels):
                self.generate_animation_wheel_bones(name, drift)
            self.generate_wheel_damper('Bk', 'R', drift)

            wheelBkR = amt.edit_bones.get('DEF-Wheel.Bk.R')
            wheelBkL = amt.edit_bones.get('DEF-Wheel.Bk.L')

            wheels = amt.edit_bones.new('Back Wheels')
            wheels.head = wheelBkL.head
            wheels.tail = wheelBkL.tail
            wheels.head.x = math.copysign(wheelBkL.head.x + 1.1 * wheelBkL.head.z, wheels.head.x)
            wheels.tail.x = math.copysign(wheelBkL.tail.x + 1.1 * wheelBkL.head.z, wheels.tail.x)
            wheels.tail.y = wheels.head.y + wheels.head.z - (wheels.head.z / 10)
            wheels.use_deform = False
            wheels.parent = amt.edit_bones['GroundSensor.Bk.L']

            axisBk = amt.edit_bones.new('MCH-Axis.Bk')
            axisBk.head = wheelBkR.head
            axisBk.tail = wheelBkL.head
            axisBk.use_deform = False
            axisBk.parent = drift

        suspensionBk = amt.edit_bones.new('MCH-Suspension.Bk')
        suspensionBk.head = self.dimension.suspension_back_position
        suspensionBk.tail = self.dimension.suspension_back_position
        suspensionBk.tail.y += 2
        suspensionBk.use_deform = False
        suspensionBk.parent = drift

        suspensionFt = amt.edit_bones.new('MCH-Suspension.Ft')
        suspensionFt.head = self.dimension.suspension_front_position
        align_vector = suspensionBk.head - suspensionFt.head
        align_vector.magnitude = 2
        suspensionFt.tail = self.dimension.suspension_front_position + align_vector
        suspensionFt.use_deform = False
        suspensionFt.parent = drift

        axis = amt.edit_bones.new('MCH-Axis')
        axis.head = suspensionFt.head
        axis.tail = suspensionBk.head
        axis.use_deform = False
        axis.parent = suspensionFt

        mchBody = amt.edit_bones.new('MCH-Body')
        mchBody.head = body.head
        mchBody.tail = body.tail
        mchBody.tail.y += 1
        mchBody.use_deform = False
        mchBody.parent = axis

        suspension = amt.edit_bones.new('Suspension')
        suspension.head = self.dimension.center
        suspension.tail = self.dimension.center
        suspension.tail.y += self.dimension.length / 2
        suspension.head.z = self.dimension.height * 1.2
        suspension.tail.z = self.dimension.height * 1.2
        suspension.use_deform = False
        suspension.parent = axis

    def generate_animation_wheel_bones(self, name_suffix, parent_bone):
        amt = self.ob.data

        def_wheel_bone = amt.edit_bones.get('DEF-Wheel.%s' % name_suffix)

        if def_wheel_bone is None:
            return

        ground_sensor = amt.edit_bones.new('GroundSensor.%s' % name_suffix)
        ground_sensor.head = def_wheel_bone.head
        ground_sensor.head.x = math.copysign(abs(def_wheel_bone.head.x) + def_wheel_bone.head.z * .4, ground_sensor.head.x)
        ground_sensor.tail.x = math.copysign(abs(def_wheel_bone.tail.x) + def_wheel_bone.head.z * .4, ground_sensor.head.x)
        ground_sensor.tail.y = ground_sensor.head.y + ground_sensor.head.z
        ground_sensor.head.z = 0
        ground_sensor.tail.z = 0
        ground_sensor.use_deform = False
        ground_sensor.parent = parent_bone

        mch_wheel = amt.edit_bones.new('MCH-Wheel.%s' % name_suffix)
        mch_wheel.head = def_wheel_bone.head
        mch_wheel.tail = def_wheel_bone.tail
        mch_wheel.tail.y += .5
        mch_wheel.use_deform = False
        mch_wheel.parent = ground_sensor

        self.ob['Wheel.rotation.%s' % name_suffix] = .0
        mch_wheel_rotation = amt.edit_bones.new('MCH-Wheel.rotation.%s' % name_suffix)
        mch_wheel_rotation.head = def_wheel_bone.head
        mch_wheel_rotation.tail = def_wheel_bone.head
        mch_wheel_rotation.tail.y += mch_wheel_rotation.tail.z
        mch_wheel_rotation.use_deform = False

        def_wheel_brake_bone = amt.edit_bones.get('DEF-WheelBrake.%s' % name_suffix)
        if def_wheel_brake_bone is not None:
            mch_wheel = amt.edit_bones.new('MCH-WheelBrake.%s' % name_suffix)
            mch_wheel.head = def_wheel_brake_bone.head
            mch_wheel.tail = def_wheel_brake_bone.tail
            mch_wheel.tail.y += .5
            mch_wheel.use_deform = False
            mch_wheel.parent = ground_sensor

    def generate_wheel_damper(self, position, side_position, parent_bone):
        amt = self.ob.data
        wheels = self.dimension.wheels(position, side_position)

        if wheels.nb == 1:
            wheel_damper_parent = amt.edit_bones['GroundSensor.%s.%s' % (position, side_position)]
        else:
            wheel_damper_parent = amt.edit_bones.new('MCH-GroundSensor.%s.%s' % (position, side_position))
            wheel_damper_parent.head = wheels.medium_position
            wheel_damper_parent.tail = wheels.medium_position
            wheel_damper_parent.tail.y += 1.0
            wheel_damper_parent.head.z = 0
            wheel_damper_parent.tail.z = 0
            wheel_damper_parent.use_deform = False
            wheel_damper_parent.parent = parent_bone

        wheel_damper = amt.edit_bones.new('WheelDamper.%s.%s' % (position, side_position))
        wheel_damper.head = wheels.medium_position
        wheel_damper.tail = wheels.medium_position
        wheel_damper.tail.y += abs(wheel_damper.tail.z)
        wheel_damper.head.x = math.copysign(abs(wheels.medium_position.x) + wheels.medium_position.z, wheel_damper.head.x)
        wheel_damper.tail.x = wheel_damper.head.x
        wheel_damper.head.z *= 1.5
        wheel_damper.tail.z *= 1.5
        wheel_damper.use_deform = False
        wheel_damper.parent = wheel_damper_parent

        mch_wheel_damper = amt.edit_bones.new('MCH-WheelDamper.%s.%s' % (position, side_position))
        mch_wheel_damper.head = wheels.medium_position
        mch_wheel_damper.tail = wheels.medium_position
        mch_wheel_damper.tail.y += 2
        mch_wheel_damper.use_deform = False
        mch_wheel_damper.parent = wheel_damper

    def generate_constraints_on_rig(self):
        pose = self.ob.pose
        amt = self.ob.data

        for b in pose.bones:
            if b.name.startswith('DEF-') or b.name.startswith('MCH-'):
                b.lock_location = (True, True, True)
                b.lock_rotation = (True, True, True)
                b.lock_scale = (True, True, True)
                b.lock_rotation_w = True

        for name in name_range('Ft.L', self.dimension.nb_front_wheels):
            self.generate_constraints_on_wheel_bones(name)
        self.generate_constraints_on_wheel_damper('Ft.L', self.dimension.nb_front_wheels)

        for name in name_range('Ft.R', self.dimension.nb_front_wheels):
            self.generate_constraints_on_wheel_bones(name)
        self.generate_constraints_on_wheel_damper('Ft.R', self.dimension.nb_front_wheels)

        for name in name_range('Bk.L', self.dimension.nb_back_wheels):
            self.generate_constraints_on_wheel_bones(name)
        self.generate_constraints_on_wheel_damper('Bk.L', self.dimension.nb_back_wheels)

        for name in name_range('Bk.R', self.dimension.nb_back_wheels):
            self.generate_constraints_on_wheel_bones(name)
        self.generate_constraints_on_wheel_damper('Bk.R', self.dimension.nb_back_wheels)

        self.generate_constraints_on_axle_bones('Ft')
        self.generate_constraints_on_axle_bones('Bk')

        root = pose.bones['Root']
        cns = root.constraints.new('SHRINKWRAP')
        cns.name = 'Ground projection'
        cns.shrinkwrap_type = 'PROJECT'
        cns.project_axis_space = 'LOCAL'
        cns.project_axis = 'NEG_Z'
        cns.distance = 0

        mch_axis = pose.bones.get('MCH-Axis')
        if mch_axis is not None:
            for axis_pos, influence in (('Ft', 1), ('Bk', .5)):
                subtarget = 'MCH-Axis.%s' % axis_pos
                if subtarget in pose.bones:
                    cns = mch_axis.constraints.new('TRANSFORM')
                    cns.name = 'Rotation from %s' % subtarget
                    cns.target = self.ob
                    cns.subtarget = subtarget
                    cns.map_from = 'ROTATION'
                    cns.from_min_x_rot = math.radians(-180)
                    cns.from_max_x_rot = math.radians(180)
                    cns.map_to_y_from = 'X'
                    cns.map_to = 'ROTATION'
                    cns.to_min_y_rot = math.radians(180)
                    cns.to_max_y_rot = math.radians(-180)
                    cns.owner_space = 'LOCAL'
                    cns.target_space = 'LOCAL'
                    create_constraint_influence_driver(self.ob, cns, '["suspension_rolling_factor"]', base_influence=influence)

        shapeRoot = pose.bones['SHP-Root']
        shapeRoot.lock_location = (True, True, True)
        shapeRoot.lock_rotation = (True, True, True)
        shapeRoot.lock_scale = (True, True, True)
        shapeRoot.lock_rotation_w = True
        amt.bones['SHP-Root'].hide = True

        root = pose.bones['Root']
        root.lock_scale = (True, True, True)
        root.custom_shape = bpy.data.objects['WGT-CarRig.Root']
        root.custom_shape_transform = shapeRoot
        amt.bones[root.name].show_wire = True

        shapeDrift = pose.bones['SHP-Drift']
        shapeDrift.lock_location = (True, True, True)
        shapeDrift.lock_rotation = (True, True, True)
        shapeDrift.lock_scale = (True, True, True)
        shapeDrift.lock_rotation_w = True
        amt.bones['SHP-Drift'].hide = True

        drift = pose.bones['Drift']
        drift.lock_location = (True, True, True)
        drift.lock_rotation = (True, True, False)
        drift.lock_scale = (True, True, True)
        drift.rotation_mode = 'ZYX'
        drift.custom_shape = bpy.data.objects['WGT-CarRig.DriftHandle']
        drift.custom_shape_transform = shapeDrift
        amt.bones[drift.name].show_wire = True

        suspension = pose.bones['Suspension']
        suspension.lock_rotation = (True, True, True)
        suspension.lock_scale = (True, True, True)
        suspension.lock_rotation_w = True
        suspension.custom_shape = bpy.data.objects['WGT-CarRig.Suspension']
        amt.bones[suspension.name].show_wire = True

        steering = pose.bones.get('Steering')
        if steering is not None:
            steering.lock_location = (False, True, True)
            steering.lock_rotation = (True, True, True)
            steering.lock_scale = (True, True, True)
            steering.lock_rotation_w = True
            steering.custom_shape = bpy.data.objects['WGT-CarRig.Steering']
            amt.bones[steering.name].show_wire = True

            mch_steering_rotation = pose.bones['MCH-Steering.rotation']
            mch_steering_rotation.rotation_mode = 'ZYX'
            cns = mch_steering_rotation.constraints.new('CHILD_OF')
            cns.target = self.ob
            cns.subtarget = 'Root'
            cns.inverse_matrix = self.ob.data.bones['Root'].matrix_local.inverted()
            cns.use_location_x = True
            cns.use_location_y = True
            cns.use_location_z = True
            cns.use_rotation_x = True
            cns.use_rotation_y = True
            cns.use_rotation_z = True
            self.ob['Steering.rotation'] = .0
            create_translation_x_driver(self.ob, mch_steering_rotation, '["Steering.rotation"]')

            mch_steering = pose.bones['MCH-Steering']
            cns = mch_steering.constraints.new('DAMPED_TRACK')
            cns.name = 'Track steering bone'
            cns.target = self.ob
            cns.subtarget = 'Steering'
            cns.track_axis = 'TRACK_NEGATIVE_Y'

            cns = mch_steering.constraints.new('COPY_ROTATION')
            cns.name = 'Drift counter animation'
            cns.target = self.ob
            cns.subtarget = 'Drift'
            cns.use_x = False
            cns.use_y = False
            cns.use_z = True
            cns.use_offset = True
            cns.owner_space = 'LOCAL'
            cns.target_space = 'LOCAL'

        mch_body = self.ob.pose.bones['MCH-Body']
        cns = mch_body.constraints.new('TRANSFORM')
        cns.name = 'Suspension on rollover'
        cns.target = self.ob
        cns.subtarget = 'Suspension'
        cns.map_from = 'LOCATION'
        cns.from_min_x = -2
        cns.from_max_x = 2
        cns.from_min_y = -2
        cns.from_max_y = 2
        cns.map_to_x_from = 'Y'
        cns.map_to_y_from = 'X'
        cns.map_to = 'ROTATION'
        cns.to_min_x_rot = math.radians(6)
        cns.to_max_x_rot = math.radians(-6)
        cns.to_min_y_rot = math.radians(-7)
        cns.to_max_y_rot = math.radians(7)
        cns.owner_space = 'LOCAL'
        cns.target_space = 'LOCAL'

        cns = mch_body.constraints.new('TRANSFORM')
        cns.name = 'Suspension on vertical'
        cns.target = self.ob
        cns.subtarget = 'Suspension'
        cns.map_from = 'LOCATION'
        cns.from_min_z = -0.5
        cns.from_max_z = 0.5
        cns.map_to_z_from = 'Z'
        cns.map_to = 'LOCATION'
        cns.to_min_z = -0.1
        cns.to_max_z = 0.1
        cns.owner_space = 'LOCAL'
        cns.target_space = 'LOCAL'

        body = self.ob.pose.bones['DEF-Body']
        cns = body.constraints.new('COPY_TRANSFORMS')
        cns.target = self.ob
        cns.subtarget = 'MCH-Body'

    def generate_constraints_on_axle_bones(self, position):
        pos_name = 'Front' if position == 'Ft' else 'Back'
        pose = self.ob.pose
        amt = self.ob.data

        wheels = pose.bones.get('%s Wheels' % pos_name)
        if wheels is not None:
            wheels.rotation_mode = "XYZ"
            wheels.lock_location = (True, True, True)
            wheels.lock_rotation = (False, True, True)
            wheels.lock_scale = (True, False, False)
            wheels.custom_shape = bpy.data.objects['WGT-CarRig.Wheel']
            amt.bones[wheels.name].show_wire = True

            cns = wheels.constraints.new('LIMIT_SCALE')
            cns.name = 'Brakes'
            cns.use_transform_limit = True
            cns.owner_space = 'LOCAL'
            cns.use_max_x = True
            cns.use_min_x = True
            cns.min_x = 1.0
            cns.max_x = 1.0
            cns.use_max_y = True
            cns.use_min_y = True
            cns.min_y = .5
            cns.max_y = 1.0
            cns.use_max_z = True
            cns.use_min_z = True
            cns.min_z = .5
            cns.max_z = 1.0

        subtarget = 'MCH-Axis.%s' % position
        if subtarget in pose.bones:
            mch_suspension = pose.bones['MCH-Suspension.%s' % position]
            cns = mch_suspension.constraints.new('COPY_LOCATION')
            cns.name = 'Location from %s' % subtarget
            cns.target = self.ob
            cns.subtarget = subtarget
            cns.head_tail = .5
            cns.use_x = False
            cns.use_y = False
            cns.use_z = True
            cns.owner_space = 'WORLD'
            cns.target_space = 'WORLD'
            create_constraint_influence_driver(self.ob, cns, '["suspension_factor"]')

            if position == 'Ft':
                cns = mch_suspension.constraints.new('DAMPED_TRACK')
                cns.name = 'Track suspension back'
                cns.target = self.ob
                cns.subtarget = 'MCH-Suspension.Bk'
                cns.track_axis = 'TRACK_Y'

        mch_axis = pose.bones.get('MCH-Axis.%s' % position)
        if mch_axis is not None:
            cns = mch_axis.constraints.new('COPY_LOCATION')
            cns.name = 'Copy location from right wheel'
            cns.target = self.ob
            cns.subtarget = 'MCH-WheelDamper.%s.R' % position
            cns.use_x = True
            cns.use_y = True
            cns.use_z = True
            cns.owner_space = 'WORLD'
            cns.target_space = 'WORLD'

            mch_axis = pose.bones['MCH-Axis.%s' % position]
            cns = mch_axis.constraints.new('DAMPED_TRACK')
            cns.name = 'Track Left Wheel'
            cns.target = self.ob
            cns.subtarget = 'MCH-WheelDamper.%s.L' % position
            cns.track_axis = 'TRACK_Y'

    def generate_constraints_on_wheel_bones(self, name_suffix):
        pose = self.ob.pose
        amt = self.ob.data

        def_wheel = pose.bones.get('DEF-Wheel.%s' % name_suffix)
        if def_wheel is None:
            return

        cns = def_wheel.constraints.new('COPY_TRANSFORMS')
        cns.target = self.ob
        cns.subtarget = 'MCH-Wheel.%s' % name_suffix

        def_wheel_brake = pose.bones.get('DEF-WheelBrake.%s' % name_suffix)
        if def_wheel_brake is not None:
            cns = def_wheel_brake.constraints.new('COPY_TRANSFORMS')
            cns.target = self.ob
            cns.subtarget = 'MCH-WheelBrake.%s' % name_suffix

        ground_sensor = pose.bones['GroundSensor.%s' % name_suffix]
        ground_sensor.lock_location = (True, True, False)
        ground_sensor.lock_rotation = (True, True, True)
        ground_sensor.lock_rotation_w = True
        ground_sensor.lock_scale = (True, True, True)
        ground_sensor.custom_shape = bpy.data.objects['WGT-CarRig.GroundSensor']
        amt.bones[ground_sensor.name].show_wire = True

        if name_suffix.startswith('Ft.'):
            cns = ground_sensor.constraints.new('COPY_ROTATION')
            cns.name = 'Steering rotation'
            cns.target = self.ob
            cns.subtarget = 'MCH-Steering'
            cns.use_x = False
            cns.use_y = False
            cns.use_z = True
            cns.owner_space = 'LOCAL'
            cns.target_space = 'LOCAL'

        cns = ground_sensor.constraints.new('SHRINKWRAP')
        cns.name = 'Ground projection'
        cns.shrinkwrap_type = 'PROJECT'
        cns.project_axis_space = 'LOCAL'
        cns.project_axis = 'NEG_Z'
        cns.distance = 0

        cns = ground_sensor.constraints.new('LIMIT_LOCATION')
        cns.name = 'Ground projection limitation'
        cns.use_transform_limit = False
        cns.owner_space = 'LOCAL'
        cns.use_max_x = True
        cns.use_min_x = True
        cns.min_x = 0
        cns.max_x = 0
        cns.use_max_y = True
        cns.use_min_y = True
        cns.min_y = 0
        cns.max_y = 0
        cns.use_max_z = True
        cns.use_min_z = True
        cns.min_z = -.2
        cns.max_z = .2

        mch_wheel = pose.bones['MCH-Wheel.%s' % name_suffix]
        mch_wheel.rotation_mode = "XYZ"

        cns = mch_wheel.constraints.new('COPY_ROTATION')
        cns.name = 'Bake animation wheels'
        cns.target = self.ob
        cns.subtarget = 'MCH-Wheel.rotation.%s' % name_suffix
        cns.use_x = True
        cns.use_y = False
        cns.use_z = False
        cns.use_offset = False
        cns.owner_space = 'POSE'
        cns.target_space = 'POSE'

        cns = mch_wheel.constraints.new('TRANSFORM')
        cns.name = 'Wheel rotation along Y axis'
        cns.target = self.ob
        cns.subtarget = 'Root'
        cns.use_motion_extrapolate = True
        cns.map_from = 'LOCATION'
        cns.from_min_y = - math.pi * abs(mch_wheel.head.z if mch_wheel.head.z != 0 else 1)
        cns.from_max_y = - cns.from_min_y
        cns.map_to_x_from = 'Y'
        cns.map_to = 'ROTATION'
        cns.to_min_x_rot = math.pi
        cns.to_max_x_rot = -math.pi
        cns.owner_space = 'LOCAL'
        cns.target_space = 'LOCAL'

        create_constraint_influence_driver(self.ob, cns, '["wheels_on_y_axis"]')

        cns = mch_wheel.constraints.new('COPY_ROTATION')
        cns.name = 'Animation wheels'
        cns.target = self.ob
        cns.subtarget = '%s Wheels' % ('Front' if name_suffix.startswith('Ft.') else 'Back')
        cns.use_x = True
        cns.use_y = False
        cns.use_z = False
        cns.use_offset = True
        cns.owner_space = 'LOCAL'
        cns.target_space = 'LOCAL'

        mch_wheel_rotation = pose.bones['MCH-Wheel.rotation.%s' % name_suffix]
        mch_wheel_rotation.rotation_mode = "XYZ"
        cns = mch_wheel_rotation.constraints.new('CHILD_OF')
        cns.target = self.ob
        cns.subtarget = 'Root'
        cns.inverse_matrix = amt.bones['Root'].matrix_local.inverted()
        cns.use_location_x = True
        cns.use_location_y = True
        cns.use_location_z = True
        cns.use_rotation_x = True
        cns.use_rotation_y = True
        cns.use_rotation_z = True
        create_rotation_euler_x_driver(self.ob, mch_wheel_rotation, '["Wheel.rotation.%s"]' % name_suffix)

    def generate_constraints_on_wheel_damper(self, name_suffix, nb_wheels):
        pose = self.ob.pose
        amt = self.ob.data

        wheel_damper = pose.bones.get('WheelDamper.%s' % name_suffix)
        if wheel_damper is not None:
            wheel_damper.lock_location = (True, True, False)
            wheel_damper.lock_rotation = (True, True, True)
            wheel_damper.lock_rotation_w = True
            wheel_damper.lock_scale = (True, True, True)
            wheel_damper.custom_shape = bpy.data.objects['WGT-CarRig.WheelDamper']
            amt.bones[wheel_damper.name].show_wire = True

        mch_ground_sensor = pose.bones.get('MCH-GroundSensor.%s' % name_suffix)
        if mch_ground_sensor is not None:
            fcurve = mch_ground_sensor.driver_add('location', 2)
            drv = fcurve.driver
            drv.type = 'MAX'

            for i, ground_sensor_name in enumerate(name_range('GroundSensor.%s' % name_suffix, nb_wheels)):
                if ground_sensor_name in pose.bones:
                    var = drv.variables.new()
                    var.name = 'groundSensor%03d' % i
                    var.type = 'TRANSFORMS'

                    targ = var.targets[0]
                    targ.id = self.ob
                    targ.bone_target = ground_sensor_name
                    targ.transform_space = 'LOCAL_SPACE'
                    targ.transform_type = 'LOC_Z'

    def generate_bone_groups(self):
        pose = self.ob.pose
        create_bone_group(pose, 'Direction', color_set='THEME04', bone_names=('Root', 'Drift', 'SHP-Root', 'SHP-Drift'))
        create_bone_group(pose, 'Suspension', color_set='THEME09', bone_names=('Suspension', 'WheelDamper.Ft.L', 'WheelDamper.Ft.R', 'WheelDamper.Bk.L', 'WheelDamper.Bk.R'))
        create_bone_group(pose, 'Wheel', color_set='THEME03', bone_names=('Steering', 'Front Wheels', 'Back Wheels'))
        ground_sensor_names = tuple(name_range('GroundSensor.Ft.L', self.dimension.nb_front_wheels))
        ground_sensor_names += tuple(name_range('GroundSensor.Ft.R', self.dimension.nb_front_wheels))
        ground_sensor_names += tuple(name_range('GroundSensor.Bk.L', self.dimension.nb_back_wheels))
        ground_sensor_names += tuple(name_range('GroundSensor.Bk.R', self.dimension.nb_back_wheels))
        create_bone_group(pose, 'GroundSensor', color_set='THEME02', bone_names=ground_sensor_names)


class AddCarDeformationRigOperator(bpy.types.Operator):
    bl_idname = "object.armature_car_deformation_rig"
    bl_label = "Add car deformation rig"
    bl_description = "Creates the base rig for a car."
    bl_options = {'REGISTER', 'UNDO'}

    body_pos_delta = bpy.props.FloatVectorProperty(name='Delta Location',
                                                   description='Extra translation added to location of the car body',
                                                   size=3,
                                                   default=(0, 0, 0),
                                                   subtype='TRANSLATION')

    body_size_delta = bpy.props.FloatProperty(name='Delta Length',
                                              description='Extra length added to the car body',
                                              default=.0,
                                              subtype='DISTANCE')

    nb_front_wheels_pairs = bpy.props.IntProperty(name='Pairs',
                                                  description='Number of front wheels pairs',
                                                  default=1,
                                                  min=0)

    front_wheel_pos_delta = bpy.props.FloatVectorProperty(name='Delta Location',
                                                          description='Extra translation added to location of the front wheels',
                                                          size=3,
                                                          default=(0, 0, 0),
                                                          subtype='TRANSLATION')

    nb_back_wheels_pairs = bpy.props.IntProperty(name='Pairs',
                                                 description='Number of back wheels pairs',
                                                 default=1,
                                                 min=0)

    back_wheel_pos_delta = bpy.props.FloatVectorProperty(name='Delta Location',
                                                         description='Extra translation added to location of the back wheels',
                                                         size=3,
                                                         default=(0, 0, 0),
                                                         subtype='TRANSLATION')

    nb_front_wheel_brakes_pairs = bpy.props.IntProperty(name='Front Pairs',
                                                        description='Number of front wheel brakes pairs',
                                                        default=0,
                                                        min=0)

    front_wheel_brakes_pos_delta = bpy.props.FloatProperty(name='Front Delta Location',
                                                           description='Extra translation added to location of the front brakes',
                                                           default=0)

    nb_back_wheel_brakes_pairs = bpy.props.IntProperty(name='Back Pairs',
                                                       description='Number of back wheel brakes pairs',
                                                       default=0,
                                                       min=0)

    back_wheel_brakes_pos_delta = bpy.props.FloatProperty(name='Back Delta Location',
                                                          description='Extra translation added to location of the back brakes',
                                                          default=0)

    def draw(self, context):
        self.layout.label('Body')
        layout = self.layout.box()
        layout.prop(self, 'body_pos_delta')
        layout.prop(self, 'body_size_delta')
        self.layout.label('Front wheels')
        layout = self.layout.box()
        layout.prop(self, 'nb_front_wheels_pairs')
        layout.prop(self, 'front_wheel_pos_delta')
        self.layout.label('Back wheels')
        layout = self.layout.box()
        layout.prop(self, 'nb_back_wheels_pairs')
        layout.prop(self, 'back_wheel_pos_delta')
        self.layout.label('Brakes')
        layout = self.layout.box()
        layout.prop(self, 'nb_front_wheel_brakes_pairs')
        layout.prop(self, 'front_wheel_brakes_pos_delta')
        layout.prop(self, 'nb_back_wheel_brakes_pairs')
        layout.prop(self, 'back_wheel_brakes_pos_delta')

    def invoke(self, context, event):
        self.bones_position = {
            'Body':       mathutils.Vector((0.0,  0,  .8)),
            'Wheel.Ft.L': mathutils.Vector((0.9, -2,  .5)),
            'Wheel.Ft.R': mathutils.Vector((-.9, -2,  .5)),
            'Wheel.Bk.L': mathutils.Vector((0.9,  2,  .5)),
            'Wheel.Bk.R': mathutils.Vector((-.9,  2,  .5)),
            'WheelBrake.Ft.L': mathutils.Vector((0.8, -2,  .5)),
            'WheelBrake.Ft.R': mathutils.Vector((-.8, -2,  .5)),
            'WheelBrake.Bk.L': mathutils.Vector((0.8,  2,  .5)),
            'WheelBrake.Bk.R': mathutils.Vector((-.8,  2,  .5))
        }
        self.target_objects_name = {}

        has_body_target = self._find_target_object(context, 'Body')

        nb_wheels_ft_l = self._find_target_object_for_wheels(context, 'Wheel.Ft.L')
        nb_wheels_ft_r = self._find_target_object_for_wheels(context, 'Wheel.Ft.R')
        nb_wheels_bk_l = self._find_target_object_for_wheels(context, 'Wheel.Bk.L')
        nb_wheels_bk_r = self._find_target_object_for_wheels(context, 'Wheel.Bk.R')

        nb_wheel_brakes_ft_l = self._find_target_object_for_wheels(context, 'WheelBrake.Ft.L')
        nb_wheel_brakes_ft_r = self._find_target_object_for_wheels(context, 'WheelBrake.Ft.R')
        nb_wheel_brakes_bk_l = self._find_target_object_for_wheels(context, 'WheelBrake.Bk.L')
        nb_wheel_brakes_bk_r = self._find_target_object_for_wheels(context, 'WheelBrake.Bk.R')

        self.nb_front_wheels_pairs = max(nb_wheels_ft_l, nb_wheels_ft_r)
        self.nb_back_wheels_pairs = max(nb_wheels_bk_l, nb_wheels_bk_r)
        self.nb_front_wheel_brakes_pairs = max(nb_wheel_brakes_ft_l, nb_wheel_brakes_ft_r)
        self.nb_back_wheel_brakes_pairs = max(nb_wheel_brakes_bk_l, nb_wheel_brakes_bk_r)

        # if no target object has been found for body, we assume it may have no
        # target object for front and back wheels either.
        if not has_body_target:
            self.nb_front_wheels_pairs = max(1, self.nb_front_wheels_pairs)
            self.nb_back_wheels_pairs = max(1, self.nb_back_wheels_pairs)

        return self.execute(context)

    def _find_target_object_for_wheels(self, context, suffix_name):
        for count, name in enumerate(name_range(suffix_name)):
            if not self._find_target_object(context, name):
                return count

    def _find_target_object(self, context, name):
        for obj in context.selected_objects:
            if obj.name.endswith(name):
                self.target_objects_name[name] = obj.name
                self.bones_position[name] = obj.location.copy()
                return True
        return False

    def execute(self, context):
        """Creates the meta rig with basic bones"""
        amt = bpy.data.armatures.new('Car Rig Data')
        amt['Car Rig'] = False

        rig = bpy_extras.object_utils.object_data_add(context, amt, name='Car Rig')

        bpy.ops.object.mode_set(mode='EDIT')

        self._create_bone(rig, 'Body', delta_pos=self.body_pos_delta, delta_length=self.body_size_delta)

        self._create_wheel_bones(rig, 'Wheel.Ft.L', self.nb_front_wheels_pairs, self.front_wheel_pos_delta)
        self._create_wheel_bones(rig, 'Wheel.Ft.R', self.nb_front_wheels_pairs, self.front_wheel_pos_delta.reflect(mathutils.Vector((1, 0, 0))))
        self._create_wheel_bones(rig, 'Wheel.Bk.L', self.nb_back_wheels_pairs, self.back_wheel_pos_delta)
        self._create_wheel_bones(rig, 'Wheel.Bk.R', self.nb_back_wheels_pairs, self.back_wheel_pos_delta.reflect(mathutils.Vector((1, 0, 0))))

        front_wheel_brakes_delta_pos = self.front_wheel_pos_delta.copy()
        front_wheel_brakes_delta_pos.x = self.front_wheel_brakes_pos_delta
        self._create_wheel_bones(rig, 'WheelBrake.Ft.L', self.nb_front_wheel_brakes_pairs, front_wheel_brakes_delta_pos)
        self._create_wheel_bones(rig, 'WheelBrake.Ft.R', self.nb_front_wheel_brakes_pairs, front_wheel_brakes_delta_pos.reflect(mathutils.Vector((1, 0, 0))))
        back_wheel_brakes_delta_pos = self.back_wheel_pos_delta.copy()
        back_wheel_brakes_delta_pos.x = self.back_wheel_brakes_pos_delta
        self._create_wheel_bones(rig, 'WheelBrake.Bk.L', self.nb_back_wheel_brakes_pairs, back_wheel_brakes_delta_pos)
        self._create_wheel_bones(rig, 'WheelBrake.Bk.R', self.nb_back_wheel_brakes_pairs, back_wheel_brakes_delta_pos.reflect(mathutils.Vector((1, 0, 0))))

        deselect_edit_bones(rig)

        bpy.ops.object.mode_set(mode='OBJECT')

        return{'FINISHED'}

    def _create_bone(self, rig, name, delta_pos, delta_length=0):
        b = rig.data.edit_bones.new('DEF-' + name)

        b.head = self.bones_position[name] + delta_pos
        b.tail = b.head
        b.tail.y += delta_length
        if name == 'Body':
            b.tail.y += b.tail.z * 4
        else:
            b.tail.y += b.tail.z

        target_obj_name = self.target_objects_name.get(name)
        if target_obj_name is not None and target_obj_name in bpy.context.scene.objects:
            target_obj = bpy.context.scene.objects[target_obj_name]
            if name == 'Body':
                b.tail = b.head
                b.tail.y += target_obj.dimensions[1] / 2 if target_obj.dimensions and target_obj.dimensions[0] != 0 else 1
                b.tail.y += delta_length
            target_obj.parent = rig
            target_obj.parent_bone = b.name
            target_obj.parent_type = 'BONE'
            target_obj.location += rig.matrix_world.to_translation()
            target_obj.matrix_parent_inverse = (rig.matrix_world * mathutils.Matrix.Translation(b.tail)).inverted()

        return b

    def _create_wheel_bones(self, rig, base_wheel_name, nb_wheels, delta_pos):
        for wheel_name in name_range(base_wheel_name, nb_wheels):
            if wheel_name not in self.bones_position:
                wheel_position = previous_wheel_default_pos.copy()
                wheel_position.y += abs(previous_wheel.head.z * 2.2)
                self.bones_position[wheel_name] = wheel_position
            previous_wheel = self._create_bone(rig, wheel_name, delta_pos)
            previous_wheel_default_pos = self.bones_position[wheel_name]


class GenerateCarAnimationRigOperator(bpy.types.Operator):
    bl_idname = "pose.car_animation_rig_generate"
    bl_label = "Generate car animation rig"
    bl_description = "Creates the complete armature for animating the car."
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None and context.object.data is not None and
                'Car Rig' in context.object.data and not context.object.data['Car Rig'])

    def execute(self, context):
        if 'DEF-Body' not in context.object.data.bones:
            self.report({'ERROR'}, 'No bone named DEF-Body. This is not a valid armature!')
            return {"CANCELLED"}

        armature_generator = ArmatureGenerator(context.object)
        armature_generator.generate()
        return {"FINISHED"}


def register():
    bpy.utils.register_class(GenerateCarAnimationRigOperator)
    bpy.utils.register_class(AddCarDeformationRigOperator)


def unregister():
    bpy.utils.unregister_class(GenerateCarAnimationRigOperator)
    bpy.utils.unregister_class(AddCarDeformationRigOperator)


if __name__ == "__main__":
    register()

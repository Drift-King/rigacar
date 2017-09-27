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

import bpy
import mathutils
import math


class FCurvesEvaluator:
    """Encapsulates a bunch of FCurves for vector animations."""

    def __init__(self, fcurves, default_value):
        self.default_value = default_value
        self.fcurves = fcurves

    def evaluate(self, f):
        result = []
        for fcurve, value in zip(self.fcurves, self.default_value):
            if fcurve is not None:
                result.append(fcurve.evaluate(f))
            else:
                result.append(value)
        return result


class BakingOperator:
    frame_start = bpy.props.IntProperty(name='Start Frame', min=1)
    frame_end = bpy.props.IntProperty(name='End Frame', min=1)
    visual_keying = bpy.props.BoolProperty(name='Visual Keying', default=True)

    @classmethod
    def poll(cls, context):
        return ('Car Rig' in context.object.data and
                context.object.data['Car Rig'])

    def invoke(self, context, event):
        if context.object.animation_data is None:
            context.object.animation_data_create()
        if context.object.animation_data.action is None:
            context.object.animation_data.action = bpy.data.actions.new("%sAction" % context.object.name)

        action = context.object.animation_data.action
        self.frame_start, self.frame_end = action.frame_range

        return context.window_manager.invoke_props_dialog(self)

    def _create_rotation_evaluator(self, action, source_bone):
        fcurve_name = 'pose.bones["%s"].rotation_quaternion' % source_bone.name
        fc_root_rot = [action.fcurves.find(fcurve_name, i) for i in range(0, 4)]
        return FCurvesEvaluator(fc_root_rot, default_value=(1.0, .0, .0, .0))

    def _create_location_evaluator(self, action, source_bone):
        fcurve_name = 'pose.bones["%s"].location' % source_bone.name
        fc_root_loc = [action.fcurves.find(fcurve_name, i) for i in range(0, 3)]
        return FCurvesEvaluator(fc_root_loc, default_value=(.0, .0, .0))

    def _bake_action(self, context, source_bone):
        action = context.object.animation_data.action

        # saving context
        selected_bones = [b for b in context.object.data.bones if b.select]
        matrix_basis = context.object.pose.bones[source_bone.name].matrix_basis.copy()
        mode = context.object.mode

        bpy.ops.object.mode_set(mode='OBJECT')
        for b in selected_bones:
            b.select = False
        source_bone.select = True

        bpy.ops.nla.bake(frame_start=self.frame_start, frame_end=self.frame_end, only_selected=True, bake_types={'POSE'}, visual_keying=True)
        bpy.context.scene.update()
        baked_action = bpy.context.active_object.animation_data.action

        # restoring context
        for b in selected_bones:
            b.select = True
        context.object.pose.bones[source_bone.name].matrix_basis = matrix_basis
        bpy.context.active_object.animation_data.action = action
        bpy.ops.object.mode_set(mode=mode)

        return baked_action

    def _create_or_replace_fcurve(self, context, target_bone, data_path, data_index=0):
        action = context.object.animation_data.action
        fcurve_datapath = 'pose.bones["%s"].%s' % (target_bone.name, data_path)
        fc_rot = action.fcurves.find(fcurve_datapath, data_index)
        if fc_rot is not None:
            action.fcurves.remove(fc_rot)
        return action.fcurves.new(fcurve_datapath, data_index, target_bone.name)


class BakeWheelRotationOperator(bpy.types.Operator, BakingOperator):
    bl_idname = 'anim.car_wheels_rotation_bake'
    bl_label = 'Bake car wheels rotation'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if self.frame_end > self.frame_start:
            self._bake_wheel_rotation(context, context.object.data.bones['Root'], context.object.data.bones['MCH-Wheels'])
            context.object['wheels_on_y_axis'] = False
        return {'FINISHED'}

    def _evaluate_distance_per_frame(self, action, source_bone):
        locEvaluator = self._create_location_evaluator(action, source_bone)
        rotEvaluator = self._create_rotation_evaluator(action, source_bone)

        bone_init_vector = (source_bone.head_local - source_bone.tail_local).normalized()
        prev_pos = mathutils.Vector(locEvaluator.evaluate(self.frame_start))
        distance = 0
        prev_speed = 0
        for f in range(self.frame_start, self.frame_end + 1):
            pos = mathutils.Vector(locEvaluator.evaluate(f))
            rotation_quaternion = mathutils.Quaternion(rotEvaluator.evaluate(f))
            speed_vector = pos - prev_pos
            speed = speed_vector.magnitude
            root_orientation = rotation_quaternion * bone_init_vector
            distance += math.copysign(speed, root_orientation.dot(speed_vector))
            # yields only if speed has significantly changed (avoids unecessary keyframes)
            if abs(speed - prev_speed) > prev_speed / 100 or f == self.frame_end:
                prev_speed = speed
                yield f, distance
            prev_pos = pos

    def _bake_wheel_rotation(self, context, source_bone, target_bone):
        source_action = context.object.animation_data.action
        if self.visual_keying:
            source_action = self._bake_action(context, source_bone)

        try:
            fc_rot = self._create_or_replace_fcurve(context, target_bone, "rotation_euler")
            for f, distance in self._evaluate_distance_per_frame(source_action, source_bone):
                kf = fc_rot.keyframe_points.insert(f, distance)
                kf.interpolation = 'LINEAR'
        finally:
            if self.visual_keying:
                bpy.data.actions.remove(source_action)


class BakeSteeringOperator(bpy.types.Operator, BakingOperator):
    bl_idname = 'anim.car_steering_bake'
    bl_label = 'Bake car steering rotation'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if self.frame_end > self.frame_start:
            steering = context.object.data.bones['Steering']
            mch_steering = context.object.data.bones['MCH-Steering']
            distance = (steering.head - mch_steering.head).length
            self._bake_steering_rotation(context, distance, context.object.data.bones['Root'], context.object.data.bones['MCH-Steering.controller'])
        return {'FINISHED'}

    def _evaluate_rotation_per_frame(self, action, source_bone):
        rotEvaluator = self._create_rotation_evaluator(action, source_bone)

        bone_init_vector = (source_bone.head_local - source_bone.tail_local).normalized()
        current_rotation_quaternion = mathutils.Quaternion(rotEvaluator.evaluate(self.frame_start))
        current_bone_orientation = current_rotation_quaternion * bone_init_vector
        for f in range(self.frame_start, self.frame_end + 1):
            next_rotation_quaternion = mathutils.Quaternion(rotEvaluator.evaluate(f + 25))
            next_bone_orientation = next_rotation_quaternion * bone_init_vector
            rot_axis, rot_angle = current_rotation_quaternion.rotation_difference(next_rotation_quaternion).to_axis_angle()
            yield f, math.copysign(rot_angle, rot_axis.z * current_bone_orientation.dot(next_bone_orientation))
            current_rotation_quaternion = next_rotation_quaternion
            current_bone_orientation = next_bone_orientation

    def _bake_steering_rotation(self, context, distance, source_bone, target_bone):
        source_action = context.object.animation_data.action
        if self.visual_keying:
            source_action = self._bake_action(context, source_bone)

        try:
            fc_rot = self._create_or_replace_fcurve(context, target_bone, "location")

            for f, rotation_angle in self._evaluate_rotation_per_frame(source_action, source_bone):
                # TODO use correct ratio and correct bone
                fc_rot.keyframe_points.insert(f, math.tan(rotation_angle) * 10 * distance)
        finally:
            if self.visual_keying:
                bpy.data.actions.remove(source_action)


def register():
    bpy.utils.register_class(BakeWheelRotationOperator)
    bpy.utils.register_class(BakeSteeringOperator)


def unregister():
    bpy.utils.unregister_class(BakeWheelRotationOperator)
    bpy.utils.unregister_class(BakeSteeringOperator)


if __name__ == "__main__":
    register()
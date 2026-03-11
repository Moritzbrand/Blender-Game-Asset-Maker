# Purpose: mesh utils module.
# Example: import mesh_utils
import math

import bmesh
import bpy


class MeshUtils:
    @staticmethod
    def add_unsubdivide_modifier(obj, iterations=1):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        iterations = max(1, int(iterations))

        mod = obj.modifiers.new(name="GameReady Unsubdivide", type='DECIMATE')
        mod.decimate_type = 'UNSUBDIV'
        mod.iterations = iterations

        last_subsurf_index = -1
        for i, existing_mod in enumerate(obj.modifiers):
            if existing_mod == mod:
                continue
            if existing_mod.type == 'SUBSURF':
                last_subsurf_index = i

        current_index = len(obj.modifiers) - 1
        target_index = last_subsurf_index + 1 if last_subsurf_index >= 0 else current_index

        if target_index != current_index:
            obj.modifiers.move(current_index, target_index)

        return mod

    @staticmethod
    def add_unsubdivide_to_objects(objects, iterations=1):
        valid_objects = []

        for obj in objects:
            if obj is not None and obj.type == 'MESH':
                MeshUtils.add_unsubdivide_modifier(obj, iterations)
                valid_objects.append(obj)

        return valid_objects

    @staticmethod
    def remove_custom_normals(obj):
        bpy.ops.object.mode_set(mode='OBJECT')
        for selected_obj in bpy.context.selected_objects:
            selected_obj.select_set(False)

        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.mesh.customdata_custom_splitnormals_clear()

    @staticmethod
    def join_objects(context, objects):
        if not objects:
            return None

        if len(objects) == 1:
            return objects[0]

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        active_obj = objects[0]

        override = context.copy()
        override["active_object"] = active_obj
        override["object"] = active_obj
        override["selected_objects"] = objects
        override["selected_editable_objects"] = objects

        with context.temp_override(**override):
            bpy.ops.object.join()

        return active_obj

    @staticmethod
    def triangulate_object(obj):
        if obj is None or obj.type != 'MESH':
            raise ValueError("triangulate_object: obj must be a mesh object")

        mesh = obj.data

        bm = bmesh.new()
        bm.from_mesh(mesh)

        bmesh.ops.triangulate(bm, faces=bm.faces[:])

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        return obj

    @staticmethod
    def _is_valid_mesh_object(obj):
        try:
            return (
                obj is not None
                and obj.name in bpy.data.objects
                and obj.type == 'MESH'
                and obj.data is not None
            )
        except ReferenceError:
            return False

    @staticmethod
    def _is_volumetric_mesh(obj, volume_epsilon=1e-6):
        if not MeshUtils._is_valid_mesh_object(obj):
            return False

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.normal_update()

        try:
            if len(bm.faces) == 0:
                return False

            all_edges_manifold = all(edge.is_manifold for edge in bm.edges)
            volume = abs(bm.calc_volume())

            return all_edges_manifold and volume > volume_epsilon
        finally:
            bm.free()

    @staticmethod
    def _cleanup_union_result(obj, merge_distance=0.00001):
        if not MeshUtils._is_valid_mesh_object(obj):
            return obj

        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.normal_update()

        bmesh.ops.remove_doubles(
            bm,
            verts=list(bm.verts),
            dist=merge_distance,
        )

        if bm.faces:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

        bm.to_mesh(me)
        me.update()
        bm.free()

        return obj

    @staticmethod
    def _boolean_union_only(context, objects):
        objects = [obj for obj in objects if MeshUtils._is_valid_mesh_object(obj)]

        if not objects:
            return None

        if len(objects) == 1:
            return objects[0]

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        base = objects[0]
        all_inputs_manifold = all(MeshUtils._is_volumetric_mesh(obj) for obj in objects)

        for obj in context.selected_objects:
            obj.select_set(False)

        base.select_set(True)
        context.view_layer.objects.active = base

        for other in objects[1:]:
            if not MeshUtils._is_valid_mesh_object(other):
                continue

            mod = base.modifiers.new(name=f"GR_Union_{other.name}", type='BOOLEAN')
            mod.operation = 'UNION'
            mod.operand_type = 'OBJECT'
            mod.object = other
            mod.solver = 'MANIFOLD' if all_inputs_manifold else 'EXACT'

            override = context.copy()
            override["active_object"] = base
            override["object"] = base
            override["selected_objects"] = [base]
            override["selected_editable_objects"] = [base]

            with context.temp_override(**override):
                bpy.ops.object.modifier_apply(modifier=mod.name)

            if MeshUtils._is_valid_mesh_object(other):
                bpy.data.objects.remove(other, do_unlink=True)

        return MeshUtils._cleanup_union_result(base)

    @staticmethod
    def union(context, new_objects):
        mesh_objects = [obj for obj in new_objects if MeshUtils._is_valid_mesh_object(obj)]

        if not mesh_objects:
            return None

        volumetric_objects = []
        floating_objects = []

        for obj in mesh_objects:
            if MeshUtils._is_volumetric_mesh(obj):
                volumetric_objects.append(obj)
            else:
                floating_objects.append(obj)

        union_result = MeshUtils._boolean_union_only(context, volumetric_objects)

        if union_result and floating_objects:
            combined = [union_result] + [
                obj for obj in floating_objects if MeshUtils._is_valid_mesh_object(obj)
            ]
            return MeshUtils.join_objects(context, combined)

        if union_result:
            return union_result

        return MeshUtils.join_objects(context, floating_objects)

    @staticmethod
    def decimate_planar(obj, angle_degrees=5.0, apply_modifier=True, context=None):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        ctx = context or bpy.context

        if ctx.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        mod = obj.modifiers.new(name="Planar Decimate", type='DECIMATE')
        mod.decimate_type = 'DISSOLVE'
        mod.angle_limit = math.radians(angle_degrees)
        mod.use_dissolve_boundaries = False

        if apply_modifier:
            ctx.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=mod.name)

    @staticmethod
    def decimate_collapse(obj, ratio=0.5, apply_modifier=True, context=None):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        ctx = context or bpy.context

        if ctx.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        mod = obj.modifiers.new(name="Collapse Decimate", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio

        if apply_modifier:
            ctx.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=mod.name)

    @staticmethod
    def merge_by_distance(context, obj, distance=0.0001):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        for other in context.selected_objects:
            other.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        if context.mode != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=distance)
        bpy.ops.object.mode_set(mode='OBJECT')

    @staticmethod
    def apply_modifiers_to_selected(context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        selected_mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        for obj in selected_mesh_objects:
            for other in context.selected_objects:
                other.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj

            modifier_names = [mod.name for mod in obj.modifiers]

            for mod_name in modifier_names:
                if mod_name not in obj.modifiers:
                    continue

                override = context.copy()
                override["active_object"] = obj
                override["object"] = obj
                override["selected_objects"] = [obj]
                override["selected_editable_objects"] = [obj]

                with context.temp_override(**override):
                    bpy.ops.object.modifier_apply(modifier=mod_name)

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
    def get_triangle_count(obj):
        if not MeshUtils._is_valid_mesh_object(obj):
            return 0

        mesh = obj.data
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)

    @staticmethod
    def get_bounding_box_surface_area(obj, epsilon=1e-6):
        if not MeshUtils._is_valid_mesh_object(obj):
            return epsilon

        dimensions = obj.dimensions
        x = max(abs(dimensions.x), 0.0)
        y = max(abs(dimensions.y), 0.0)
        z = max(abs(dimensions.z), 0.0)
        surface_area = 2.0 * ((x * y) + (x * z) + (y * z))
        return max(surface_area, epsilon)

    @staticmethod
    def get_triangle_density(obj, epsilon=1e-6):
        triangle_count = MeshUtils.get_triangle_count(obj)
        if triangle_count <= 0:
            return 0.0

        return triangle_count / MeshUtils.get_bounding_box_surface_area(obj, epsilon=epsilon)

    @staticmethod
    def _select_single_object(context, obj):
        for other in context.selected_objects:
            other.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

    @staticmethod
    def decimate_object_to_triangle_density(context, obj, max_density, minimum_ratio=0.01):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        triangle_count = MeshUtils.get_triangle_count(obj)
        if triangle_count <= 0:
            return False

        surface_area = MeshUtils.get_bounding_box_surface_area(obj)
        target_triangle_count = max(4.0, float(max_density) * surface_area)
        ratio = max(minimum_ratio, min(1.0, target_triangle_count / float(triangle_count)))

        if ratio >= 0.9999:
            return False

        MeshUtils.decimate_collapse(obj, ratio=ratio, apply_modifier=True, context=context)
        return True

    @staticmethod
    def limit_triangle_density_on_objects(context, objects, max_density):
        if max_density <= 0.0:
            return []

        changed_objects = []
        for obj in objects:
            if not MeshUtils._is_valid_mesh_object(obj):
                continue
            if MeshUtils.get_triangle_density(obj) <= max_density:
                continue
            if MeshUtils.decimate_object_to_triangle_density(context, obj, max_density):
                changed_objects.append(obj)

        if changed_objects:
            MeshUtils._select_single_object(context, changed_objects[0])

        return changed_objects

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

        selected_object_names = [obj.name for obj in context.selected_objects]
        active_object = context.view_layer.objects.active
        active_object_name = active_object.name if active_object is not None else ""

        selected_mesh_objects = [
            obj
            for obj in (bpy.data.objects.get(name) for name in selected_object_names)
            if obj is not None and obj.type == 'MESH'
        ]

        try:
            for obj in selected_mesh_objects:
                for other in list(context.selected_objects):
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
        finally:
            for other in list(context.selected_objects):
                other.select_set(False)

            restored_objects = []
            for name in selected_object_names:
                obj = bpy.data.objects.get(name)
                if obj is None:
                    continue
                obj.select_set(True)
                restored_objects.append(obj)

            restored_active = bpy.data.objects.get(active_object_name) if active_object_name else None
            if restored_active is None and restored_objects:
                restored_active = restored_objects[0]
            context.view_layer.objects.active = restored_active

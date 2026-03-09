import os

import bpy


class ExportUtils:
    @staticmethod
    def build_lod_ratios(lod_count):
        lod_count = max(0, int(lod_count))
        if lod_count == 0:
            return []

        step = 1.0 / (lod_count + 1)
        return [round(step * i, 6) for i in range(1, lod_count + 1)]

    @staticmethod
    def apply_collapse_decimate_for_export(context, obj, ratio):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        ratio = max(0.0, min(1.0, float(ratio)))

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for other in list(context.selected_objects):
            other.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        mod = obj.modifiers.new(name=f"LOD_Collapse_{ratio:.3f}", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio

        override = context.copy()
        override["active_object"] = obj
        override["object"] = obj
        override["selected_objects"] = [obj]
        override["selected_editable_objects"] = [obj]

        with context.temp_override(**override):
            bpy.ops.object.modifier_apply(modifier=mod.name)

        return obj

    @staticmethod
    def duplicate_object_for_export(context, obj, new_name=None):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        export_obj = obj.copy()

        if obj.data is not None:
            export_obj.data = obj.data.copy()

        context.collection.objects.link(export_obj)
        export_obj.matrix_world = obj.matrix_world.copy()

        if new_name:
            export_obj.name = new_name
            if export_obj.data is not None:
                export_obj.data.name = f"{new_name}_MESH"

        return export_obj

    @staticmethod
    def remove_all_materials(obj):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        obj.data.materials.clear()
        return obj

    @staticmethod
    def export_object_as_fbx(context, obj, output_dir, file_name=None):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        abs_output_dir = bpy.path.abspath(output_dir)
        os.makedirs(abs_output_dir, exist_ok=True)

        if not file_name:
            file_name = obj.name

        if not file_name.lower().endswith(".fbx"):
            file_name = f"{file_name}.fbx"

        export_path = os.path.join(abs_output_dir, file_name)

        previous_selected = list(context.selected_objects)
        previous_active = context.view_layer.objects.active

        try:
            for other in list(context.selected_objects):
                other.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj

            bpy.ops.export_scene.fbx(
                filepath=export_path,
                use_selection=True,
                axis_forward='-Y',
                axis_up='Z',
                global_scale=1.0,
                apply_unit_scale=True,
                use_space_transform=True,
                bake_space_transform=True,
                use_mesh_modifiers=True,
                use_mesh_modifiers_render=True,
            )
        finally:
            for other in list(context.selected_objects):
                other.select_set(False)

            for prev in previous_selected:
                if prev is not None and prev.name in bpy.data.objects:
                    prev.select_set(True)

            if previous_active is not None and previous_active.name in bpy.data.objects:
                context.view_layer.objects.active = previous_active

        return export_path

    @staticmethod
    def export_object_and_lods_as_fbx(context, obj, output_dir, lod_count):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        exported_paths = []

        export_copy = ExportUtils.duplicate_object_for_export(
            context,
            obj,
            new_name=f"{obj.name}_FBX_EXPORT",
        )
        ExportUtils.remove_all_materials(export_copy)

        try:
            exported_paths.append(
                ExportUtils.export_object_as_fbx(
                    context=context,
                    obj=export_copy,
                    output_dir=output_dir,
                    file_name=obj.name,
                )
            )
        finally:
            existing = bpy.data.objects.get(export_copy.name)
            if existing is not None:
                bpy.data.objects.remove(existing, do_unlink=True)

        ratios = ExportUtils.build_lod_ratios(lod_count)

        for lod_index, ratio in enumerate(reversed(ratios), start=1):
            lod_obj = ExportUtils.duplicate_object_for_export(
                context,
                obj,
                new_name=f"{obj.name}_LOD{lod_index}_FBX_EXPORT",
            )
            ExportUtils.remove_all_materials(lod_obj)
            ExportUtils.apply_collapse_decimate_for_export(context, lod_obj, ratio)

            try:
                exported_paths.append(
                    ExportUtils.export_object_as_fbx(
                        context=context,
                        obj=lod_obj,
                        output_dir=output_dir,
                        file_name=f"{obj.name}_LOD{lod_index}",
                    )
                )
            finally:
                existing = bpy.data.objects.get(lod_obj.name)
                if existing is not None:
                    bpy.data.objects.remove(existing, do_unlink=True)

        return exported_paths

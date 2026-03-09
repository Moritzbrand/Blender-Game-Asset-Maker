# operators.py

import math
import bpy

from .scripts.baking_utils import BakingUtils
from .scripts.cycles_utils import CyclesUtils
from .scripts.export_utils import ExportUtils
from .scripts.image_utils import ImageUtils
from .scripts.material_utils import MaterialUtils
from .scripts.mesh_utils import MeshUtils
from .scripts.object_utils import ObjectUtils


class GAMEREADY_OT_create_game_asset(bpy.types.Operator):
    bl_idname = "gameready.create_game_asset"
    bl_label = "Create Game Asset"
    bl_description = "Create a game asset from the active object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                return False
        return (
            context.active_object is not None
            and context.mode == 'OBJECT'
            and context.active_object.type == 'MESH'
        )

    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        selected_objects = list(context.selected_objects)

        visibility_state = {}

        # -------------------------
        # High-poly bake source
        # -------------------------
        temporary_objects = ObjectUtils.duplicate_selected(context)

        if scene.gameready_apply_rot_scale:
            ObjectUtils.apply_transform_to_selected(context)

        MeshUtils.apply_modifiers_to_selected(context)
        temporary_obj = MeshUtils.join_objects(context, temporary_objects)
        temporary_obj.name = f"{obj.name}_temp"

        # -------------------------
        # Low-poly game asset inputs
        # -------------------------
        ObjectUtils.select_objects(context, selected_objects)
        new_objects = ObjectUtils.duplicate_selected(context)

        if scene.gameready_unsubdivide:
            MeshUtils.add_unsubdivide_to_objects(
                new_objects,
                scene.gameready_unsubdivide_iterations * 2,
            )

        if scene.gameready_apply_rot_scale:
            ObjectUtils.apply_transform_to_selected(context)

        MeshUtils.apply_modifiers_to_selected(context)

        game_asset = MeshUtils.union(context, new_objects)
        game_asset.name = f"{obj.name}_game"

        if scene.gameready_merge_by_distance:
            merge_distance = scene.gameready_merge_distance
            MeshUtils.merge_by_distance(context, game_asset, merge_distance)

        if scene.gameready_collapse:
            MeshUtils.decimate_collapse(game_asset, scene.gameready_collapse_ratio)

        if scene.gameready_remove_planar_vertices:
            angle_limit = scene.gameready_planar_angle_limit
            MeshUtils.decimate_planar(game_asset, angle_limit)

        if scene.gameready_triangulate:
            MeshUtils.triangulate_object(game_asset)

        MeshUtils.remove_custom_normals(game_asset)
        bpy.context.view_layer.objects.active = game_asset
        game_asset.select_set(True)

        if scene.gameready_shade_auto_smooth:
            bpy.ops.object.shade_auto_smooth(
                angle=math.radians(scene.gameready_auto_smooth_angle)
            )
        else:
            bpy.ops.object.shade_flat()

        if scene.gameready_uv_unwrap:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(island_margin=0.03)
            bpy.ops.object.mode_set(mode='OBJECT')

        if scene.gameready_bake_textures:
            CyclesUtils.configure_cycles(
                context.scene,
                samples=scene.gameready_sample_count,
            )
            _, created_images = MaterialUtils.setup_bake_material(game_asset, scene)

            rendered_objects = BakingUtils.get_all_rendered_objects(context)
            objects_to_hide = [
                rendered_obj for rendered_obj in rendered_objects
                if rendered_obj not in {temporary_obj, game_asset}
            ]
            visibility_state = BakingUtils.store_render_visibility(objects_to_hide)
            BakingUtils.hide_from_render(objects_to_hide)

            texture_size = int(scene.gameready_texture_size)
            bake_margin = texture_size // 8

            if scene.gameready_bake_normal and "normal" in created_images:
                BakingUtils.bake_normal_selected_to_active(
                    context=context,
                    source_obj=temporary_obj,
                    target_obj=game_asset,
                    target_image=created_images["normal"],
                    extrusion=scene.gameready_cage_extrusion,
                    margin=bake_margin,
                )

                if scene.gameready_flip_y_normal:
                    ImageUtils.flip_normal_map_y(created_images["normal"])

            if scene.gameready_bake_ao and "ao" in created_images:
                BakingUtils.bake_ao_selected_to_active(
                    context=context,
                    source_obj=temporary_obj,
                    target_obj=game_asset,
                    target_image=created_images["ao"],
                    extrusion=scene.gameready_cage_extrusion,
                    margin=bake_margin,
                )

            if (
                scene.gameready_bake_base_color
                or scene.gameready_bake_alpha
                or scene.gameready_bake_roughness
                or scene.gameready_bake_metallic
                or scene.gameready_bake_emission
            ):
                MaterialUtils.make_materials_single_user(temporary_obj)

            if scene.gameready_bake_base_color and "base_color" in created_images:
                if (
                    scene.gameready_bake_alpha
                    and "base_color_rgb_tmp" in created_images
                    and "base_color_alpha_tmp" in created_images
                ):
                    BakingUtils.prepare_object_materials_for_emit_bake(
                        temporary_obj,
                        "BASE_COLOR",
                    )
                    BakingUtils.bake_emit_selected_to_active(
                        context=context,
                        source_obj=temporary_obj,
                        target_obj=game_asset,
                        target_image=created_images["base_color_rgb_tmp"],
                        extrusion=scene.gameready_cage_extrusion,
                        margin=bake_margin,
                    )

                    BakingUtils.prepare_object_materials_for_emit_bake(
                        temporary_obj,
                        "ALPHA",
                    )
                    BakingUtils.bake_emit_selected_to_active(
                        context=context,
                        source_obj=temporary_obj,
                        target_obj=game_asset,
                        target_image=created_images["base_color_alpha_tmp"],
                        extrusion=scene.gameready_cage_extrusion,
                        margin=bake_margin,
                    )

                    ImageUtils.debug_grayscale_range(
                        created_images["base_color_alpha_tmp"],
                        "Alpha TMP",
                    )
                    ImageUtils.combine_rgb_and_alpha_images(
                        created_images["base_color_rgb_tmp"],
                        created_images["base_color_alpha_tmp"],
                        created_images["base_color"],
                    )
                    ImageUtils.debug_grayscale_range(
                        created_images["base_color"],
                        "Final BaseColor",
                    )
                else:
                    BakingUtils.prepare_object_materials_for_emit_bake(
                        temporary_obj,
                        "BASE_COLOR",
                    )
                    BakingUtils.bake_emit_selected_to_active(
                        context=context,
                        source_obj=temporary_obj,
                        target_obj=game_asset,
                        target_image=created_images["base_color"],
                        extrusion=scene.gameready_cage_extrusion,
                        margin=bake_margin,
                    )

            if scene.gameready_bake_roughness and "roughness" in created_images:
                BakingUtils.prepare_object_materials_for_emit_bake(
                    temporary_obj,
                    "ROUGHNESS",
                )
                BakingUtils.bake_emit_selected_to_active(
                    context=context,
                    source_obj=temporary_obj,
                    target_obj=game_asset,
                    target_image=created_images["roughness"],
                    extrusion=scene.gameready_cage_extrusion,
                    margin=bake_margin,
                )

            if scene.gameready_bake_metallic and "metallic" in created_images:
                BakingUtils.prepare_object_materials_for_emit_bake(
                    temporary_obj,
                    "METALLIC",
                )
                BakingUtils.bake_emit_selected_to_active(
                    context=context,
                    source_obj=temporary_obj,
                    target_obj=game_asset,
                    target_image=created_images["metallic"],
                    extrusion=scene.gameready_cage_extrusion,
                    margin=bake_margin,
                )

            if (
                scene.gameready_pack_as_orm
                and "ao" in created_images
                and "roughness" in created_images
                and "metallic" in created_images
                and "orm" in created_images
            ):
                ImageUtils.combine_orm_images(
                    created_images["ao"],
                    created_images["roughness"],
                    created_images["metallic"],
                    created_images["orm"],
                )

            if scene.gameready_bake_emission and "emission" in created_images:
                BakingUtils.prepare_object_materials_for_emit_bake(
                    temporary_obj,
                    "EMISSION",
                )
                BakingUtils.bake_emit_selected_to_active(
                    context=context,
                    source_obj=temporary_obj,
                    target_obj=game_asset,
                    target_image=created_images["emission"],
                    extrusion=scene.gameready_cage_extrusion,
                    margin=bake_margin,
                )

        BakingUtils.restore_render_visibility(visibility_state)

        bpy.data.objects.remove(temporary_obj, do_unlink=True)

        cleanup_stats = MaterialUtils.cleanup_unused_textures_and_materials(game_asset)

        exported_file_paths = []

        if scene.gameready_export_files:
            lod_count = scene.gameready_lod_count if scene.gameready_generate_lods else 0
            exported_file_paths = ExportUtils.export_object_and_lods(
                context=context,
                obj=game_asset,
                output_dir=scene.gameready_output_dir,
                lod_count=lod_count,
                export_format_identifier=scene.gameready_export_format,
                preset_identifier=scene.gameready_export_preset,
            )

        if scene.gameready_flip_y_normal and scene.gameready_bake_normal:
            MaterialUtils.apply_normal_y_display_fix_to_object(game_asset)

        message = (
            f"Game asset created: {obj.name} | "
            f"Removed unplugged texture nodes: {cleanup_stats['removed_nodes']}, "
            f"unused images: {cleanup_stats['removed_images']}, "
            f"unused materials: {cleanup_stats['removed_materials']}"
        )

        if exported_file_paths:
            message += f" | Exported Files: {', '.join(exported_file_paths)}"

        self.report({'INFO'}, message)
        return {'FINISHED'}

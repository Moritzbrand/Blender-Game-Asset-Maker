# Purpose: panel module.
# Example: import panel
import bpy

from .addon_operators.create_asset_preconditions import CreateAssetPreconditions


class GAMEREADY_PT_main_panel(bpy.types.Panel):
    bl_label = "Game Ready Addon"
    bl_idname = "GAMEREADY_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Game Ready'

    def draw(self, context):
        layout = self.layout
        window_manager = context.window_manager

        action_box = layout.box()
        action_box.label(text="Create", icon='MOD_BUILD')

        is_running = window_manager.gameready_progress_running
        precondition_evaluation = CreateAssetPreconditions.evaluate(context)
        disable_reasons = precondition_evaluation.blocking_issues
        warning_messages = precondition_evaluation.warnings

        if not is_running and disable_reasons:
            reason_box = action_box.box()
            reason_box.alert = True
            reason_box.label(text="Can't create asset yet:", icon='ERROR')
            for issue in disable_reasons:
                reason_box.label(text=issue.message, icon='DOT')

        if not is_running and warning_messages:
            warning_box = action_box.box()
            warning_box.label(text="Warnings:", icon='ERROR')
            for warning in warning_messages:
                warning_box.label(text=warning.message, icon='DOT')

        create_row = action_box.row()
        create_row.enabled = (not is_running) and (not disable_reasons)
        create_row.operator("gameready.create_game_asset", icon='DUPLICATE')

        if is_running:
            progress_box = layout.box()
            progress_box.label(text=window_manager.gameready_progress_title or "Processing", icon='TIME')
            progress_box.progress(
                factor=window_manager.gameready_progress_factor,
                type='BAR',
                text=f"{int(window_manager.gameready_progress_factor * 100)}%",
            )

            if window_manager.gameready_progress_detail:
                progress_box.label(text=window_manager.gameready_progress_detail, icon='INFO')

            if getattr(window_manager, "gameready_progress_is_baking", False):
                hint_box = progress_box.box()
                hint_box.label(text="Bake in progress", icon='RENDER_STILL')
                hint_box.label(text="Watch Blender's status bar for the live bake progress.")


class GAMEREADY_PT_settings_panel(bpy.types.Panel):
    bl_label = "Settings"
    bl_idname = "GAMEREADY_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Game Ready'
    bl_parent_id = "GAMEREADY_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        window_manager = context.window_manager
        layout.enabled = not window_manager.gameready_progress_running

        general_box = layout.box()
        general_box.label(text="General", icon='SETTINGS')
        general_box.prop(scene, "gameready_apply_rot_scale")

        export_box = layout.box()
        export_box.label(text="Export", icon='EXPORT')
        export_box.prop(scene, "gameready_export_files")
        export_sub = export_box.column()
        export_sub.enabled = scene.gameready_export_files
        export_sub.prop(scene, "gameready_output_dir")
        export_sub.prop(scene, "gameready_export_format")
        export_sub.prop(scene, "gameready_export_preset")
        export_sub.prop(scene, "gameready_material_export_strategy")

        material_box = layout.box()
        material_box.label(text="Material/Texture", icon='MATERIAL')
        material_box.prop(scene, "gameready_uv_unwrap")
        uv_margin_column = material_box.column()
        uv_margin_column.enabled = scene.gameready_uv_unwrap
        uv_margin_column.prop(scene, "gameready_uv_island_margin", slider=True)
        material_box.prop(scene, "gameready_shade_auto_smooth")
        sub_smooth = material_box.column()
        sub_smooth.enabled = scene.gameready_shade_auto_smooth
        sub_smooth.prop(scene, "gameready_auto_smooth_angle")
        material_box.prop(scene, "gameready_bake_textures")
        sub = material_box.column()
        sub.enabled = scene.gameready_bake_textures
        sub.prop(scene, "gameready_texture_size")
        sub.prop(scene, "gameready_texture_compression")
        sub.prop(scene, "gameready_bake_base_color")
        subsub = sub.column()
        subsub.enabled = scene.gameready_bake_base_color
        subsub.prop(scene, "gameready_bake_alpha")
        sub.prop(scene, "gameready_bake_emission")
        sub.prop(scene, "gameready_bake_sss")
        sub.prop(scene, "gameready_bake_normal")
        sub_flip = sub.column()
        sub_flip.enabled = scene.gameready_bake_normal
        sub_flip.prop(scene, "gameready_flip_y_normal")
        sub.prop(scene, "gameready_bake_ao")
        sub.prop(scene, "gameready_bake_roughness")
        sub.prop(scene, "gameready_bake_metallic")
        suborm = sub.column()
        suborm.enabled = (
            scene.gameready_bake_roughness
            and scene.gameready_bake_metallic
            and scene.gameready_bake_ao
        )
        suborm.prop(scene, "gameready_pack_as_orm")
        sub.prop(scene, "gameready_sample_count")
        sub.prop(scene, "gameready_auto_cage_extrusion")
        sub_cage_extrusion = sub.column()
        sub_cage_extrusion.enabled = not scene.gameready_auto_cage_extrusion
        sub_cage_extrusion.prop(scene, "gameready_cage_extrusion")

        mesh_box = layout.box()
        mesh_box.label(text="Mesh", icon='MESH_DATA')
        mesh_box.prop(scene, "gameready_bake_selected_to_active")

        mesh_options_box = mesh_box.column()
        mesh_options_box.enabled = not scene.gameready_bake_selected_to_active
        mesh_options_box.prop(scene, "gameready_unsubdivide")
        sub_unsubdivide = mesh_options_box.column()
        sub_unsubdivide.enabled = scene.gameready_unsubdivide and not scene.gameready_bake_selected_to_active
        sub_unsubdivide.prop(scene, "gameready_unsubdivide_iterations")
        mesh_options_box.prop(scene, "gameready_merge_by_distance")
        sub_merge = mesh_options_box.column()
        sub_merge.enabled = scene.gameready_merge_by_distance and not scene.gameready_bake_selected_to_active
        sub_merge.prop(scene, "gameready_merge_distance")
        mesh_options_box.prop(scene, "gameready_collapse")
        sub_collapse = mesh_options_box.column()
        sub_collapse.enabled = scene.gameready_collapse and not scene.gameready_bake_selected_to_active
        sub_collapse.prop(scene, "gameready_collapse_ratio")
        mesh_options_box.prop(scene, "gameready_remove_planar_vertices")
        sub = mesh_options_box.column()
        sub.enabled = scene.gameready_remove_planar_vertices and not scene.gameready_bake_selected_to_active
        sub.prop(scene, "gameready_planar_angle_limit")
        mesh_box.prop(scene, "gameready_triangulate")

        lod_box = mesh_box.box()
        sub_lod = lod_box.column()
        sub_lod.enabled = scene.gameready_export_files
        sub_lod.label(text="LOD", icon='MOD_DECIM')
        sub_lod.prop(scene, "gameready_generate_lods")
        sub = sub_lod.column()
        sub.enabled = scene.gameready_generate_lods and scene.gameready_export_files
        sub.prop(scene, "gameready_lod_count")

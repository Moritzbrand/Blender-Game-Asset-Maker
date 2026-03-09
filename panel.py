import bpy


class GAMEREADY_PT_main_panel(bpy.types.Panel):
    bl_label = "Game Ready Addon"
    bl_idname = "GAMEREADY_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Game Ready'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        action_box = layout.box()
        action_box.label(text="Create", icon='MOD_BUILD')

        create_row = action_box.row()
        create_row.enabled = not scene.gameready_job_running
        create_row.operator("gameready.create_game_asset", icon='DUPLICATE')

        if scene.gameready_job_running:
            progress_box = layout.box()
            progress_box.label(text="Processing", icon='TIME')
            progress_box.label(text=scene.gameready_job_current_step_label or "Working...")
            progress_box.prop(scene, "gameready_job_progress", slider=True, text="Progress")
            progress_box.label(text=scene.gameready_job_status_text)

            if scene.gameready_job_preview_image is not None:
                progress_box.label(text=f"Last Texture: {scene.gameready_job_preview_image.name}")
                progress_box.template_ID_preview(
                    scene,
                    "gameready_job_preview_image",
                    rows=3,
                    cols=6,
                )
        elif scene.gameready_job_result_text:
            result_box = layout.box()
            result_box.label(text="Last Result", icon='CHECKMARK')
            result_box.label(text=scene.gameready_job_result_text[:120])


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

        general_box = layout.box()
        general_box.label(text="General", icon='SETTINGS')
        general_box.prop(scene, "gameready_apply_rot_scale")

        export_box = layout.box()
        export_box.label(text="Export", icon='EXPORT')
        export_box.prop(scene, "gameready_export_files")
        export_sub = export_box.column()
        export_sub.enabled = scene.gameready_export_files and not scene.gameready_job_running
        export_sub.prop(scene, "gameready_output_dir")
        export_sub.prop(scene, "gameready_export_format")
        export_sub.prop(scene, "gameready_export_preset")
        export_sub.prop(scene, "gameready_material_export_strategy")

        material_box = layout.box()
        material_box.label(text="Material/Texture", icon='MATERIAL')
        material_box.enabled = not scene.gameready_job_running
        material_box.prop(scene, "gameready_uv_unwrap")
        material_box.prop(scene, "gameready_shade_auto_smooth")
        sub_smooth = material_box.column()
        sub_smooth.enabled = scene.gameready_shade_auto_smooth
        sub_smooth.prop(scene, "gameready_auto_smooth_angle")
        material_box.prop(scene, "gameready_bake_textures")
        sub = material_box.column()
        sub.enabled = scene.gameready_bake_textures
        sub.prop(scene, "gameready_texture_size")
        sub.prop(scene, "gameready_bake_base_color")
        subsub = sub.column()
        subsub.enabled = scene.gameready_bake_base_color
        subsub.prop(scene, "gameready_bake_alpha")
        sub.prop(scene, "gameready_bake_emission")
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
        sub.prop(scene, "gameready_cage_extrusion")

        mesh_box = layout.box()
        mesh_box.label(text="Mesh", icon='MESH_DATA')
        mesh_box.enabled = not scene.gameready_job_running
        mesh_box.prop(scene, "gameready_unsubdivide")
        sub_unsubdivide = mesh_box.column()
        sub_unsubdivide.enabled = scene.gameready_unsubdivide
        sub_unsubdivide.prop(scene, "gameready_unsubdivide_iterations")
        mesh_box.prop(scene, "gameready_merge_by_distance")
        sub_merge = mesh_box.column()
        sub_merge.enabled = scene.gameready_merge_by_distance
        sub_merge.prop(scene, "gameready_merge_distance")
        mesh_box.prop(scene, "gameready_collapse")
        sub_collapse = mesh_box.column()
        sub_collapse.enabled = scene.gameready_collapse
        sub_collapse.prop(scene, "gameready_collapse_ratio")
        mesh_box.prop(scene, "gameready_remove_planar_vertices")
        sub = mesh_box.column()
        sub.enabled = scene.gameready_remove_planar_vertices
        sub.prop(scene, "gameready_planar_angle_limit")
        mesh_box.prop(scene, "gameready_triangulate")

        lod_box = mesh_box.box()
        sub_lod = lod_box.column()
        sub_lod.enabled = scene.gameready_export_files and not scene.gameready_job_running
        sub_lod.label(text="LOD", icon='MOD_DECIM')
        sub_lod.prop(scene, "gameready_generate_lods")
        sub = sub_lod.column()
        sub.enabled = scene.gameready_generate_lods and scene.gameready_export_files
        sub.prop(scene, "gameready_lod_count")

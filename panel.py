# panel.py

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
        layout.operator("gameready.create_game_asset", icon='DUPLICATE')
        layout.prop(scene, "gameready_output_dir")


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

        # General Settings
        general_box = layout.box()
        general_box.label(text="General", icon='SETTINGS')
        general_box.prop(scene, "gameready_export_fbx")
        general_box.prop(scene, "gameready_apply_rot_scale")

        # Material/Texture Settings
        material_box = layout.box()
        material_box.label(text="Material/Texture", icon='MATERIAL')
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
        suborm.enabled = scene.gameready_bake_roughness and scene.gameready_bake_metallic and scene.gameready_bake_ao
        suborm.prop(scene, "gameready_pack_as_orm")
        sub.prop(scene, "gameready_sample_count")
        sub.prop(scene, "gameready_cage_extrusion")

        # Mesh Settings
        mesh_box = layout.box()
        mesh_box.label(text="Mesh", icon='MESH_DATA')
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

        # LOD Settings
        
        lod_box = mesh_box.box()
        sub_lod = lod_box.column()
        sub_lod.enabled = scene.gameready_export_fbx 
        sub_lod.label(text="LOD", icon='MOD_DECIM')
        sub_lod.prop(scene, "gameready_generate_lods")
        sub = sub_lod.column()
        sub.enabled = scene.gameready_generate_lods and scene.gameready_export_fbx
        sub.prop(scene, "gameready_lod_count")

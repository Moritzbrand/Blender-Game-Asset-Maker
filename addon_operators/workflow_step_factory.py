# Purpose: workflow step factory module.
# Example: import workflow_step_factory
from .models import WorkflowStep


class WorkflowStepFactory:
    def __init__(self, services):
        self.services = services

    def build(self, context):
        scene = context.scene
        steps: list[WorkflowStep] = []

        self._add(steps, "Preparing Source Objects", "Duplicating the selected objects for the high-poly bake source.", self.services.prepare_temporary_source, 4)
        self._add(steps, "Building Game Asset Mesh", "Creating the optimized game asset mesh.", self.services.build_game_asset_mesh, 8)
        self._add(steps, "Applying Shading", "Updating normals and shading on the new asset.", self.services.apply_shading, 2)

        if scene.gameready_uv_unwrap:
            self._add(steps, "Creating UVs", "Unwrapping the generated game asset.", self.services.uv_unwrap, 4, "UV unwrap finished.")

        if scene.gameready_bake_textures:
            self._add(steps, "Preparing Bake Material", "Creating placeholder images and the bake material.", self.services.prepare_bake_setup, 3)
            self._add(steps, "Preparing Source Materials", "Assigning temporary standard materials to source faces that have no material.", self.services.ensure_source_materials_for_bake, 1)
            self._add(steps, "Preparing Bake Visibility", "Hiding unrelated objects from render during baking.", self.services.prepare_bake_visibility, 1)

            self._add(steps, "Resolving Cage Extrusion", "Calculating the cage extrusion distance used for bake ray casting.", self.services.resolve_bake_extrusion, 1)

            if scene.gameready_bake_normal:
                self._add(steps, "Baking Normal Map", "Normal map bake is running. Watch Blender's status bar for the live bake progress.", self.services.bake_normal, 20, "The normal map bake finished.")
            if scene.gameready_bake_ao:
                self._add(steps, "Baking Ambient Occlusion", "AO bake is running. Watch Blender's status bar for the live bake progress.", self.services.bake_ao, 14, "The ambient occlusion bake finished.")

            self._build_emit_bake_steps(steps, scene)

            if scene.gameready_pack_as_orm and scene.gameready_bake_ao and scene.gameready_bake_roughness and scene.gameready_bake_metallic:
                self._add(steps, "Packing ORM Texture", "Combining AO, roughness, and metallic into the ORM texture.", self.services.pack_orm, 2)

            self._add(steps, "Restoring Scene Visibility", "Making hidden objects visible for rendering again.", self.services.restore_visibility, 1)
            self._add(steps, "Restoring Source Materials", "Removing temporary standard source materials created for baking.", self.services.restore_source_materials_after_bake, 1)

        self._add(steps, "Cleaning Up Materials", "Removing temporary and unused data blocks.", self.services.cleanup_materials, 2)

        if scene.gameready_export_files:
            export_weight = 5 + (scene.gameready_lod_count if scene.gameready_generate_lods else 0) * 2
            self._add(steps, "Exporting Files", "Writing the generated asset files to disk.", self.services.export_files, export_weight)

        if scene.gameready_flip_y_normal and scene.gameready_bake_normal:
            self._add(steps, "Restoring Blender Normal Preview", "Reinserting the Blender-only normal Y display fix after baking and export.", self.services.restore_blender_normal_preview, 1)

        if scene.gameready_bake_sss:
            self._add(steps, "Restoring Blender SSS Preview", "Reinserting the Blender-only subsurface preview texture after baking and export.", self.services.restore_blender_sss_preview, 1)

        self._add(steps, "Finalizing", "Selecting the new asset and removing temporary source objects.", self.services.finalize_scene, 1)
        return steps

    def _build_emit_bake_steps(self, steps, scene):
        if scene.gameready_bake_base_color:
            if scene.gameready_bake_alpha:
                self._add(steps, "Baking Base Color", "Base color bake is running. Watch Blender's status bar for the live bake progress.", lambda context: self.services.bake_emit_channel(context, "base_color_rgb_tmp", "BASE_COLOR"), 12)
                self._add(steps, "Baking Alpha", "Alpha bake is running. Watch Blender's status bar for the live bake progress.", lambda context: self.services.bake_emit_channel(context, "base_color_alpha_tmp", "ALPHA"), 8)
                self._add(steps, "Combining Base Color and Alpha", "Packing RGB and alpha into the final base color texture.", self.services.combine_base_color_and_alpha, 2)
            else:
                self._add(steps, "Baking Base Color", "Base color bake is running. Watch Blender's status bar for the live bake progress.", lambda context: self.services.bake_emit_channel(context, "base_color", "BASE_COLOR"), 12)

        emit_channels = [
            (scene.gameready_bake_roughness, "Baking Roughness", "Roughness bake is running. Watch Blender's status bar for the live bake progress.", "roughness", "ROUGHNESS", 8, ""),
            (scene.gameready_bake_metallic, "Baking Metallic", "Metallic bake is running. Watch Blender's status bar for the live bake progress.", "metallic", "METALLIC", 8, ""),
            (scene.gameready_bake_sss, "Baking Subsurface Scattering", "SSS bake is running. Watch Blender's status bar for the live bake progress.", "sss", "SSS", 10, "The subsurface scattering bake finished."),
            (scene.gameready_bake_emission, "Baking Emission", "Emission bake is running. Watch Blender's status bar for the live bake progress.", "emission", "EMISSION", 10, ""),
        ]
        for enabled, title, detail, image_key, material_channel, weight, completed in emit_channels:
            if enabled:
                self._add(steps, title, detail, lambda context, key=image_key, channel=material_channel: self.services.bake_emit_channel(context, key, channel), weight, completed)

    @staticmethod
    def _has_emit_channels(scene):
        return any([
            scene.gameready_bake_base_color,
            scene.gameready_bake_alpha,
            scene.gameready_bake_roughness,
            scene.gameready_bake_metallic,
            scene.gameready_bake_emission,
            scene.gameready_bake_sss,
        ])

    @staticmethod
    def _add(steps, title, detail, function, weight, completed_detail=""):
        steps.append(WorkflowStep(title, detail, function, float(weight), completed_detail))

import math
import bpy

from .scripts.baking_utils import BakingUtils
from .scripts.cycles_utils import CyclesUtils
from .scripts.export_utils import ExportUtils
from .scripts.image_utils import ImageUtils
from .scripts.material_utils import MaterialUtils
from .scripts.mesh_utils import MeshUtils
from .scripts.object_utils import ObjectUtils
from .scripts.progress_utils import ProgressUtils
from .scripts.uv_utils import UVUtils


class GAMEREADY_OT_result_dialog(bpy.types.Operator):
    bl_idname = "gameready.result_dialog"
    bl_label = "Game Asset Ready"
    bl_options = {'INTERNAL'}

    message: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self,
            width=480,
            title="Game Asset Ready",
            confirm_text="Done",
        )

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.label(text="The process finished successfully.", icon='CHECKMARK')
        column.label(text="You can now continue working with the created asset.")
        column.separator()

        for message_line in self.message.split("\n"):
            if message_line:
                column.label(text=message_line)

    def execute(self, context):
        return {'FINISHED'}


class GAMEREADY_OT_create_game_asset(bpy.types.Operator):
    bl_idname = "gameready.create_game_asset"
    bl_label = "Create Game Asset"
    bl_description = "Create a game asset from the active object"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _steps = None
    _completed_weight = 0.0
    _total_weight = 0.0
    _state = None

    @classmethod
    def poll(cls, context):
        if getattr(context.window_manager, "gameready_progress_running", False):
            return False

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                return False

        return (
            context.active_object is not None
            and context.mode == 'OBJECT'
            and context.active_object.type == 'MESH'
        )

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        scene = context.scene
        active_object = context.active_object

        self._state = {
            "source_object_name": active_object.name,
            "selected_object_names": [obj.name for obj in context.selected_objects],
            "temporary_obj_name": "",
            "game_asset_name": "",
            "created_image_names": {},
            "created_image_filepaths": {},
            "visibility_state": {},
            "cleanup_stats": {
                "removed_nodes": 0,
                "removed_images": 0,
                "removed_materials": 0,
            },
            "exported_file_paths": [],
            "bake_margin": max(1, int(scene.gameready_texture_size) // 8),
        }

        self._steps = self._build_steps(context)
        self._completed_weight = 0.0
        self._total_weight = sum(step["weight"] for step in self._steps) or 1.0

        ProgressUtils.reset(context.window_manager)
        ProgressUtils.begin(
            context,
            title="Preparing Game Asset",
            detail="The job has started.",
            factor=0.0,
        )

        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self._safe_cleanup(context)
            self._finish_modal(context)
            ProgressUtils.cancel(
                context,
                title="Cancelled",
                detail="Game asset creation was cancelled.",
            )
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}

        if not self._steps:
            self._safe_cleanup(context)
            result_message = self._build_result_message()
            self._finish_modal(context)
            ProgressUtils.finish(
                context,
                title="Finished",
                detail="The asset is ready.",
            )
            bpy.ops.gameready.result_dialog('INVOKE_DEFAULT', message=result_message)
            return {'FINISHED'}

        current_step = self._steps.pop(0)
        self._announce_step(context, current_step)

        try:
            current_step["function"](context)
        except Exception as exception:
            self._safe_cleanup(context)
            self._finish_modal(context)
            ProgressUtils.cancel(
                context,
                title="Failed",
                detail=f"{current_step['title']} failed: {exception}",
            )
            self.report({'ERROR'}, f"{current_step['title']} failed: {exception}")
            return {'CANCELLED'}

        self._completed_weight += current_step["weight"]
        progress_factor = self._completed_weight / self._total_weight

        ProgressUtils.update(
            context,
            factor=progress_factor,
            title=current_step["title"],
            detail=current_step.get("completed_detail", current_step["detail"]),
        )
        ProgressUtils.flush_ui()
        return {'RUNNING_MODAL'}

    def _announce_step(self, context, step):
        ProgressUtils.update(
            context,
            factor=self._completed_weight / self._total_weight,
            title=step["title"],
            detail=step["detail"],
        )
        ProgressUtils.flush_ui()

    def _finish_modal(self, context):
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None

    def _add_step(self, steps, title, detail, function, weight, completed_detail=None):
        steps.append(
            {
                "title": title,
                "detail": detail,
                "function": function,
                "weight": float(weight),
                "completed_detail": completed_detail or detail,
            }
        )

    def _build_steps(self, context):
        scene = context.scene
        steps = []

        self._add_step(
            steps,
            title="Preparing Source Objects",
            detail="Duplicating the selected objects for the high-poly bake source.",
            function=self._step_prepare_temporary_source,
            weight=4,
        )
        self._add_step(
            steps,
            title="Building Game Asset Mesh",
            detail="Creating the optimized game asset mesh.",
            function=self._step_build_game_asset_mesh,
            weight=8,
        )
        self._add_step(
            steps,
            title="Applying Shading",
            detail="Updating normals and shading on the new asset.",
            function=self._step_apply_shading,
            weight=2,
        )

        if scene.gameready_uv_unwrap:
            self._add_step(
                steps,
                title="Creating UVs",
                detail="Unwrapping the generated game asset.",
                function=self._step_uv_unwrap,
                weight=4,
                completed_detail="UV unwrap finished.",
            )

        if scene.gameready_bake_textures:
            self._add_step(
                steps,
                title="Preparing Bake Material",
                detail="Creating placeholder images and the bake material.",
                function=self._step_prepare_bake_setup,
                weight=3,
            )
            self._add_step(
                steps,
                title="Preparing Bake Visibility",
                detail="Hiding unrelated objects from render during baking.",
                function=self._step_prepare_bake_visibility,
                weight=1,
            )

            if self._has_any_emit_bake_channels(scene):
                self._add_step(
                    steps,
                    title="Preparing Source Materials",
                    detail="Making source materials single-user for emit-based bakes.",
                    function=self._step_make_source_materials_single_user,
                    weight=1,
                )

            if scene.gameready_bake_normal:
                self._add_step(
                    steps,
                    title="Baking Normal Map",
                    detail="Normal map bake is running. Watch Blender's status bar for the live bake progress.",
                    function=self._step_bake_normal,
                    weight=20,
                    completed_detail="The normal map bake finished.",
                )

            if scene.gameready_bake_ao:
                self._add_step(
                    steps,
                    title="Baking Ambient Occlusion",
                    detail="AO bake is running. Watch Blender's status bar for the live bake progress.",
                    function=self._step_bake_ao,
                    weight=14,
                    completed_detail="The ambient occlusion bake finished.",
                )

            if scene.gameready_bake_base_color:
                if scene.gameready_bake_alpha:
                    self._add_step(
                        steps,
                        title="Baking Base Color",
                        detail="Base color bake is running. Watch Blender's status bar for the live bake progress.",
                        function=self._step_bake_base_color_rgb,
                        weight=12,
                    )
                    self._add_step(
                        steps,
                        title="Baking Alpha",
                        detail="Alpha bake is running. Watch Blender's status bar for the live bake progress.",
                        function=self._step_bake_base_color_alpha,
                        weight=8,
                    )
                    self._add_step(
                        steps,
                        title="Combining Base Color and Alpha",
                        detail="Packing RGB and alpha into the final base color texture.",
                        function=self._step_combine_base_color_and_alpha,
                        weight=2,
                    )
                else:
                    self._add_step(
                        steps,
                        title="Baking Base Color",
                        detail="Base color bake is running. Watch Blender's status bar for the live bake progress.",
                        function=self._step_bake_base_color,
                        weight=12,
                    )

            if scene.gameready_bake_roughness:
                self._add_step(
                    steps,
                    title="Baking Roughness",
                    detail="Roughness bake is running. Watch Blender's status bar for the live bake progress.",
                    function=self._step_bake_roughness,
                    weight=8,
                )

            if scene.gameready_bake_metallic:
                self._add_step(
                    steps,
                    title="Baking Metallic",
                    detail="Metallic bake is running. Watch Blender's status bar for the live bake progress.",
                    function=self._step_bake_metallic,
                    weight=8,
                )

            if scene.gameready_bake_sss:
                self._add_step(
                    steps,
                    title="Baking Subsurface Scattering",
                    detail="SSS bake is running. Watch Blender's status bar for the live bake progress.",
                    function=self._step_bake_sss,
                    weight=10,
                    completed_detail="The subsurface scattering bake finished.",
                )

            if (
                scene.gameready_pack_as_orm
                and scene.gameready_bake_ao
                and scene.gameready_bake_roughness
                and scene.gameready_bake_metallic
            ):
                self._add_step(
                    steps,
                    title="Packing ORM Texture",
                    detail="Combining AO, roughness, and metallic into the ORM texture.",
                    function=self._step_pack_orm,
                    weight=2,
                )

            if scene.gameready_bake_emission:
                self._add_step(
                    steps,
                    title="Baking Emission",
                    detail="Emission bake is running. Watch Blender's status bar for the live bake progress.",
                    function=self._step_bake_emission,
                    weight=10,
                )

            self._add_step(
                steps,
                title="Restoring Scene Visibility",
                detail="Making hidden objects visible for rendering again.",
                function=self._step_restore_visibility,
                weight=1,
            )

        self._add_step(
            steps,
            title="Cleaning Up Materials",
            detail="Removing temporary and unused data blocks.",
            function=self._step_cleanup_materials,
            weight=2,
        )

        if scene.gameready_export_files:
            export_weight = 5 + (scene.gameready_lod_count if scene.gameready_generate_lods else 0) * 2
            self._add_step(
                steps,
                title="Exporting Files",
                detail="Writing the generated asset files to disk.",
                function=self._step_export_files,
                weight=export_weight,
            )

        if scene.gameready_flip_y_normal and scene.gameready_bake_normal:
            self._add_step(
                steps,
                title="Restoring Blender Normal Preview",
                detail="Reinserting the Blender-only normal Y display fix after baking and export.",
                function=self._step_restore_blender_normal_preview,
                weight=1,
            )

        if scene.gameready_bake_sss:
            self._add_step(
                steps,
                title="Restoring Blender SSS Preview",
                detail="Reinserting the Blender-only subsurface preview texture after baking and export.",
                function=self._step_restore_blender_sss_preview,
                weight=1,
            )

        self._add_step(
            steps,
            title="Finalizing",
            detail="Selecting the new asset and removing temporary source objects.",
            function=self._step_finalize_scene,
            weight=1,
        )

        return steps

    def _has_any_emit_bake_channels(self, scene):
        return (
            scene.gameready_bake_base_color
            or scene.gameready_bake_alpha
            or scene.gameready_bake_roughness
            or scene.gameready_bake_metallic
            or scene.gameready_bake_emission
            or scene.gameready_bake_sss
        )

    def _get_object(self, object_name):
        if not object_name:
            return None
        return bpy.data.objects.get(object_name)

    def _get_image(self, image_name):
        if not image_name:
            return None
        return bpy.data.images.get(image_name)

    def _get_created_image(self, image_key):
        image_name = self._state["created_image_names"].get(image_key, "")
        return self._get_image(image_name)

    def _get_created_image_filepath(self, image_key):
        return self._state["created_image_filepaths"].get(image_key, "")

    def _store_created_images(self, created_images):
        self._state["created_image_names"] = {
            image_key: image.name
            for image_key, image in created_images.items()
            if image is not None
        }
        self._state["created_image_filepaths"] = {
            image_key: str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", ""))
            for image_key, image in created_images.items()
            if image is not None
        }

    def _select_single_object(self, context, obj):
        for selected_object in list(context.selected_objects):
            selected_object.select_set(False)

        if obj is not None:
            obj.select_set(True)
            context.view_layer.objects.active = obj

    def _step_prepare_temporary_source(self, context):
        scene = context.scene
        selected_objects = [
            self._get_object(object_name)
            for object_name in self._state["selected_object_names"]
        ]
        selected_objects = [obj for obj in selected_objects if obj is not None]

        ObjectUtils.select_objects(context, selected_objects)
        temporary_objects = ObjectUtils.duplicate_selected(context)

        if scene.gameready_apply_rot_scale:
            ObjectUtils.apply_transform_to_selected(context)

        MeshUtils.apply_modifiers_to_selected(context)
        temporary_obj = MeshUtils.join_objects(context, temporary_objects)
        temporary_obj.name = f"{self._state['source_object_name']}_temp"
        self._state["temporary_obj_name"] = temporary_obj.name

    def _step_build_game_asset_mesh(self, context):
        scene = context.scene
        selected_objects = [
            self._get_object(object_name)
            for object_name in self._state["selected_object_names"]
        ]
        selected_objects = [obj for obj in selected_objects if obj is not None]

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
        game_asset.name = f"{self._state['source_object_name']}_game"

        if scene.gameready_merge_by_distance:
            MeshUtils.merge_by_distance(
                context,
                game_asset,
                scene.gameready_merge_distance,
            )

        if scene.gameready_collapse:
            MeshUtils.decimate_collapse(game_asset, scene.gameready_collapse_ratio)

        if scene.gameready_remove_planar_vertices:
            MeshUtils.decimate_planar(game_asset, scene.gameready_planar_angle_limit)

        if scene.gameready_triangulate:
            MeshUtils.triangulate_object(game_asset)

        MeshUtils.remove_custom_normals(game_asset)
        self._state["game_asset_name"] = game_asset.name
        self._select_single_object(context, game_asset)

    def _step_apply_shading(self, context):
        scene = context.scene
        game_asset = self._get_object(self._state["game_asset_name"])
        self._select_single_object(context, game_asset)

        if scene.gameready_shade_auto_smooth:
            bpy.ops.object.shade_auto_smooth(
                angle=math.radians(scene.gameready_auto_smooth_angle)
            )
        else:
            bpy.ops.object.shade_flat()

    def _step_uv_unwrap(self, context):
        game_asset = self._get_object(self._state["game_asset_name"])
        UVUtils.unwrap_object(context, game_asset)

    def _step_prepare_bake_setup(self, context):
        scene = context.scene
        game_asset = self._get_object(self._state["game_asset_name"])

        CyclesUtils.configure_cycles(
            scene,
            samples=scene.gameready_sample_count,
        )
        _, created_images = MaterialUtils.setup_bake_material(game_asset, scene)
        self._store_created_images(created_images)

    def _step_prepare_bake_visibility(self, context):
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        rendered_objects = BakingUtils.get_all_rendered_objects(context)
        objects_to_hide = [
            rendered_object
            for rendered_object in rendered_objects
            if rendered_object not in {temporary_obj, game_asset}
        ]
        self._state["visibility_state"] = BakingUtils.store_render_visibility(objects_to_hide)
        BakingUtils.hide_from_render(objects_to_hide)

    def _step_make_source_materials_single_user(self, context):
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        MaterialUtils.make_materials_single_user(temporary_obj)

    def _step_bake_normal(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        normal_image = self._get_created_image("normal")

        BakingUtils.bake_normal_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=normal_image,
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

        if scene.gameready_flip_y_normal:
            ImageUtils.flip_normal_map_y(normal_image, scene=scene)

    def _step_bake_ao(self, context):
        scene = context.scene
        BakingUtils.bake_ao_selected_to_active(
            context=context,
            source_obj=self._get_object(self._state["temporary_obj_name"]),
            target_obj=self._get_object(self._state["game_asset_name"]),
            target_image=self._get_created_image("ao"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_bake_base_color_rgb(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "BASE_COLOR")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("base_color_rgb_tmp"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_bake_base_color_alpha(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "ALPHA")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("base_color_alpha_tmp"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_combine_base_color_and_alpha(self, context):
        scene = context.scene
        alpha_image = self._get_created_image("base_color_alpha_tmp")
        final_image = self._get_created_image("base_color")
        ImageUtils.debug_grayscale_range(alpha_image, "Alpha TMP")
        ImageUtils.combine_rgb_and_alpha_images(
            self._get_created_image("base_color_rgb_tmp"),
            alpha_image,
            final_image,
            scene=scene,
        )
        ImageUtils.debug_grayscale_range(final_image, "Final BaseColor")

    def _step_bake_base_color(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "BASE_COLOR")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("base_color"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_bake_roughness(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "ROUGHNESS")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("roughness"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_bake_metallic(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "METALLIC")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("metallic"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_bake_sss(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "SSS")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("sss"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_pack_orm(self, context):
        ImageUtils.combine_orm_images(
            self._get_created_image("ao"),
            self._get_created_image("roughness"),
            self._get_created_image("metallic"),
            self._get_created_image("orm"),
            scene=context.scene,
        )

    def _step_bake_emission(self, context):
        scene = context.scene
        temporary_obj = self._get_object(self._state["temporary_obj_name"])
        game_asset = self._get_object(self._state["game_asset_name"])
        BakingUtils.prepare_object_materials_for_emit_bake(temporary_obj, "EMISSION")
        BakingUtils.bake_emit_selected_to_active(
            context=context,
            source_obj=temporary_obj,
            target_obj=game_asset,
            target_image=self._get_created_image("emission"),
            extrusion=scene.gameready_cage_extrusion,
            margin=self._state["bake_margin"],
        )

    def _step_restore_visibility(self, context):
        BakingUtils.restore_render_visibility(self._state["visibility_state"])
        self._state["visibility_state"] = {}

    def _step_cleanup_materials(self, context):
        game_asset = self._get_object(self._state["game_asset_name"])
        self._state["cleanup_stats"] = MaterialUtils.cleanup_unused_textures_and_materials(game_asset)

    def _step_export_files(self, context):
        scene = context.scene
        game_asset = self._get_object(self._state["game_asset_name"])
        lod_count = scene.gameready_lod_count if scene.gameready_generate_lods else 0
        self._state["exported_file_paths"] = ExportUtils.export_object_and_lods(
            context=context,
            obj=game_asset,
            output_dir=scene.gameready_output_dir,
            lod_count=lod_count,
            export_format_identifier=scene.gameready_export_format,
            preset_identifier=scene.gameready_export_preset,
            material_export_strategy_identifier=scene.gameready_material_export_strategy,
        )

    def _step_restore_blender_normal_preview(self, context):
        game_asset = self._get_object(self._state["game_asset_name"])
        if game_asset is not None:
            MaterialUtils.apply_normal_y_display_fix_to_object(game_asset)
            MaterialUtils.refresh_material_preview_on_object(game_asset, context=context)

    def _step_restore_blender_sss_preview(self, context):
        game_asset = self._get_object(self._state["game_asset_name"])
        if game_asset is None:
            return

        MaterialUtils.apply_sss_preview_to_object(
            obj=game_asset,
            image=self._get_created_image("sss"),
            image_filepath=self._get_created_image_filepath("sss"),
        )
        MaterialUtils.refresh_material_preview_on_object(game_asset, context=context)

    def _step_finalize_scene(self, context):
        game_asset = self._get_object(self._state["game_asset_name"])
        temporary_obj = self._get_object(self._state["temporary_obj_name"])

        self._select_single_object(context, game_asset)

        if game_asset is not None:
            MaterialUtils.refresh_material_preview_on_object(game_asset, context=context)

        if temporary_obj is not None:
            bpy.data.objects.remove(temporary_obj, do_unlink=True)
            self._state["temporary_obj_name"] = ""

    def _safe_cleanup(self, context):
        try:
            BakingUtils.restore_render_visibility(self._state.get("visibility_state", {}))
        except Exception:
            pass

        self._state["visibility_state"] = {}

        temporary_obj = self._get_object(self._state.get("temporary_obj_name", ""))
        if temporary_obj is not None:
            try:
                bpy.data.objects.remove(temporary_obj, do_unlink=True)
            except Exception:
                pass
            self._state["temporary_obj_name"] = ""

    def _build_result_message(self):
        source_name = self._state["source_object_name"]
        cleanup_stats = self._state["cleanup_stats"]
        exported_file_paths = self._state["exported_file_paths"]

        message_lines = [
            f"Created asset from: {source_name}",
            (
                "Cleanup: "
                f"removed texture nodes {cleanup_stats['removed_nodes']}, "
                f"unused images {cleanup_stats['removed_images']}, "
                f"unused materials {cleanup_stats['removed_materials']}"
            ),
        ]

        if exported_file_paths:
            message_lines.append("Exported files:")
            for export_path in exported_file_paths[:8]:
                message_lines.append(f"• {export_path}")
            if len(exported_file_paths) > 8:
                message_lines.append(f"• ... and {len(exported_file_paths) - 8} more")
        else:
            message_lines.append("No files were exported.")

        return "\n".join(message_lines)

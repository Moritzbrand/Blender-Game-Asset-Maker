# Purpose: workflow services module.
# Example: import workflow_services
import math

import bpy

from ..scripts.baking_utils import BakingUtils
from ..scripts.cycles_utils import CyclesUtils
from ..scripts.export_utils import ExportUtils
from ..scripts.image_utils import ImageUtils
from ..scripts.material_utils import MaterialUtils
from ..scripts.mesh_utils import MeshUtils
from ..scripts.object_utils import ObjectUtils
from ..scripts.uv_utils import UVUtils
from .models import WorkflowState


class WorkflowContextStore:
    def __init__(self, state: WorkflowState):
        self.state = state

    def get_object(self, object_name: str):
        if not object_name:
            return None
        return bpy.data.objects.get(object_name)

    def get_image(self, image_name: str):
        if not image_name:
            return None
        return bpy.data.images.get(image_name)

    def get_created_image(self, image_key: str):
        return self.get_image(self.state.created_image_names.get(image_key, ""))

    def get_created_image_filepath(self, image_key: str):
        return self.state.created_image_filepaths.get(image_key, "")

    def selected_objects(self):
        return [
            obj
            for obj in (self.get_object(name) for name in self.state.selected_object_names)
            if obj is not None
        ]


class SelectionCoordinator:
    @staticmethod
    def select_single(context, obj):
        for selected_object in list(context.selected_objects):
            selected_object.select_set(False)

        if obj is not None:
            obj.select_set(True)
            context.view_layer.objects.active = obj


class GameAssetWorkflowServices:
    def __init__(self, state: WorkflowState):
        self.state = state
        self.store = WorkflowContextStore(state)

    def _use_selected_to_active_mode(self, context):
        return bool(context.scene.gameready_bake_selected_to_active)

    def _active_source_object(self):
        return self.store.get_object(self.state.active_object_name)

    def _source_objects_for_temp_join(self):
        active_object = self._active_source_object()
        return [
            obj
            for obj in self.store.selected_objects()
            if obj is not None and obj != active_object
        ]

    def _objects_for_game_asset_build(self, context):
        if self._use_selected_to_active_mode(context):
            active_object = self._active_source_object()
            return [active_object] if active_object is not None else []
        return self.store.selected_objects()

    def store_created_images(self, created_images):
        self.state.created_image_names = {
            image_key: image.name
            for image_key, image in created_images.items()
            if image is not None
        }
        self.state.created_image_filepaths = {
            image_key: str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", ""))
            for image_key, image in created_images.items()
            if image is not None
        }

    def prepare_temporary_source(self, context):
        scene = context.scene
        source_objects = (
            self._source_objects_for_temp_join()
            if self._use_selected_to_active_mode(context)
            else self.store.selected_objects()
        )
        ObjectUtils.select_objects(context, source_objects)
        temporary_objects = ObjectUtils.duplicate_selected(context)
        self.state.temporary_texture_anchor_names = MaterialUtils.prepare_texture_coordinate_anchors_for_objects(temporary_objects)

        if scene.gameready_apply_rot_scale:
            ObjectUtils.apply_transform_to_selected(context)

        MeshUtils.apply_modifiers_to_selected(context)
        temporary_object = MeshUtils.join_objects(context, temporary_objects)
        if temporary_object is None:
            self.state.temporary_object_name = ""
            return
        temporary_object.name = f"{self.state.source_object_name}_temp"
        self.state.temporary_object_name = temporary_object.name

    def build_game_asset_mesh(self, context):
        scene = context.scene
        ObjectUtils.select_objects(context, self._objects_for_game_asset_build(context))
        new_objects = ObjectUtils.duplicate_selected(context)

        if not self._use_selected_to_active_mode(context) and scene.gameready_unsubdivide:
            MeshUtils.add_unsubdivide_to_objects(new_objects, scene.gameready_unsubdivide_iterations * 2)

        if scene.gameready_apply_rot_scale:
            ObjectUtils.apply_transform_to_selected(context)

        MeshUtils.apply_modifiers_to_selected(context)
        if self._use_selected_to_active_mode(context):
            game_asset = MeshUtils.join_objects(context, new_objects)
        else:
            game_asset = MeshUtils.union(context, new_objects)
        if game_asset is None:
            raise ValueError("Could not create game asset mesh from current selection")

        game_asset.name = f"{self.state.source_object_name}_game"

        if not self._use_selected_to_active_mode(context) and scene.gameready_merge_by_distance:
            MeshUtils.merge_by_distance(context, game_asset, scene.gameready_merge_distance)
        if not self._use_selected_to_active_mode(context) and scene.gameready_collapse:
            MeshUtils.decimate_collapse(game_asset, scene.gameready_collapse_ratio)
        if not self._use_selected_to_active_mode(context) and scene.gameready_remove_planar_vertices:
            MeshUtils.decimate_planar(game_asset, scene.gameready_planar_angle_limit)
        if scene.gameready_triangulate:
            MeshUtils.triangulate_object(game_asset)

        MeshUtils.remove_custom_normals(game_asset)
        self.state.game_asset_name = game_asset.name
        SelectionCoordinator.select_single(context, game_asset)

    def cleanup_temporary_texture_coordinate_anchors(self, context):
        MaterialUtils.remove_temporary_objects_by_name(self.state.temporary_texture_anchor_names)
        self.state.temporary_texture_anchor_names = []

    def apply_shading(self, context):
        scene = context.scene
        game_asset = self.store.get_object(self.state.game_asset_name)
        SelectionCoordinator.select_single(context, game_asset)

        if scene.gameready_shade_auto_smooth:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(scene.gameready_auto_smooth_angle))
            return
        bpy.ops.object.shade_flat()

    def uv_unwrap(self, context):
        UVUtils.unwrap_object(context, self.store.get_object(self.state.game_asset_name))

    def prepare_bake_setup(self, context):
        scene = context.scene
        game_asset = self.store.get_object(self.state.game_asset_name)
        CyclesUtils.configure_cycles(scene, samples=scene.gameready_sample_count)
        _, created_images = MaterialUtils.setup_bake_material(game_asset, scene)
        self.store_created_images(created_images)

    def prepare_bake_visibility(self, context):
        temporary_object = self.store.get_object(self.state.temporary_object_name)
        game_asset = self.store.get_object(self.state.game_asset_name)
        objects_to_hide = [
            obj
            for obj in BakingUtils.get_all_rendered_objects(context)
            if obj not in {temporary_object, game_asset}
        ]
        self.state.visibility_state = BakingUtils.store_render_visibility(objects_to_hide)
        BakingUtils.hide_from_render(objects_to_hide)

    def make_source_materials_single_user(self, context):
        source_object = self.store.get_object(self.state.temporary_object_name)
        if source_object is None:
            source_object = self.store.get_object(self.state.game_asset_name)
        MaterialUtils.make_materials_single_user(source_object)

    def ensure_source_materials_for_bake(self, context):
        source_object = self.store.get_object(self.state.temporary_object_name)
        if source_object is None:
            source_object = self.store.get_object(self.state.game_asset_name)

        if source_object is None:
            self.state.temporary_source_materials = []
            return

        self.state.temporary_source_materials = MaterialUtils.ensure_standard_material_on_empty_slots(source_object)

    def restore_source_materials_after_bake(self, context):
        source_object = self.store.get_object(self.state.temporary_object_name)
        if source_object is None:
            source_object = self.store.get_object(self.state.game_asset_name)

        MaterialUtils.remove_temporary_material_assignments(source_object, self.state.temporary_source_materials)
        self.state.temporary_source_materials = []

    def resolve_bake_extrusion(self, context):
        scene = context.scene
        default_extrusion = float(scene.gameready_cage_extrusion)

        if not scene.gameready_auto_cage_extrusion:
            self.state.resolved_cage_extrusion = default_extrusion
            return

        source_object = self.store.get_object(self.state.temporary_object_name) or self.store.get_object(self.state.game_asset_name)
        target_object = self.store.get_object(self.state.game_asset_name)

        self.state.resolved_cage_extrusion = BakingUtils.calculate_auto_cage_extrusion(
            context=context,
            source_object=source_object,
            target_object=target_object,
            fallback_extrusion=default_extrusion,
            maximum_extrusion=1.0,
        )

    def _resolved_cage_extrusion(self, context):
        if self.state.resolved_cage_extrusion > 0.0:
            return self.state.resolved_cage_extrusion
        return float(context.scene.gameready_cage_extrusion)

    def bake_normal(self, context):
        scene = context.scene
        temporary_object = self.store.get_object(self.state.temporary_object_name)
        game_asset = self.store.get_object(self.state.game_asset_name)
        normal_image = self.store.get_created_image("normal")
        BakingUtils.bake_normal_selected_to_active(
            context=context,
            source_obj=temporary_object or game_asset,
            target_obj=game_asset,
            target_image=normal_image,
            extrusion=self._resolved_cage_extrusion(context),
            margin=self.state.bake_margin,
        )
        if scene.gameready_flip_y_normal:
            ImageUtils.flip_normal_map_y(normal_image, scene=scene)

    def bake_ao(self, context):
        self._bake_selected_to_active(context, "ao", bake_mode="AO")

    def bake_emit_channel(self, context, image_key: str, material_channel: str):
        temporary_object = self.store.get_object(self.state.temporary_object_name)
        source_object = temporary_object or self.store.get_object(self.state.game_asset_name)
        BakingUtils.prepare_object_materials_for_emit_bake(source_object, material_channel)
        self._bake_selected_to_active(context, image_key, bake_mode="EMIT")

    def _bake_selected_to_active(self, context, image_key: str, bake_mode: str):
        bake_call = (
            BakingUtils.bake_emit_selected_to_active
            if bake_mode == "EMIT"
            else BakingUtils.bake_ao_selected_to_active
        )
        bake_call(
            context=context,
            source_obj=self.store.get_object(self.state.temporary_object_name) or self.store.get_object(self.state.game_asset_name),
            target_obj=self.store.get_object(self.state.game_asset_name),
            target_image=self.store.get_created_image(image_key),
            extrusion=self._resolved_cage_extrusion(context),
            margin=self.state.bake_margin,
        )

    def combine_base_color_and_alpha(self, context):
        scene = context.scene
        alpha_image = self.store.get_created_image("base_color_alpha_tmp")
        final_image = self.store.get_created_image("base_color")
        ImageUtils.combine_rgb_and_alpha_images(
            self.store.get_created_image("base_color_rgb_tmp"),
            alpha_image,
            final_image,
            scene=scene,
        )

    def pack_orm(self, context):
        ImageUtils.combine_orm_images(
            self.store.get_created_image("ao"),
            self.store.get_created_image("roughness"),
            self.store.get_created_image("metallic"),
            self.store.get_created_image("orm"),
            scene=context.scene,
        )

    def restore_visibility(self, context):
        BakingUtils.restore_render_visibility(self.state.visibility_state)
        self.state.visibility_state = {}

    def cleanup_materials(self, context):
        game_asset = self.store.get_object(self.state.game_asset_name)
        self.state.cleanup_stats = MaterialUtils.cleanup_unused_textures_and_materials(game_asset)

    def export_files(self, context):
        scene = context.scene
        lod_count = scene.gameready_lod_count if scene.gameready_generate_lods else 0
        self.state.exported_file_paths = ExportUtils.export_object_and_lods(
            context=context,
            obj=self.store.get_object(self.state.game_asset_name),
            output_dir=scene.gameready_output_dir,
            lod_count=lod_count,
            export_format_identifier=scene.gameready_export_format,
            preset_identifier=scene.gameready_export_preset,
            material_export_strategy_identifier=scene.gameready_material_export_strategy,
        )

    def restore_blender_normal_preview(self, context):
        game_asset = self.store.get_object(self.state.game_asset_name)
        if game_asset is not None:
            MaterialUtils.apply_normal_y_display_fix_to_object(game_asset)
            MaterialUtils.refresh_material_preview_on_object(game_asset, context=context)

    def restore_blender_sss_preview(self, context):
        game_asset = self.store.get_object(self.state.game_asset_name)
        if game_asset is None:
            return
        MaterialUtils.apply_sss_preview_to_object(
            obj=game_asset,
            image=self.store.get_created_image("sss"),
            image_filepath=self.store.get_created_image_filepath("sss"),
        )
        MaterialUtils.refresh_material_preview_on_object(game_asset, context=context)

    def finalize_scene(self, context):
        self.restore_source_materials_after_bake(context)
        self.cleanup_temporary_texture_coordinate_anchors(context)
        game_asset = self.store.get_object(self.state.game_asset_name)
        temporary_object = self.store.get_object(self.state.temporary_object_name)
        SelectionCoordinator.select_single(context, game_asset)
        if game_asset is not None:
            MaterialUtils.refresh_material_preview_on_object(game_asset, context=context)
        if temporary_object is not None:
            bpy.data.objects.remove(temporary_object, do_unlink=True)
            self.state.temporary_object_name = ""

    def safe_cleanup(self, context):
        try:
            self.restore_source_materials_after_bake(context)
        except Exception:
            pass
        try:
            BakingUtils.restore_render_visibility(self.state.visibility_state)
        except Exception:
            pass
        self.state.visibility_state = {}
        try:
            self.cleanup_temporary_texture_coordinate_anchors(context)
        except Exception:
            pass
        temporary_object = self.store.get_object(self.state.temporary_object_name)
        if temporary_object is None:
            return
        try:
            bpy.data.objects.remove(temporary_object, do_unlink=True)
        except Exception:
            pass
        self.state.temporary_object_name = ""

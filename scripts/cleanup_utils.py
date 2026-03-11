import bpy

from .baking_utils import BakingUtils
from .material_utils import MaterialUtils
from .progress_utils import ProgressUtils


class CleanupUtils:
    @staticmethod
    def _get_object(object_name):
        if not object_name:
            return None
        return bpy.data.objects.get(object_name)

    @staticmethod
    def _select_single_object(context, obj):
        for selected_object in list(context.selected_objects):
            selected_object.select_set(False)

        if obj is not None:
            obj.select_set(True)
            context.view_layer.objects.active = obj

    @staticmethod
    def release_preview(context):
        ProgressUtils.clear_preview(context)

    @staticmethod
    def restore_visibility(state):
        visibility_state = state.get("visibility_state", {})
        if visibility_state:
            BakingUtils.restore_render_visibility(visibility_state)
        state["visibility_state"] = {}

    @staticmethod
    def remove_temporary_object(state):
        temporary_obj = CleanupUtils._get_object(state.get("temporary_obj_name", ""))
        if temporary_obj is not None:
            bpy.data.objects.remove(temporary_obj, do_unlink=True)
        state["temporary_obj_name"] = ""

    @staticmethod
    def cleanup_materials(context, state):
        CleanupUtils.release_preview(context)

        game_asset = CleanupUtils._get_object(state.get("game_asset_name", ""))
        state["cleanup_stats"] = MaterialUtils.cleanup_unused_textures_and_materials(game_asset)
        return state["cleanup_stats"]

    @staticmethod
    def finalize_scene(context, state):
        game_asset = CleanupUtils._get_object(state.get("game_asset_name", ""))
        CleanupUtils._select_single_object(context, game_asset)
        CleanupUtils.remove_temporary_object(state)

    @staticmethod
    def safe_cleanup(context, state):
        try:
            CleanupUtils.release_preview(context)
        except Exception:
            pass

        try:
            CleanupUtils.restore_visibility(state)
        except Exception:
            state["visibility_state"] = {}

        try:
            CleanupUtils.remove_temporary_object(state)
        except Exception:
            state["temporary_obj_name"] = ""

    @staticmethod
    def build_result_message(state):
        source_name = state.get("source_object_name", "Unknown")
        cleanup_stats = state.get("cleanup_stats", {})
        exported_file_paths = state.get("exported_file_paths", [])

        removed_nodes = cleanup_stats.get("removed_nodes", 0)
        removed_images = cleanup_stats.get("removed_images", 0)
        removed_materials = cleanup_stats.get("removed_materials", 0)

        message_lines = [
            f"Created asset from: {source_name}",
            (
                "Cleanup: "
                f"removed texture nodes {removed_nodes}, "
                f"unused images {removed_images}, "
                f"unused materials {removed_materials}"
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
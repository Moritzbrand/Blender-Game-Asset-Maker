# Purpose: create game asset operator module.
# Example: import create_game_asset_operator
import bpy

from ..scripts.progress_utils import ProgressUtils
from .models import WorkflowState
from .workflow_services import GameAssetWorkflowServices
from .workflow_step_factory import WorkflowStepFactory


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
    _services = None

    @classmethod
    def poll(cls, context):
        if getattr(context.window_manager, "gameready_progress_running", False):
            return False
        return (
            context.active_object is not None
            and context.mode == 'OBJECT'
            and context.active_object.type == 'MESH'
            and all(obj.type == 'MESH' for obj in context.selected_objects)
        )

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        scene = context.scene
        active_object = context.active_object
        self._state = WorkflowState(
            source_object_name=active_object.name,
            selected_object_names=[obj.name for obj in context.selected_objects],
            active_object_name=active_object.name,
            bake_margin=max(1, int(scene.gameready_texture_size) // 8),
        )
        self._services = GameAssetWorkflowServices(self._state)

        self._steps = WorkflowStepFactory(self._services).build(context)
        self._completed_weight = 0.0
        self._total_weight = sum(step.weight for step in self._steps) or 1.0

        ProgressUtils.reset(context.window_manager)
        ProgressUtils.begin(context, title="Preparing Game Asset", detail="The job has started.", factor=0.0)

        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self._services.safe_cleanup(context)
            self._finish_modal(context)
            ProgressUtils.cancel(context, title="Cancelled", detail="Game asset creation was cancelled.")
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}

        if not self._steps:
            self._services.safe_cleanup(context)
            result_message = self._build_result_message()
            self._finish_modal(context)
            ProgressUtils.finish(context, title="Finished", detail="The asset is ready.")
            bpy.ops.gameready.result_dialog('INVOKE_DEFAULT', message=result_message)
            return {'FINISHED'}

        current_step = self._steps.pop(0)
        self._announce_step(context, current_step)

        try:
            current_step.function(context)
        except Exception as exception:
            self._services.safe_cleanup(context)
            self._finish_modal(context)
            ProgressUtils.cancel(context, title="Failed", detail=f"{current_step.title} failed: {exception}")
            self.report({'ERROR'}, f"{current_step.title} failed: {exception}")
            return {'CANCELLED'}

        self._completed_weight += current_step.weight
        ProgressUtils.update(
            context,
            factor=self._completed_weight / self._total_weight,
            title=current_step.title,
            detail=current_step.completed_detail,
        )
        ProgressUtils.flush_ui()
        return {'RUNNING_MODAL'}

    def _announce_step(self, context, step):
        ProgressUtils.update(
            context,
            factor=self._completed_weight / self._total_weight,
            title=step.title,
            detail=step.detail,
        )
        ProgressUtils.flush_ui()

    def _finish_modal(self, context):
        if self._timer is None:
            return
        try:
            context.window_manager.event_timer_remove(self._timer)
        except Exception:
            pass
        self._timer = None

    def _build_result_message(self):
        cleanup = self._state.cleanup_stats
        lines = [
            f"Created asset from: {self._state.source_object_name}",
            (
                "Cleanup: "
                f"removed texture nodes {cleanup['removed_nodes']}, "
                f"unused images {cleanup['removed_images']}, "
                f"unused materials {cleanup['removed_materials']}"
            ),
        ]

        if not self._state.exported_file_paths:
            lines.append("No files were exported.")
            return "\n".join(lines)

        lines.append("Exported files:")
        for export_path in self._state.exported_file_paths[:8]:
            lines.append(f"• {export_path}")
        if len(self._state.exported_file_paths) > 8:
            lines.append(f"• ... and {len(self._state.exported_file_paths) - 8} more")
        return "\n".join(lines)

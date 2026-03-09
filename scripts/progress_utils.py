import bpy


class GameReadyProgressUtils:
    @classmethod
    def reset_runtime_state(cls, scene):
        scene.gameready_job_running = False
        scene.gameready_job_progress = 0.0
        scene.gameready_job_current_step_label = ""
        scene.gameready_job_status_text = ""
        scene.gameready_job_result_text = ""
        scene.gameready_job_preview_image = None

    @classmethod
    def begin_job(cls, scene):
        cls.reset_runtime_state(scene)
        scene.gameready_job_running = True
        scene.gameready_job_status_text = "Preparing job"

    @classmethod
    def show_pending_step(cls, scene, step_label, step_index, total_step_count):
        scene.gameready_job_current_step_label = step_label
        scene.gameready_job_status_text = f"Step {step_index + 1} of {total_step_count}"

    @classmethod
    def mark_step_finished(
        cls,
        scene,
        completed_step_count,
        total_step_count,
        preview_image=None,
    ):
        if total_step_count <= 0:
            scene.gameready_job_progress = 100.0
        else:
            scene.gameready_job_progress = (completed_step_count / total_step_count) * 100.0

        scene.gameready_job_status_text = (
            f"Completed {completed_step_count} of {total_step_count} steps"
        )

        if preview_image is not None:
            scene.gameready_job_preview_image = preview_image

    @classmethod
    def finish_job(cls, scene, result_text):
        scene.gameready_job_running = False
        scene.gameready_job_progress = 100.0
        scene.gameready_job_current_step_label = "Finished"
        scene.gameready_job_status_text = "Game asset creation completed"
        scene.gameready_job_result_text = result_text

    @classmethod
    def fail_job(cls, scene, error_text):
        scene.gameready_job_running = False
        scene.gameready_job_current_step_label = "Failed"
        scene.gameready_job_status_text = error_text
        scene.gameready_job_result_text = error_text

    @classmethod
    def tag_redraw_all_areas(cls, context):
        window_manager = context.window_manager
        for window in window_manager.windows:
            screen = window.screen
            if screen is None:
                continue

            for area in screen.areas:
                area.tag_redraw()

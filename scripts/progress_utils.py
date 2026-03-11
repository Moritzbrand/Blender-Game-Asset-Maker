import bpy


class ProgressUtils:
    @staticmethod
    def register():
        bpy.types.WindowManager.gameready_progress_running = bpy.props.BoolProperty(
            default=False,
            options={'SKIP_SAVE'},
        )
        bpy.types.WindowManager.gameready_progress_factor = bpy.props.FloatProperty(
            default=0.0,
            min=0.0,
            max=1.0,
            options={'SKIP_SAVE'},
        )
        bpy.types.WindowManager.gameready_progress_title = bpy.props.StringProperty(
            default="",
            options={'SKIP_SAVE'},
        )
        bpy.types.WindowManager.gameready_progress_detail = bpy.props.StringProperty(
            default="",
            options={'SKIP_SAVE'},
        )
        bpy.types.WindowManager.gameready_progress_is_baking = bpy.props.BoolProperty(
            default=False,
            options={'SKIP_SAVE'},
        )

    @staticmethod
    def unregister():
        for attribute_name in (
            'gameready_progress_is_baking',
            'gameready_progress_detail',
            'gameready_progress_title',
            'gameready_progress_factor',
            'gameready_progress_running',
        ):
            if hasattr(bpy.types.WindowManager, attribute_name):
                delattr(bpy.types.WindowManager, attribute_name)

    @staticmethod
    def reset(window_manager):
        window_manager.gameready_progress_running = False
        window_manager.gameready_progress_factor = 0.0
        window_manager.gameready_progress_title = ""
        window_manager.gameready_progress_detail = ""
        window_manager.gameready_progress_is_baking = False

    @staticmethod
    def _detect_bake_phase(title, detail):
        combined_text = f"{title or ''} {detail or ''}".lower()
        return "baking" in combined_text or "bake" in combined_text

    @staticmethod
    def begin(context, title, detail="", factor=0.0):
        window_manager = context.window_manager
        window_manager.gameready_progress_running = True
        window_manager.gameready_progress_factor = max(0.0, min(1.0, float(factor)))
        window_manager.gameready_progress_title = title
        window_manager.gameready_progress_detail = detail
        window_manager.gameready_progress_is_baking = ProgressUtils._detect_bake_phase(title, detail)

        try:
            window_manager.progress_begin(0.0, 1.0)
            window_manager.progress_update(window_manager.gameready_progress_factor)
        except Exception:
            pass

        ProgressUtils.tag_redraw_all()

    @staticmethod
    def update(context, factor=None, title=None, detail=None):
        window_manager = context.window_manager

        if factor is not None:
            window_manager.gameready_progress_factor = max(0.0, min(1.0, float(factor)))
        if title is not None:
            window_manager.gameready_progress_title = title
        if detail is not None:
            window_manager.gameready_progress_detail = detail

        window_manager.gameready_progress_is_baking = ProgressUtils._detect_bake_phase(
            window_manager.gameready_progress_title,
            window_manager.gameready_progress_detail,
        )

        try:
            window_manager.progress_update(window_manager.gameready_progress_factor)
        except Exception:
            pass

        ProgressUtils.tag_redraw_all()

    @staticmethod
    def finish(context, title="Finished", detail=""):
        window_manager = context.window_manager

        window_manager.gameready_progress_factor = 1.0
        window_manager.gameready_progress_title = title
        window_manager.gameready_progress_detail = detail
        window_manager.gameready_progress_running = False
        window_manager.gameready_progress_is_baking = False

        try:
            window_manager.progress_update(1.0)
        except Exception:
            pass

        try:
            window_manager.progress_end()
        except Exception:
            pass

        ProgressUtils.tag_redraw_all()

    @staticmethod
    def cancel(context, title="Cancelled", detail=""):
        window_manager = context.window_manager

        window_manager.gameready_progress_title = title
        window_manager.gameready_progress_detail = detail
        window_manager.gameready_progress_running = False
        window_manager.gameready_progress_is_baking = False

        try:
            window_manager.progress_end()
        except Exception:
            pass

        ProgressUtils.tag_redraw_all()

    @staticmethod
    def flush_ui():
        ProgressUtils.tag_redraw_all()

    @staticmethod
    def tag_redraw_all():
        for window_manager in bpy.data.window_managers:
            for window in window_manager.windows:
                screen = window.screen
                if screen is None:
                    continue
                for area in screen.areas:
                    area.tag_redraw()

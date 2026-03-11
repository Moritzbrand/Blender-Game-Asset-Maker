bl_info = {
    "name": "Game Asset Maker",
    "author": "Moritz Brand",
    "version": (1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar",
    "description": "Create game-ready assets from high-poly meshes",
    "category": "Object",
}

import bpy

from .operators import GAMEREADY_OT_create_game_asset, GAMEREADY_OT_result_dialog
from .panel import (
    GAMEREADY_PT_common_settings_panel,
    GAMEREADY_PT_main_panel,
    GAMEREADY_PT_settings_panel,
)
from .scripts.progress_utils import ProgressUtils
from . import properties


classes = (
    GAMEREADY_OT_result_dialog,
    GAMEREADY_OT_create_game_asset,
    GAMEREADY_PT_main_panel,
    GAMEREADY_PT_common_settings_panel,
    GAMEREADY_PT_settings_panel,
)


def register():
    properties.register()
    ProgressUtils.register()

    for cls in classes:
        bpy.utils.register_class(cls)

    print("Game Asset Maker enabled")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    ProgressUtils.unregister()
    properties.unregister()
    print("Game Asset Maker disabled")


if __name__ == "__main__":
    register()

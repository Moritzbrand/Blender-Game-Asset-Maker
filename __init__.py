bl_info = {
    "name": "Game Ready Addon",
    "author": "Moritz Brand",
    "version": (0, 1),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar",
    "description": "Make a model game ready",
    "category": "Object",
}

import bpy

from .operators import GAMEREADY_OT_create_game_asset
from .panel import GAMEREADY_PT_main_panel, GAMEREADY_PT_settings_panel
from . import properties


classes = (
    GAMEREADY_OT_create_game_asset,
    GAMEREADY_PT_main_panel,
    GAMEREADY_PT_settings_panel,
)


def register():
    properties.register()
    for cls in classes:
        bpy.utils.register_class(cls)
    print("Game Ready Addon enabled")


def unregister():
    properties.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("Game Ready Addon disabled")


if __name__ == "__main__":
    register()

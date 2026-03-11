from .scene_properties import SCENE_PROPERTIES


def register():
    for scene_property in SCENE_PROPERTIES:
        scene_property.register()


def unregister():
    for scene_property in reversed(SCENE_PROPERTIES):
        scene_property.unregister()

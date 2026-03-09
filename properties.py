import bpy

from .scripts.export_utils import (
    ExportPresetCatalog,
    ExportStrategyRegistry,
    MaterialExportStrategyRegistry,
)


_EXPORT_FORMAT_ENUM_CACHE = []
_EXPORT_PRESET_ENUM_CACHE = []


def get_export_format_enum_items(self, context):
    global _EXPORT_FORMAT_ENUM_CACHE
    _EXPORT_FORMAT_ENUM_CACHE = ExportStrategyRegistry.build_format_enum_items()
    return _EXPORT_FORMAT_ENUM_CACHE


def get_export_preset_enum_items(self, context):
    global _EXPORT_PRESET_ENUM_CACHE

    export_format_identifier = "FBX"
    if context is not None and context.scene is not None:
        export_format_identifier = getattr(context.scene, "gameready_export_format", "FBX")

    _EXPORT_PRESET_ENUM_CACHE = ExportPresetCatalog.build_preset_enum_items(
        export_format_identifier
    )
    return _EXPORT_PRESET_ENUM_CACHE


def on_export_format_changed(self, context):
    preset_items = get_export_preset_enum_items(self, context)
    valid_preset_identifiers = {item[0] for item in preset_items}

    current_preset_identifier = getattr(self, "gameready_export_preset", "")
    if current_preset_identifier in valid_preset_identifiers:
        return

    if preset_items:
        self.gameready_export_preset = preset_items[0][0]


class Property:
    def __init__(self, attr_name: str, name: str, description: str, options=None):
        self.attr_name = attr_name
        self.name = name
        self.description = description
        self.options = options or set()

    def register(self):
        raise NotImplementedError("Subclasses must implement register()")

    def unregister(self):
        if hasattr(bpy.types.Scene, self.attr_name):
            delattr(bpy.types.Scene, self.attr_name)


class BoolProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default=False, options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.BoolProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                options=self.options,
            ),
        )


class EnumProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, items, default=None, update=None, options=None):
        super().__init__(attr_name, name, description, options=options)
        self.items = items
        self.default = default
        self.update = update

    def register(self):
        enum_kwargs = {
            "name": self.name,
            "description": self.description,
            "items": self.items,
            "options": self.options,
        }

        if self.default is not None and not callable(self.items):
            enum_kwargs["default"] = self.default

        if self.update is not None:
            enum_kwargs["update"] = self.update

        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.EnumProperty(**enum_kwargs),
        )


class IntProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default=0, min=0, max=100, options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default
        self.min = min
        self.max = max

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.IntProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                min=self.min,
                max=self.max,
                options=self.options,
            ),
        )


class FloatProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default=0.0, min=0.0, max=1.0, subtype='NONE', options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default
        self.min = min
        self.max = max
        self.subtype = subtype

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.FloatProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                min=self.min,
                max=self.max,
                subtype=self.subtype,
                options=self.options,
            ),
        )


class PathStringProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default="", subtype='NONE', options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default
        self.subtype = subtype

    def register(self):
        property_options = set(self.options)
        property_options.add('PATH_SUPPORTS_BLEND_RELATIVE')
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.StringProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                subtype=self.subtype,
                options=property_options,
            ),
        )


class StringProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default="", options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.StringProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                options=self.options,
            ),
        )


class PointerProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, pointer_type, options=None):
        super().__init__(attr_name, name, description, options=options)
        self.pointer_type = pointer_type

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.PointerProperty(
                name=self.name,
                description=self.description,
                type=self.pointer_type,
                options=self.options,
            ),
        )


PROPERTIES = [
    PathStringProperty(
        "gameready_output_dir",
        "Output Folder",
        "Folder where baked textures and exports will be written",
        default="//game_assets/",
        subtype='DIR_PATH',
    ),
    BoolProperty(
        "gameready_export_files",
        "Export",
        "Export the new game asset after processing",
        True,
    ),
    EnumProperty(
        "gameready_export_format",
        "Export Format",
        "Choose which file format the generated asset should use",
        items=get_export_format_enum_items,
        update=on_export_format_changed,
    ),
    EnumProperty(
        "gameready_export_preset",
        "Export Preset",
        "Choose a Blender user preset or an addon preset for the selected export format",
        items=get_export_preset_enum_items,
    ),
    EnumProperty(
        "gameready_material_export_strategy",
        "Material Export",
        "Choose whether materials should be stripped or kept during export",
        items=MaterialExportStrategyRegistry.build_enum_items(),
        default="STRIP_MATERIALS",
    ),
    BoolProperty(
        "gameready_uv_unwrap",
        "UV Unwrap",
        "Automatically create UVs for the new game asset using Smart UV Project",
        True,
    ),
    BoolProperty(
        "gameready_apply_rot_scale",
        "Apply Rotation & Scale",
        "Apply rotation and scale before creating the game asset",
        True,
    ),
    BoolProperty(
        "gameready_merge_by_distance",
        "Merge by Distance",
        "Remove duplicate vertices within a certain distance to optimize the mesh for game engines",
        True,
    ),
    FloatProperty(
        "gameready_merge_distance",
        "Merge Distance",
        "Distance threshold for merging vertices when 'Merge by Distance' is enabled",
        default=0.0001,
        min=0.0,
        max=0.1,
    ),
    BoolProperty(
        "gameready_unsubdivide",
        "Unsubdivide",
        "Unsubdivide the mesh of the new game asset",
        False,
    ),
    IntProperty(
        "gameready_unsubdivide_iterations",
        "Unsubdivide Iterations",
        "Number of iterations to perform when unsubdividing the mesh",
        default=1,
        min=1,
        max=4,
    ),
    BoolProperty(
        "gameready_collapse",
        "Collapse",
        "Collapse the mesh of the new game asset",
        True,
    ),
    FloatProperty(
        "gameready_collapse_ratio",
        "Collapse Ratio",
        "Ratio of vertices to collapse when collapsing the mesh",
        default=0.9,
        min=0.0,
        max=1.0,
    ),
    BoolProperty(
        "gameready_remove_planar_vertices",
        "Remove Planar Vertices",
        "Remove vertices that are part of planar faces to optimize the mesh",
        True,
    ),
    IntProperty(
        "gameready_planar_angle_limit",
        "Planar Angle Limit",
        "Maximum angle between faces to consider them planar",
        default=5,
        min=0,
        max=30,
    ),
    BoolProperty(
        "gameready_triangulate",
        "Triangulate",
        "Triangulate the mesh of the new game asset",
        True,
    ),
    BoolProperty(
        "gameready_bake_textures",
        "Bake Textures",
        "Bake textures from the original object's materials to the new game asset",
        True,
    ),
    EnumProperty(
        "gameready_texture_size",
        "Texture Size",
        "Resolution of the baked texture",
        items=[
            ("256", "256", "256 x 256"),
            ("512", "512", "512 x 512"),
            ("1024", "1024", "1024 x 1024"),
            ("2048", "2048", "2048 x 2048"),
            ("4096", "4096", "4096 x 4096"),
        ],
        default="1024",
    ),
    BoolProperty(
        "gameready_generate_lods",
        "Generate LODs",
        "Automatically generate Level of Detail models",
        False,
    ),
    IntProperty(
        "gameready_lod_count",
        "LOD Count",
        "Number of LOD levels to generate",
        default=3,
        min=1,
        max=10,
    ),
    BoolProperty(
        "gameready_bake_base_color",
        "Base Color",
        "Bake base color from the original object's materials to the new game asset",
        True,
    ),
    BoolProperty(
        "gameready_bake_alpha",
        "Alpha",
        "Add an alpha channel to the baked base color texture if needed",
        False,
    ),
    BoolProperty(
        "gameready_bake_emission",
        "Emission",
        "Bake emission from the original object's materials to the new game asset",
        False,
    ),
    BoolProperty(
        "gameready_bake_normal",
        "Normal Map",
        "Bake normal map from the original object's materials to the new game asset",
        True,
    ),
    BoolProperty(
        "gameready_flip_y_normal",
        "Flip Y Normal",
        "Flip the Y channel of the baked normal map",
        True,
    ),
    BoolProperty(
        "gameready_bake_ao",
        "Ambient Occlusion",
        "Bake ambient occlusion from the original object's materials to the new game asset",
        True,
    ),
    BoolProperty(
        "gameready_bake_roughness",
        "Roughness",
        "Bake roughness from the original object's materials to the new game asset",
        True,
    ),
    BoolProperty(
        "gameready_bake_metallic",
        "Metallic",
        "Bake metallic from the original object's materials to the new game asset",
        True,
    ),
    BoolProperty(
        "gameready_pack_as_orm",
        "Pack as ORM",
        "Pack roughness, metallic, and ambient occlusion into a single texture",
        True,
    ),
    IntProperty(
        "gameready_sample_count",
        "Sample Count",
        "Number of samples to use when baking textures",
        default=512,
        min=8,
        max=1024,
    ),
    FloatProperty(
        "gameready_cage_extrusion",
        "Cage Extrusion",
        "Amount of extrusion to apply to the cage when baking",
        default=0.07,
        min=0.0,
        max=1.0,
    ),
    BoolProperty(
        "gameready_shade_auto_smooth",
        "Auto Smooth Shading",
        "Enable auto smooth shading on the new game asset",
        True,
    ),
    IntProperty(
        "gameready_auto_smooth_angle",
        "Auto Smooth Angle",
        "Angle for auto smooth shading",
        default=60,
        min=0,
        max=180,
    ),
    BoolProperty(
        "gameready_job_running",
        "Job Running",
        "True while the game asset build job is running",
        default=False,
        options={'SKIP_SAVE'},
    ),
    FloatProperty(
        "gameready_job_progress",
        "Job Progress",
        "Progress of the running game asset build job",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
        options={'SKIP_SAVE'},
    ),
    StringProperty(
        "gameready_job_current_step_label",
        "Current Step",
        "Current game asset build step",
        default="",
        options={'SKIP_SAVE'},
    ),
    StringProperty(
        "gameready_job_status_text",
        "Job Status",
        "Additional job status text",
        default="",
        options={'SKIP_SAVE'},
    ),
    StringProperty(
        "gameready_job_result_text",
        "Job Result",
        "Final result text of the last build job",
        default="",
        options={'SKIP_SAVE'},
    ),
    PointerProperty(
        "gameready_job_preview_image",
        "Preview Image",
        "Last baked texture preview image",
        pointer_type=bpy.types.Image,
        options={'SKIP_SAVE'},
    ),
]


def register():
    for prop in PROPERTIES:
        prop.register()


def unregister():
    for prop in reversed(PROPERTIES):
        prop.unregister()

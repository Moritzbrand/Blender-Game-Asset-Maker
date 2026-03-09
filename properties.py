# properties.py

import bpy


class Property:
    def __init__(self, attr_name: str, name: str, description: str):
        self.attr_name = attr_name
        self.name = name
        self.description = description

    def register(self):
        raise NotImplementedError("Subclasses must implement register()")

    def unregister(self):
        if hasattr(bpy.types.Scene, self.attr_name):
            delattr(bpy.types.Scene, self.attr_name)


class BoolProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default=False):
        super().__init__(attr_name, name, description)
        self.default = default

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.BoolProperty(
                name=self.name,
                description=self.description,
                default=self.default,
            ),
        )


class EnumProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, items, default=None):
        super().__init__(attr_name, name, description)
        self.items = items
        self.default = default

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.EnumProperty(
                name=self.name,
                description=self.description,
                items=self.items,
                default=self.default,
            ),
        )


class IntProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default=0, min=0, max=100):
        super().__init__(attr_name, name, description)
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
            ),
        )

class FloatProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default=0.0, min=0.0, max=1.0):
        super().__init__(attr_name, name, description)
        self.default = default
        self.min = min
        self.max = max

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
            ),
        )

class PathStringProperty(Property):
    def __init__(self, attr_name: str, name: str, description: str, default="", subtype='NONE'):
        super().__init__(attr_name, name, description)
        self.default = default
        self.subtype = subtype

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.StringProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                subtype=self.subtype,
                options={'PATH_SUPPORTS_BLEND_RELATIVE'},
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
        "gameready_export_fbx",
        "Export FBX",
        "Export the new game asset as an FBX file (this is a common format for game engines)",
        True,
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
        "Unsubdivide the mesh of the new game asset (this can help reduce the polygon count for game engines)",
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
        "Collapse the mesh of the new game asset (this can help reduce the polygon count for game engines)",
        True,
    ),
    FloatProperty(
        "gameready_collapse_ratio",
        "Collapse Ratio",
        "Ratio of vertices to collapse when collapsing the mesh (1.0 = no collapse, 0.0 = collapse all vertices)",
        default=0.9,    
        min=0.0,
        max=1.0,
    ),
    BoolProperty(
        "gameready_remove_planar_vertices",
        "Remove Planar Vertices",
        "Remove vertices that are part of planar faces to optimize the mesh for game engines (this can cause issues with certain types of geometry, so only enable if needed)",
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
        "Triangulate the mesh of the new game asset (some game engines require triangulated meshes)",
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
        "Add an alpha channel to the baked base color texture if any of the original materials have transparency (this will increase the file size of the baked texture, so only enable if needed)",
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
        "Flip the Y channel of the baked normal map (some game engines use a different normal map convention, so enable this if your normal maps look incorrect in your game engine)",
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
        "Pack roughness, metallic, and ambient occlusion into a single texture (ORM) for use in game engines that support it",
        True,
    ),

    IntProperty(
        "gameready_sample_count",
        "Sample Count",
        "Number of samples to use when baking textures (higher values produce better quality but take longer)",
        default=512,
        min=8,
        max=1024,
    ),

    FloatProperty(
        "gameready_cage_extrusion",
        "Cage Extrusion",
        "Amount of extrusion to apply to the cage when baking (higher values can help prevent baking artifacts but may cause distortion)",
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

]


def register():
    for prop in PROPERTIES:
        prop.register()


def unregister():
    for prop in reversed(PROPERTIES):
        prop.unregister()
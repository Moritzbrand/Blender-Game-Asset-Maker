# Purpose: scene properties module.
# Example: import scene_properties
from ..scripts.export_utils import MaterialExportStrategyRegistry
from .export_enums import (
    get_export_format_enum_items,
    get_export_preset_enum_items,
    on_export_format_changed,
)
from .property_types import (
    BoolSceneProperty,
    EnumSceneProperty,
    FloatSceneProperty,
    IntSceneProperty,
    PathSceneProperty,
    StringSceneProperty,
)


FAST_PREVIEW_SAMPLE_COUNT = 8
FAST_PREVIEW_TEXTURE_COMPRESSION = 0


def on_fast_low_quality_changed(scene, _context):
    if scene.gameready_fast_low_quality:
        scene.gameready_sample_count = FAST_PREVIEW_SAMPLE_COUNT
        scene.gameready_texture_compression = FAST_PREVIEW_TEXTURE_COMPRESSION

SCENE_PROPERTIES = [
    PathSceneProperty("gameready_output_dir", "Output Folder", "Folder where baked textures and exports will be written", default="//game_assets/", subtype='DIR_PATH'),
    BoolSceneProperty("gameready_export_files", "Export", "Export the new game asset after processing", True),
    EnumSceneProperty("gameready_export_format", "Export Format", "Choose which file format the generated asset should use", items=get_export_format_enum_items, update=on_export_format_changed),
    EnumSceneProperty("gameready_export_preset", "Export Preset", "Choose a Blender user preset or an addon preset for the selected export format", items=get_export_preset_enum_items),
    EnumSceneProperty("gameready_material_export_strategy", "Material Export", "Choose whether materials should be stripped or kept during export", items=MaterialExportStrategyRegistry.build_enum_items(), default="STRIP_MATERIALS"),
    BoolSceneProperty("gameready_uv_unwrap", "UV Unwrap", "Automatically create UVs for the new game asset", True),
    IntSceneProperty("gameready_uv_island_margin", "UV Island Margin", "Final UV island margin in pixels used when packing islands", default=1, min=0, max=16),
    BoolSceneProperty("gameready_bake_selected_to_active", "Bake Selected to Active", "Use non-active selected objects as bake source and the active object as the bake target", False),
    BoolSceneProperty("gameready_apply_rot_scale", "Apply Rotation & Scale", "Apply rotation and scale before creating the game asset", True),
    BoolSceneProperty("gameready_merge_by_distance", "Merge by Distance", "Remove duplicate vertices within a certain distance to optimize the mesh for game engines", True),
    FloatSceneProperty("gameready_merge_distance", "Merge Distance", "Distance threshold for merging vertices when 'Merge by Distance' is enabled", default=0.0001, min=0.0, max=0.1),
    BoolSceneProperty("gameready_average_triangle_density", "Average Out Triangle Density", "Decimate overly dense source-object copies before union so sparse areas keep more of their shape", False),
    FloatSceneProperty("gameready_max_triangle_density", "Max Triangle Density", "Maximum allowed triangle density in triangles per square Blender unit of bounding-box surface area before pre-union decimation kicks in", default=1000.0, min=0.1, max=100000.0),
    BoolSceneProperty("gameready_unsubdivide", "Unsubdivide", "Unsubdivide the mesh of the new game asset", False),
    IntSceneProperty("gameready_unsubdivide_iterations", "Unsubdivide Iterations", "Number of iterations to perform when unsubdividing the mesh", default=1, min=1, max=4),
    BoolSceneProperty("gameready_collapse", "Collapse", "Collapse the mesh of the new game asset", False),
    FloatSceneProperty("gameready_collapse_ratio", "Collapse Ratio", "Ratio of vertices to collapse when collapsing the mesh", default=0.9, min=0.0, max=1.0),
    BoolSceneProperty("gameready_remove_planar_vertices", "Remove Planar Vertices", "Remove vertices that are part of planar faces to optimize the mesh", True),
    IntSceneProperty("gameready_planar_angle_limit", "Planar Angle Limit", "Maximum angle between faces to consider them planar", default=5, min=0, max=30),
    BoolSceneProperty("gameready_triangulate", "Triangulate", "Triangulate the mesh of the new game asset", True),
    BoolSceneProperty("gameready_bake_textures", "Bake Textures", "Bake textures from the original object's materials to the new game asset", True),
    BoolSceneProperty("gameready_fast_low_quality", "Fast / Low-Quality", "Use minimum bake samples and texture compression for quick preview bakes", False, update=on_fast_low_quality_changed),
    EnumSceneProperty("gameready_texture_size", "Texture Size", "Resolution of the baked texture", items=[("256", "256", "256 x 256"), ("512", "512", "512 x 512"), ("1024", "1024", "1024 x 1024"), ("2048", "2048", "2048 x 2048"), ("4096", "4096", "4096 x 4096"), ("8192", "8192", "8192 x 8192")], default="1024"),
    IntSceneProperty("gameready_texture_compression", "Texture Compression", "PNG compression effort for all exported baked textures (0 = fastest, 100 = smallest files)", default=100, min=0, max=100, subtype='PERCENTAGE'),
    BoolSceneProperty("gameready_generate_lods", "Generate LODs", "Automatically generate Level of Detail models", False),
    IntSceneProperty("gameready_lod_count", "LOD Count", "Number of LOD levels to generate", default=3, min=1, max=10),
    BoolSceneProperty("gameready_bake_base_color", "Base Color", "Bake base color from the original object's materials to the new game asset", True),
    BoolSceneProperty("gameready_bake_alpha", "Alpha", "Add an alpha channel to the baked base color texture if needed", False),
    BoolSceneProperty("gameready_bake_emission", "Emission", "Bake emission from the original object's materials to the new game asset", False),
    BoolSceneProperty("gameready_bake_sss", "Subsurface Scattering", "Bake a subsurface scattering texture from Subsurface Weight multiplied by Subsurface Radius", False),
    BoolSceneProperty("gameready_bake_normal", "Normal Map", "Bake normal map from the original object's materials to the new game asset", True),
    BoolSceneProperty("gameready_flip_y_normal", "Flip Y Normal", "Flip the Y channel of the baked normal map", True),
    BoolSceneProperty("gameready_bake_ao", "Ambient Occlusion", "Bake ambient occlusion from the original object's materials to the new game asset", True),
    BoolSceneProperty("gameready_bake_roughness", "Roughness", "Bake roughness from the original object's materials to the new game asset", True),
    BoolSceneProperty("gameready_bake_metallic", "Metallic", "Bake metallic from the original object's materials to the new game asset", True),
    BoolSceneProperty("gameready_pack_as_orm", "Pack as ORM", "Pack roughness, metallic, and ambient occlusion into a single texture", True),
    IntSceneProperty("gameready_sample_count", "Sample Count", "Number of samples to use when baking textures", default=512, min=8, max=1024),
    BoolSceneProperty("gameready_auto_cage_extrusion", "Auto Cage Extrusion", "Automatically calculate a safe cage extrusion distance for selected-to-active texture baking", True),
    FloatSceneProperty("gameready_cage_extrusion", "Cage Extrusion", "Amount of extrusion to apply to the cage when baking", default=0.07, min=0.0, max=1.0),
    BoolSceneProperty("gameready_shade_auto_smooth", "Auto Smooth Shading", "Enable auto smooth shading on the new game asset", True),
    IntSceneProperty("gameready_auto_smooth_angle", "Auto Smooth Angle", "Angle for auto smooth shading", default=60, min=0, max=180),
    BoolSceneProperty("gameready_job_running", "Job Running", "True while the game asset build job is running", default=False, options={'SKIP_SAVE'}),
    FloatSceneProperty("gameready_job_progress", "Job Progress", "Progress of the running game asset build job", default=0.0, min=0.0, max=100.0, subtype='PERCENTAGE', options={'SKIP_SAVE'}),
    StringSceneProperty("gameready_job_current_step_label", "Current Step", "Current game asset build step", default="", options={'SKIP_SAVE'}),
    StringSceneProperty("gameready_job_status_text", "Job Status", "Additional job status text", default="", options={'SKIP_SAVE'}),
    StringSceneProperty("gameready_job_result_text", "Job Result", "Final result text of the last build job", default="", options={'SKIP_SAVE'}),
]

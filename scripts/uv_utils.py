# Purpose: uv utils module.
# Example: import uv_utils
import math
import bpy


class UVUtils:
    SMART_PROJECT_ANGLE_LIMIT = math.radians(72.0)
    SMART_PROJECT_ISLAND_MARGIN = 0.0
    SMART_PROJECT_AREA_WEIGHT = 0.0
    DEFAULT_PACK_MARGIN_PIXELS = 1.0
    MIN_PACK_MARGIN_PIXELS = 0.0
    MAX_PACK_MARGIN_PIXELS = 16.0

    @staticmethod
    def unwrap_object(context, obj):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Game asset mesh for UV unwrapping was not found.")

        UVUtils._select_single_object(context, obj)
        UVUtils._ensure_uv_layer(obj)

        try:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

        try:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='SELECT')
            UVUtils._unwrap_with_smart_project(context)
        finally:
            try:
                if context.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

    @staticmethod
    def _select_single_object(context, obj):
        for selected_object in list(context.selected_objects):
            selected_object.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

    @staticmethod
    def _ensure_uv_layer(obj):
        mesh = obj.data
        if getattr(mesh, "uv_layers", None) is None:
            return

        if not mesh.uv_layers:
            mesh.uv_layers.new(name="UVMap")

        if mesh.uv_layers.active is None and mesh.uv_layers:
            mesh.uv_layers.active = mesh.uv_layers[0]

    @staticmethod
    def _get_texture_resolution(context):
        value = getattr(context.scene, "gameready_texture_size", "1024")
        try:
            return max(1, int(value))
        except Exception:
            return 1024

    @staticmethod
    def _get_pack_margin_pixels(context):
        configured_margin = getattr(context.scene, "gameready_uv_island_margin", UVUtils.DEFAULT_PACK_MARGIN_PIXELS)

        try:
            margin_pixels = float(configured_margin)
        except Exception:
            margin_pixels = UVUtils.DEFAULT_PACK_MARGIN_PIXELS

        return max(UVUtils.MIN_PACK_MARGIN_PIXELS, min(UVUtils.MAX_PACK_MARGIN_PIXELS, margin_pixels))

    @staticmethod
    def _get_final_pack_margin(context):
        texture_resolution = UVUtils._get_texture_resolution(context)
        return UVUtils._get_pack_margin_pixels(context) / float(texture_resolution)

    @staticmethod
    def _unwrap_with_smart_project(context):
        bpy.ops.uv.smart_project(
            angle_limit=UVUtils.SMART_PROJECT_ANGLE_LIMIT,
            margin_method='FRACTION',
            rotate_method='AXIS_ALIGNED_Y',
            island_margin=UVUtils.SMART_PROJECT_ISLAND_MARGIN,
            area_weight=UVUtils.SMART_PROJECT_AREA_WEIGHT,
            correct_aspect=True,
            scale_to_bounds=False,
        )

        bpy.ops.uv.select_all(action='SELECT')

        try:
            bpy.ops.uv.average_islands_scale()
        except Exception:
            pass

        UVUtils._pack_islands_dense(context)

    @staticmethod
    def _pack_islands_dense(context):
        final_pack_margin = UVUtils._get_final_pack_margin(context)

        try:
            bpy.ops.uv.pack_islands(
                udim_source='CLOSEST_UDIM',
                rotate=True,
                rotate_method='ANY',
                scale=True,
                merge_overlap=False,
                margin_method='FRACTION',
                margin=final_pack_margin,
                pin=False,
                pin_method='LOCKED',
                shape_method='CONCAVE',
            )
            return
        except TypeError:
            pass
        except Exception:
            pass

        try:
            bpy.ops.uv.pack_islands(
                rotate=True,
                scale=True,
                margin=final_pack_margin,
            )
            return
        except TypeError:
            pass
        except Exception:
            pass

        try:
            bpy.ops.uv.pack_islands(
                rotate=True,
                margin=final_pack_margin,
            )
        except TypeError:
            bpy.ops.uv.pack_islands(rotate=True)
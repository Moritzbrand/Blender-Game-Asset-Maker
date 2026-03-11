# Purpose: export utils module.
# Example: import export_utils
import ast
import json
import os

import bpy

from .settings_utils import AddonSettings


class ExportPresetFileParser:
    @staticmethod
    def read_operator_settings_from_python_preset(preset_file_path):
        if not preset_file_path or not os.path.isfile(preset_file_path):
            return {}

        with open(preset_file_path, "r", encoding="utf-8") as preset_file:
            preset_source_code = preset_file.read()

        parsed_syntax_tree = ast.parse(preset_source_code, filename=preset_file_path)
        operator_settings = {}

        for syntax_node in parsed_syntax_tree.body:
            if not isinstance(syntax_node, ast.Assign):
                continue
            if len(syntax_node.targets) != 1:
                continue

            assignment_target = syntax_node.targets[0]
            if not isinstance(assignment_target, ast.Attribute):
                continue
            if not isinstance(assignment_target.value, ast.Name):
                continue
            if assignment_target.value.id != "op":
                continue

            try:
                operator_settings[assignment_target.attr] = ast.literal_eval(syntax_node.value)
            except Exception:
                continue

        return operator_settings


class ExportPresetCatalog:
    ADDON_PRESET_FILE_NAME = AddonSettings.get_value(
        "export.preset_file_name",
        "export_presets.json",
    )
    USER_PRESET_SOURCE = "USER_PRESET"
    ADDON_PRESET_SOURCE = "ADDON_PRESET"

    @classmethod
    def build_preset_enum_items(cls, export_format_identifier):
        preset_descriptors = cls.get_preset_descriptors(export_format_identifier)

        if not preset_descriptors:
            return [
                (
                    "NONE",
                    "No Preset",
                    "No export presets were found for the selected export format",
                )
            ]

        return [
            (
                preset_descriptor["identifier"],
                preset_descriptor["label"],
                preset_descriptor["description"],
            )
            for preset_descriptor in preset_descriptors
        ]

    @classmethod
    def get_preset_settings(cls, export_format_identifier, preset_identifier):
        if not preset_identifier or preset_identifier == "NONE":
            return {}

        preset_descriptors = cls.get_preset_descriptors(export_format_identifier)

        for preset_descriptor in preset_descriptors:
            if preset_descriptor["identifier"] != preset_identifier:
                continue

            if preset_descriptor["source"] == cls.ADDON_PRESET_SOURCE:
                return dict(preset_descriptor.get("settings", {}))

            if preset_descriptor["source"] == cls.USER_PRESET_SOURCE:
                preset_file_path = preset_descriptor.get("file_path", "")
                return ExportPresetFileParser.read_operator_settings_from_python_preset(
                    preset_file_path
                )

        return {}

    @classmethod
    def get_preset_descriptors(cls, export_format_identifier):
        export_strategy = ExportStrategyRegistry.get_strategy(export_format_identifier)
        if export_strategy is None:
            return []

        preset_descriptors = []
        preset_descriptors.extend(cls._load_addon_json_preset_descriptors(export_strategy))
        preset_descriptors.extend(cls._load_user_preset_descriptors(export_strategy))
        return preset_descriptors

    @classmethod
    def _load_addon_json_preset_descriptors(cls, export_strategy):
        addon_preset_file_path = os.path.join(
            os.path.dirname(__file__),
            "data",
            cls.ADDON_PRESET_FILE_NAME,
        )

        if not os.path.isfile(addon_preset_file_path):
            return []

        try:
            with open(addon_preset_file_path, "r", encoding="utf-8") as addon_preset_file:
                addon_preset_data = json.load(addon_preset_file)
        except Exception:
            return []

        format_preset_entries = addon_preset_data.get(export_strategy.format_identifier, [])
        preset_descriptors = []

        for preset_entry in format_preset_entries:
            preset_id = preset_entry.get("id")
            preset_label = preset_entry.get("label")

            if not preset_id or not preset_label:
                continue

            preset_descriptors.append(
                {
                    "identifier": f"ADDON::{export_strategy.format_identifier}::{preset_id}",
                    "label": f"{preset_label} (Addon)",
                    "description": preset_entry.get(
                        "description",
                        f"Addon preset for {export_strategy.format_label}",
                    ),
                    "source": cls.ADDON_PRESET_SOURCE,
                    "settings": dict(preset_entry.get("settings", {})),
                }
            )

        return preset_descriptors

    @classmethod
    def _load_user_preset_descriptors(cls, export_strategy):
        preset_descriptors = []
        preset_search_paths = bpy.utils.preset_paths(export_strategy.preset_subdir)

        for preset_directory_path in preset_search_paths:
            if not os.path.isdir(preset_directory_path):
                continue

            for entry_name in sorted(os.listdir(preset_directory_path)):
                if not entry_name.endswith(".py"):
                    continue

                preset_file_path = os.path.join(preset_directory_path, entry_name)
                preset_name = os.path.splitext(entry_name)[0]
                display_label = bpy.path.display_name(preset_name)

                preset_descriptors.append(
                    {
                        "identifier": f"USER::{export_strategy.format_identifier}::{preset_name}",
                        "label": f"{display_label} (User)",
                        "description": f"User Blender preset from {preset_file_path}",
                        "source": cls.USER_PRESET_SOURCE,
                        "file_path": preset_file_path,
                    }
                )

        return preset_descriptors


class BaseExportStrategy:
    format_identifier = ""
    format_label = ""
    file_extension = ""
    operator_bl_idname = ""

    @property
    def preset_subdir(self):
        return f"operator/{self.operator_bl_idname}"

    def get_operator_function(self):
        raise NotImplementedError("Subclasses must return a Blender export operator")

    def get_default_operator_settings(self, export_file_path):
        return {
            "filepath": export_file_path,
            "check_existing": False,
        }

    def get_forced_operator_settings(self, export_file_path):
        return {
            "filepath": export_file_path,
        }

    def export_selected_object(self, export_file_path, preset_settings):
        operator_function = self.get_operator_function()

        operator_settings = self.get_default_operator_settings(export_file_path)
        operator_settings.update(dict(preset_settings or {}))
        operator_settings.update(self.get_forced_operator_settings(export_file_path))
        operator_settings = self._filter_supported_operator_settings(
            operator_function,
            operator_settings,
        )

        operator_function(**operator_settings)

    def build_export_path(self, output_dir, file_name):
        absolute_output_directory = bpy.path.abspath(output_dir)
        os.makedirs(absolute_output_directory, exist_ok=True)

        export_file_name = file_name or AddonSettings.get_value(
            "defaults.export_file_name",
            "export",
        )

        if not export_file_name.lower().endswith(self.file_extension.lower()):
            export_file_name = f"{export_file_name}{self.file_extension}"

        return os.path.join(absolute_output_directory, export_file_name)

    def _filter_supported_operator_settings(self, operator_function, operator_settings):
        try:
            operator_rna = operator_function.get_rna_type()
            supported_property_names = {
                property_definition.identifier
                for property_definition in operator_rna.properties
            }
        except Exception:
            return operator_settings

        filtered_operator_settings = {}

        for setting_name, setting_value in operator_settings.items():
            if setting_name in supported_property_names:
                filtered_operator_settings[setting_name] = setting_value

        return filtered_operator_settings


class FbxExportStrategy(BaseExportStrategy):
    format_identifier = "FBX"
    format_label = "FBX"
    file_extension = ".fbx"
    operator_bl_idname = "export_scene.fbx"

    def get_operator_function(self):
        return bpy.ops.export_scene.fbx

    def get_default_operator_settings(self, export_file_path):
        operator_settings = super().get_default_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.fbx", {}))
        )
        return operator_settings

    def get_forced_operator_settings(self, export_file_path):
        operator_settings = super().get_forced_operator_settings(export_file_path)
        operator_settings.update(
            {"use_selection": AddonSettings.get_value("export.fbx.use_selection", True)}
        )
        return operator_settings


class GlbExportStrategy(BaseExportStrategy):
    format_identifier = "GLB"
    format_label = "glTF Binary (.glb)"
    file_extension = ".glb"
    operator_bl_idname = "export_scene.gltf"

    def get_operator_function(self):
        return bpy.ops.export_scene.gltf

    def get_default_operator_settings(self, export_file_path):
        operator_settings = super().get_default_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.glb", {}))
        )
        return operator_settings

    def get_forced_operator_settings(self, export_file_path):
        operator_settings = super().get_forced_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.glb", {}))
        )
        return operator_settings


class GltfSeparateExportStrategy(BaseExportStrategy):
    format_identifier = "GLTF"
    format_label = "glTF Separate (.gltf)"
    file_extension = ".gltf"
    operator_bl_idname = "export_scene.gltf"

    def get_operator_function(self):
        return bpy.ops.export_scene.gltf

    def get_default_operator_settings(self, export_file_path):
        operator_settings = super().get_default_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.gltf", {}))
        )
        return operator_settings

    def get_forced_operator_settings(self, export_file_path):
        operator_settings = super().get_forced_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.gltf", {}))
        )
        return operator_settings


class ObjExportStrategy(BaseExportStrategy):
    format_identifier = "OBJ"
    format_label = "Wavefront OBJ"
    file_extension = ".obj"
    operator_bl_idname = "wm.obj_export"

    def get_operator_function(self):
        return bpy.ops.wm.obj_export

    def get_default_operator_settings(self, export_file_path):
        operator_settings = super().get_default_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.obj", {}))
        )
        return operator_settings

    def get_forced_operator_settings(self, export_file_path):
        operator_settings = super().get_forced_operator_settings(export_file_path)
        operator_settings.update(
            dict(AddonSettings.get_value("export.obj", {}))
        )
        return operator_settings


class ExportStrategyRegistry:
    _strategies_by_identifier = {
        "FBX": FbxExportStrategy(),
        "GLB": GlbExportStrategy(),
        "GLTF": GltfSeparateExportStrategy(),
        "OBJ": ObjExportStrategy(),
    }

    @classmethod
    def get_strategy(cls, export_format_identifier):
        return cls._strategies_by_identifier.get(export_format_identifier)

    @classmethod
    def build_format_enum_items(cls):
        enum_items = []

        for export_format_identifier, export_strategy in cls._strategies_by_identifier.items():
            enum_items.append(
                (
                    export_format_identifier,
                    export_strategy.format_label,
                    f"Export as {export_strategy.format_label}",
                )
            )

        return enum_items


class BaseMaterialExportStrategy:
    strategy_identifier = ""
    strategy_label = ""
    strategy_description = ""

    def prepare_object_for_export(self, export_object, export_format_identifier):
        raise NotImplementedError("Subclasses must prepare the export object")


class StripMaterialsExportStrategy(BaseMaterialExportStrategy):
    strategy_identifier = "STRIP_MATERIALS"
    strategy_label = "Geometry Only"
    strategy_description = "Remove all materials before export"

    def prepare_object_for_export(self, export_object, export_format_identifier):
        ExportUtils.remove_all_materials(export_object)
        return export_object


class KeepMaterialsExportStrategy(BaseMaterialExportStrategy):
    strategy_identifier = "KEEP_MATERIALS"
    strategy_label = "Keep Materials"
    strategy_description = "Keep the current material slots during export"

    def prepare_object_for_export(self, export_object, export_format_identifier):
        return export_object


class MaterialExportStrategyRegistry:
    _strategies_by_identifier = {
        "STRIP_MATERIALS": StripMaterialsExportStrategy(),
        "KEEP_MATERIALS": KeepMaterialsExportStrategy(),
    }

    @classmethod
    def get_strategy(cls, strategy_identifier):
        return cls._strategies_by_identifier.get(strategy_identifier)

    @classmethod
    def build_enum_items(cls):
        enum_items = []

        for strategy_identifier, strategy in cls._strategies_by_identifier.items():
            enum_items.append(
                (
                    strategy_identifier,
                    strategy.strategy_label,
                    strategy.strategy_description,
                )
            )

        return enum_items


class ExportUtils:
    @staticmethod
    def build_lod_ratios(lod_count):
        lod_count = max(0, int(lod_count))
        if lod_count == 0:
            return []

        step = 1.0 / (lod_count + 1)
        lod_ratio_precision = AddonSettings.get_value("export.lod_ratio_precision", 6)
        return [round(step * i, lod_ratio_precision) for i in range(1, lod_count + 1)]

    @staticmethod
    def apply_collapse_decimate_for_export(context, obj, ratio):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        ratio = max(0.0, min(1.0, float(ratio)))

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for other in list(context.selected_objects):
            other.select_set(False)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        modifier = obj.modifiers.new(name=f"LOD_Collapse_{ratio:.3f}", type='DECIMATE')
        modifier.decimate_type = 'COLLAPSE'
        modifier.ratio = ratio

        override_context = context.copy()
        override_context["active_object"] = obj
        override_context["object"] = obj
        override_context["selected_objects"] = [obj]
        override_context["selected_editable_objects"] = [obj]

        with context.temp_override(**override_context):
            bpy.ops.object.modifier_apply(modifier=modifier.name)

        return obj

    @staticmethod
    def duplicate_object_for_export(context, obj, new_name=None):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        export_obj = obj.copy()

        if obj.data is not None:
            export_obj.data = obj.data.copy()

        context.collection.objects.link(export_obj)
        export_obj.matrix_world = obj.matrix_world.copy()

        if new_name:
            export_obj.name = new_name
            if export_obj.data is not None:
                export_obj.data.name = f"{new_name}_MESH"

        return export_obj

    @staticmethod
    def remove_all_materials(obj):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        obj.data.materials.clear()
        return obj

    @staticmethod
    def export_object(
        context,
        obj,
        output_dir,
        file_name,
        export_format_identifier,
        preset_identifier,
    ):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        export_strategy = ExportStrategyRegistry.get_strategy(export_format_identifier)
        if export_strategy is None:
            raise ValueError(f"Unsupported export format: {export_format_identifier}")

        preset_settings = ExportPresetCatalog.get_preset_settings(
            export_format_identifier,
            preset_identifier,
        )

        export_file_path = export_strategy.build_export_path(output_dir, file_name)

        previous_selected_objects = list(context.selected_objects)
        previous_active_object = context.view_layer.objects.active

        try:
            for other in list(context.selected_objects):
                other.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj

            export_strategy.export_selected_object(
                export_file_path=export_file_path,
                preset_settings=preset_settings,
            )
        finally:
            for other in list(context.selected_objects):
                other.select_set(False)

            for previous_selected_object in previous_selected_objects:
                if previous_selected_object is None:
                    continue
                if previous_selected_object.name not in bpy.data.objects:
                    continue
                previous_selected_object.select_set(True)

            if previous_active_object is not None and previous_active_object.name in bpy.data.objects:
                context.view_layer.objects.active = previous_active_object

        return export_file_path

    @staticmethod
    def export_object_and_lods(
        context,
        obj,
        output_dir,
        lod_count,
        export_format_identifier,
        preset_identifier,
        material_export_strategy_identifier,
    ):
        if obj is None or obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        material_export_strategy = MaterialExportStrategyRegistry.get_strategy(
            material_export_strategy_identifier
        )
        if material_export_strategy is None:
            material_export_strategy = MaterialExportStrategyRegistry.get_strategy(
                AddonSettings.get_value(
                    "defaults.material_export_strategy",
                    "STRIP_MATERIALS",
                )
            )

        exported_file_paths = []

        export_copy = ExportUtils.duplicate_object_for_export(
            context,
            obj,
            new_name=f"{obj.name}_{export_format_identifier}_EXPORT",
        )
        material_export_strategy.prepare_object_for_export(
            export_copy,
            export_format_identifier,
        )

        try:
            exported_file_paths.append(
                ExportUtils.export_object(
                    context=context,
                    obj=export_copy,
                    output_dir=output_dir,
                    file_name=obj.name,
                    export_format_identifier=export_format_identifier,
                    preset_identifier=preset_identifier,
                )
            )
        finally:
            existing_export_copy = bpy.data.objects.get(export_copy.name)
            if existing_export_copy is not None:
                bpy.data.objects.remove(existing_export_copy, do_unlink=True)

        lod_ratios = ExportUtils.build_lod_ratios(lod_count)

        for lod_index, lod_ratio in enumerate(reversed(lod_ratios), start=1):
            lod_export_object = ExportUtils.duplicate_object_for_export(
                context,
                obj,
                new_name=f"{obj.name}_LOD{lod_index}_{export_format_identifier}_EXPORT",
            )
            material_export_strategy.prepare_object_for_export(
                lod_export_object,
                export_format_identifier,
            )
            ExportUtils.apply_collapse_decimate_for_export(
                context,
                lod_export_object,
                lod_ratio,
            )

            try:
                exported_file_paths.append(
                    ExportUtils.export_object(
                        context=context,
                        obj=lod_export_object,
                        output_dir=output_dir,
                        file_name=f"{obj.name}_LOD{lod_index}",
                        export_format_identifier=export_format_identifier,
                        preset_identifier=preset_identifier,
                    )
                )
            finally:
                existing_lod_export_object = bpy.data.objects.get(lod_export_object.name)
                if existing_lod_export_object is not None:
                    bpy.data.objects.remove(existing_lod_export_object, do_unlink=True)

        return exported_file_paths

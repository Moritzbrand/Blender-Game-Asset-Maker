# Purpose: export enums module.
# Example: import export_enums
from ..scripts.export_utils import ExportPresetCatalog, ExportStrategyRegistry
from ..scripts.settings_utils import AddonSettings

_export_format_enum_cache = []
_export_preset_enum_cache = []


def get_export_format_enum_items(self, context):
    global _export_format_enum_cache
    _export_format_enum_cache = ExportStrategyRegistry.build_format_enum_items()
    return _export_format_enum_cache


def get_export_preset_enum_items(self, context):
    global _export_preset_enum_cache
    export_format_identifier = AddonSettings.get_value("defaults.export_format", "FBX")
    if context is not None and context.scene is not None:
        export_format_identifier = getattr(
            context.scene,
            "gameready_export_format",
            AddonSettings.get_value("defaults.export_format", "FBX"),
        )

    _export_preset_enum_cache = ExportPresetCatalog.build_preset_enum_items(export_format_identifier)
    return _export_preset_enum_cache


def on_export_format_changed(self, context):
    preset_items = get_export_preset_enum_items(self, context)
    valid_identifiers = {item[0] for item in preset_items}
    current_identifier = getattr(self, "gameready_export_preset", "")

    if current_identifier in valid_identifiers:
        return
    if preset_items:
        self.gameready_export_preset = preset_items[0][0]

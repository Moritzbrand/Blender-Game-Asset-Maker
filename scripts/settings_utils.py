# Purpose: settings loader for hidden addon config.
# Example: settings = AddonSettings.get_value("defaults.export_format", "FBX")
import json
import os


class AddonSettings:
    _cache = None
    _settings_file_path = os.path.join(
        os.path.dirname(__file__),
        "data",
        "addon_settings.json",
    )

    @classmethod
    def load(cls):
        if cls._cache is not None:
            return cls._cache

        try:
            with open(cls._settings_file_path, "r", encoding="utf-8") as settings_file:
                cls._cache = json.load(settings_file)
        except Exception:
            cls._cache = {}

        return cls._cache

    @classmethod
    def get_value(cls, dotted_key, default_value=None):
        current_value = cls.load()

        for part in dotted_key.split("."):
            if not isinstance(current_value, dict) or part not in current_value:
                return default_value
            current_value = current_value[part]

        return current_value

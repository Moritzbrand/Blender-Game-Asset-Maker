import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.modules.setdefault("bpy", types.SimpleNamespace())

scripts_pkg = types.ModuleType("scripts")
scripts_pkg.__path__ = [str(SCRIPTS_DIR)]
sys.modules.setdefault("scripts", scripts_pkg)

image_utils_spec = importlib.util.spec_from_file_location("scripts.image_utils", SCRIPTS_DIR / "image_utils.py")
image_utils_module = importlib.util.module_from_spec(image_utils_spec)
image_utils_spec.loader.exec_module(image_utils_module)
sys.modules["scripts.image_utils"] = image_utils_module

material_utils_spec = importlib.util.spec_from_file_location("scripts.material_utils", SCRIPTS_DIR / "material_utils.py")
material_utils_module = importlib.util.module_from_spec(material_utils_spec)
material_utils_spec.loader.exec_module(material_utils_module)
MaterialUtils = material_utils_module.MaterialUtils


class MaterialUtilsMappingMathTests(unittest.TestCase):
    def test_normal_output_uses_direction_compensation_without_translation(self):
        ctx = {
            "pre_rotation": (1.0, 0.5, -0.25),
            "pre_scale": (2.0, 3.0, 4.0),
            "post_rotation": (0.25, 0.5, 0.75),
            "post_scale": (1.0, 6.0, 2.0),
        }

        transform = MaterialUtils.compute_mapping_transform_for_texcoord_output("Normal", ctx)

        self.assertEqual(transform["vector_type"], "VECTOR")
        self.assertEqual(transform["location"], (0.0, 0.0, 0.0))
        self.assertEqual(transform["rotation"], (0.75, 0.0, -1.0))
        self.assertEqual(transform["scale"], (2.0, 0.5, 2.0))

    def test_object_output_uses_inverse_pre_post_transform(self):
        ctx = {
            "pre_location": (3.0, -2.0, 7.0),
            "pre_rotation": (0.8, 0.6, -0.2),
            "pre_scale": (10.0, 6.0, 4.0),
            "post_location": (1.0, 1.0, 2.0),
            "post_rotation": (0.3, 0.1, -0.1),
            "post_scale": (2.0, 3.0, 8.0),
        }

        transform = MaterialUtils.compute_mapping_transform_for_texcoord_output("Object", ctx)

        self.assertEqual(transform["vector_type"], "POINT")
        self.assertEqual(transform["location"], (2.0, -3.0, 5.0))
        self.assertEqual(transform["rotation"], (0.5, 0.5, -0.1))
        self.assertEqual(transform["scale"], (5.0, 2.0, 0.5))

    def test_generated_output_compensates_bounds_and_origin_shift(self):
        ctx = {
            "pre_bounds_min": (-1.0, 0.0, 2.0),
            "pre_bounds_size": (4.0, 10.0, 2.0),
            "post_bounds_min": (1.0, -1.0, 3.0),
            "post_bounds_size": (2.0, 5.0, 4.0),
            "origin_shift": (-1.0, 3.0, -2.0),
        }

        transform = MaterialUtils.compute_mapping_transform_for_texcoord_output("Generated", ctx)

        self.assertEqual(transform["vector_type"], "POINT")
        self.assertEqual(transform["rotation"], (0.0, 0.0, 0.0))
        self.assertEqual(transform["scale"], (0.5, 0.5, 2.0))
        self.assertEqual(transform["location"], (0.25, 0.2, -0.5))

    def test_unknown_output_returns_identity(self):
        transform = MaterialUtils.compute_mapping_transform_for_texcoord_output("UV", {})

        self.assertEqual(transform["location"], (0.0, 0.0, 0.0))
        self.assertEqual(transform["rotation"], (0.0, 0.0, 0.0))
        self.assertEqual(transform["scale"], (1.0, 1.0, 1.0))
        self.assertEqual(transform["vector_type"], "POINT")


if __name__ == "__main__":
    unittest.main()

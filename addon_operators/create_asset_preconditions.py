# Purpose: create asset precondition checks.
# Example: from .create_asset_preconditions import CreateAssetPreconditions
from dataclasses import dataclass
from typing import Iterable, List

import bpy


@dataclass(frozen=True)
class PreconditionIssue:
    code: str
    message: str


class CreateAssetPreconditions:
    """Encapsulates all UI/operator start checks for the create workflow."""

    ISSUE_PROGRESS_RUNNING = PreconditionIssue(
        code="progress_running",
        message="Another Game Ready process is already running.",
    )
    ISSUE_SAVE_BLEND_FILE = PreconditionIssue(
        code="blend_file_not_saved",
        message="Save the Blender file before creating a game asset.",
    )
    ISSUE_OBJECT_MODE_REQUIRED = PreconditionIssue(
        code="object_mode_required",
        message="Switch to Object Mode.",
    )
    ISSUE_ACTIVE_OBJECT_REQUIRED = PreconditionIssue(
        code="active_object_required",
        message="Select an active mesh object.",
    )
    ISSUE_ACTIVE_OBJECT_MESH_REQUIRED = PreconditionIssue(
        code="active_object_mesh_required",
        message="The active object must be a mesh.",
    )
    ISSUE_ACTIVE_OBJECT_SELECTED = PreconditionIssue(
        code="active_object_not_selected",
        message="The active object must be selected.",
    )
    ISSUE_SELECTED_MESHES_REQUIRED = PreconditionIssue(
        code="selected_meshes_required",
        message="Select at least one mesh object.",
    )
    ISSUE_ONLY_MESH_OBJECTS = PreconditionIssue(
        code="non_mesh_selected",
        message="Only mesh objects can be selected.",
    )
    ISSUE_SELECTED_TO_ACTIVE_NEEDS_MULTIPLE = PreconditionIssue(
        code="selected_to_active_needs_multiple",
        message="'Bake Selected to Active' needs at least two selected meshes.",
    )
    ISSUE_INVALID_PRINCIPLED_SETUP = PreconditionIssue(
        code="invalid_principled_setup",
        message="Each source mesh material must contain exactly one Principled BSDF node.",
    )

    @classmethod
    def evaluate(cls, context: bpy.types.Context) -> List[PreconditionIssue]:
        issues: List[PreconditionIssue] = []
        window_manager = context.window_manager

        if getattr(window_manager, "gameready_progress_running", False):
            issues.append(cls.ISSUE_PROGRESS_RUNNING)

        if not bpy.data.is_saved:
            issues.append(cls.ISSUE_SAVE_BLEND_FILE)

        if context.mode != 'OBJECT':
            issues.append(cls.ISSUE_OBJECT_MODE_REQUIRED)

        active_object = context.active_object
        if active_object is None:
            issues.append(cls.ISSUE_ACTIVE_OBJECT_REQUIRED)
            return issues

        if active_object.type != 'MESH':
            issues.append(cls.ISSUE_ACTIVE_OBJECT_MESH_REQUIRED)

        selected_objects = list(context.selected_objects)
        selected_meshes = [obj for obj in selected_objects if obj.type == 'MESH']

        if active_object not in selected_objects:
            issues.append(cls.ISSUE_ACTIVE_OBJECT_SELECTED)

        if not selected_meshes:
            issues.append(cls.ISSUE_SELECTED_MESHES_REQUIRED)

        if any(obj.type != 'MESH' for obj in selected_objects):
            issues.append(cls.ISSUE_ONLY_MESH_OBJECTS)

        if context.scene.gameready_bake_selected_to_active and len(selected_meshes) < 2:
            issues.append(cls.ISSUE_SELECTED_TO_ACTIVE_NEEDS_MULTIPLE)

        if selected_meshes and not cls._all_materials_have_single_principled_bsdf(selected_meshes):
            issues.append(cls.ISSUE_INVALID_PRINCIPLED_SETUP)

        return issues

    @classmethod
    def reasons(cls, context: bpy.types.Context) -> List[str]:
        return [issue.message for issue in cls.evaluate(context)]

    @staticmethod
    def _all_materials_have_single_principled_bsdf(mesh_objects: Iterable[bpy.types.Object]) -> bool:
        for mesh_object in mesh_objects:
            if not CreateAssetPreconditions._object_materials_have_single_principled_bsdf(mesh_object):
                return False
        return True

    @staticmethod
    def _object_materials_have_single_principled_bsdf(mesh_object: bpy.types.Object) -> bool:
        materials = [slot.material for slot in mesh_object.material_slots]
        if not materials:
            return False

        if any(material is None for material in materials):
            return False

        unique_materials = list(dict.fromkeys(materials))
        for material in unique_materials:
            if not CreateAssetPreconditions._material_has_single_principled_bsdf(material):
                return False

        return True

    @staticmethod
    def _material_has_single_principled_bsdf(material: bpy.types.Material) -> bool:
        node_tree = getattr(material, "node_tree", None)
        if node_tree is None:
            return False

        principled_nodes = [node for node in node_tree.nodes if node.type == 'BSDF_PRINCIPLED']
        return len(principled_nodes) == 1

# Purpose: create asset precondition checks.
# Example: from .create_asset_preconditions import CreateAssetPreconditions
from dataclasses import dataclass, field
from typing import Iterable, List

import bpy


@dataclass(frozen=True)
class PreconditionIssue:
    code: str
    message: str


@dataclass(frozen=True)
class PreconditionEvaluation:
    blocking_issues: List[PreconditionIssue] = field(default_factory=list)
    warnings: List[PreconditionIssue] = field(default_factory=list)


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
    ISSUE_OBJECT_WITHOUT_MATERIALS_WARNING = PreconditionIssue(
        code="objects_without_materials_warning",
        message=(
            "Bake Textures is enabled, but all selected mesh objects have no assigned materials. "
            "Baking will run, but no material textures can be generated."
        ),
    )

    @classmethod
    def evaluate(cls, context: bpy.types.Context) -> PreconditionEvaluation:
        blocking_issues: List[PreconditionIssue] = []
        warnings: List[PreconditionIssue] = []
        window_manager = context.window_manager

        if getattr(window_manager, "gameready_progress_running", False):
            blocking_issues.append(cls.ISSUE_PROGRESS_RUNNING)

        if not bpy.data.is_saved:
            blocking_issues.append(cls.ISSUE_SAVE_BLEND_FILE)

        if context.mode != 'OBJECT':
            blocking_issues.append(cls.ISSUE_OBJECT_MODE_REQUIRED)

        active_object = context.active_object
        if active_object is None:
            blocking_issues.append(cls.ISSUE_ACTIVE_OBJECT_REQUIRED)
            return PreconditionEvaluation(blocking_issues=blocking_issues, warnings=warnings)

        if active_object.type != 'MESH':
            blocking_issues.append(cls.ISSUE_ACTIVE_OBJECT_MESH_REQUIRED)

        selected_objects = list(context.selected_objects)
        selected_meshes = [obj for obj in selected_objects if obj.type == 'MESH']

        if active_object not in selected_objects:
            blocking_issues.append(cls.ISSUE_ACTIVE_OBJECT_SELECTED)

        if not selected_meshes:
            blocking_issues.append(cls.ISSUE_SELECTED_MESHES_REQUIRED)

        if any(obj.type != 'MESH' for obj in selected_objects):
            blocking_issues.append(cls.ISSUE_ONLY_MESH_OBJECTS)

        if context.scene.gameready_bake_selected_to_active and len(selected_meshes) < 2:
            blocking_issues.append(cls.ISSUE_SELECTED_TO_ACTIVE_NEEDS_MULTIPLE)

        if context.scene.gameready_bake_textures and selected_meshes:
            material_issues = cls._material_setup_issues(selected_meshes)
            blocking_issues.extend(material_issues)

            if cls._all_selected_meshes_without_materials(selected_meshes):
                warnings.append(cls.ISSUE_OBJECT_WITHOUT_MATERIALS_WARNING)

        return PreconditionEvaluation(blocking_issues=blocking_issues, warnings=warnings)

    @classmethod
    def reasons(cls, context: bpy.types.Context) -> List[str]:
        return [issue.message for issue in cls.evaluate(context).blocking_issues]

    @staticmethod
    def _material_setup_issues(mesh_objects: Iterable[bpy.types.Object]) -> List[PreconditionIssue]:
        issues: List[PreconditionIssue] = []
        for mesh_object in mesh_objects:
            for material in CreateAssetPreconditions._assigned_materials(mesh_object):
                if CreateAssetPreconditions._material_has_single_principled_bsdf(material):
                    continue
                issues.append(
                    PreconditionIssue(
                        code="invalid_principled_setup",
                        message=(
                            f"{mesh_object.name}: material '{material.name}' must contain exactly "
                            "one Principled BSDF node."
                        ),
                    )
                )
        return issues

    @staticmethod
    def _all_selected_meshes_without_materials(mesh_objects: Iterable[bpy.types.Object]) -> bool:
        mesh_objects = list(mesh_objects)
        if not mesh_objects:
            return False

        return all(not CreateAssetPreconditions._assigned_materials(mesh_object) for mesh_object in mesh_objects)

    @staticmethod
    def _assigned_materials(mesh_object: bpy.types.Object) -> List[bpy.types.Material]:
        materials = [slot.material for slot in mesh_object.material_slots]
        assigned_materials = [material for material in materials if material is not None]
        return list(dict.fromkeys(assigned_materials))

    @staticmethod
    def _material_has_single_principled_bsdf(material: bpy.types.Material) -> bool:
        node_tree = getattr(material, "node_tree", None)
        if node_tree is None:
            return False

        principled_nodes = [node for node in node_tree.nodes if node.type == 'BSDF_PRINCIPLED']
        return len(principled_nodes) == 1

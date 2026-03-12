# Purpose: models module.
# Example: import models
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class WorkflowStep:
    title: str
    detail: str
    function: Callable[[Any], None]
    weight: float
    completed_detail: str = ""

    def __post_init__(self):
        if not self.completed_detail:
            self.completed_detail = self.detail


@dataclass
class WorkflowState:
    source_object_name: str
    selected_object_names: list[str]
    active_object_name: str = ""
    temporary_object_name: str = ""
    game_asset_name: str = ""
    created_image_names: dict[str, str] = field(default_factory=dict)
    created_image_filepaths: dict[str, str] = field(default_factory=dict)
    visibility_state: dict[str, bool] = field(default_factory=dict)
    cleanup_stats: dict[str, int] = field(
        default_factory=lambda: {
            "removed_nodes": 0,
            "removed_images": 0,
            "removed_materials": 0,
        }
    )
    exported_file_paths: list[str] = field(default_factory=list)
    bake_margin: int = 1
    resolved_cage_extrusion: float = 0.0
    temporary_source_materials: list[dict[str, str]] = field(default_factory=list)
    temporary_shader_material_names: list[str] = field(default_factory=list)
    temporary_shader_group_tree_names: list[str] = field(default_factory=list)
    temporary_mapping_adjustment_records: list[dict[str, str]] = field(default_factory=list)

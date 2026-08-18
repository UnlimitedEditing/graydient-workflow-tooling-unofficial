"""
Core Builder class for Graydient ComfyUI Workflows.
Encapsulates dual-format serialization and automatically enforces pre-flight linting on save.
"""

import json
import os
from typing import Dict, Any, List, Optional
from .linter import lint_workflow, format_lint_report

class GraydientWorkflow:
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.standard_workflow: Dict[str, Any] = {"nodes": [], "links": []}
        self.api_workflow: Dict[str, Any] = {}
        self.concept_mapping: List[Dict[str, Any]] = []
        self.field_mapping: List[Dict[str, Any]] = []
        self.pip_requirements: List[str] = []
        self.github_requirements: List[str] = []
        self.avg_elapsed: int = 120
        self.author: str = "Graydient Pipeline"
        self.metadata: Dict[str, Any] = {}

    def set_workflows(self, standard: Dict[str, Any], api: Dict[str, Any]):
        """Sets the standard UI graph dict and API prompt graph dict."""
        self.standard_workflow = standard
        self.api_workflow = api
        return self

    def add_concept_mapping(self, url: str, destination: str, allow_dynamic: bool = False):
        """Adds a model weight staging entry."""
        self.concept_mapping.append({
            "allow_dynamic": allow_dynamic,
            "concept_name": None,
            "concept_type": None,
            "dynamic_family": None,
            "dynamic_subtype_1": None,
            "dynamic_subtype_2": None,
            "dynamic_type": None,
            "field_mapping": "",
            "is_zipped": False,
            "type": "url",
            "url": url,
            "destination": destination,
            "weight": None,
            "weight_field_mapping": None
        })
        return self

    def add_field_mapping(
        self,
        node_id: int,
        node_input_name: str,
        local_field: str,
        node_name: str = "",
        node_input_index: int = 0,
        default_value: Any = None,
        minimum_value: Any = None,
        maximum_value: Any = None,
        help_text: str = ""
    ):
        """Adds a field mapping entry linking Graydient UI inputs to a node widget."""
        self.field_mapping.append({
            "default_value": default_value,
            "help_text": help_text,
            "local_field": local_field,
            "maximum_value": maximum_value,
            "minimum_value": minimum_value,
            "node_id": node_id,
            "node_input_index": node_input_index,
            "node_input_name": node_input_name,
            "node_name": node_name
        })
        return self

    def add_pip_requirement(self, package: str):
        if package not in self.pip_requirements:
            self.pip_requirements.append(package)
        return self

    def add_github_requirement(self, repo_url: str):
        if repo_url not in self.github_requirements:
            self.github_requirements.append(repo_url)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serializes to the complete Graydient Backup/Restore JSON dictionary."""
        return {
            "graydient_workflow": {
                "author": self.author,
                "avg_elapsed": self.avg_elapsed,
                "concept_mapping": self.concept_mapping,
                "description": self.description,
                "field_mapping": self.field_mapping,
                "name": self.name,
                "requirements": {
                    "github": self.github_requirements,
                    "pip": self.pip_requirements
                },
                "workflow": json.dumps(self.standard_workflow, indent=2),
                "workflow_2": json.dumps(self.api_workflow, indent=2)
            }
        }

    def save(self, filepath: Optional[str] = None, force: bool = False) -> str:
        """
        Validates and writes the backup JSON file.
        Runs the pre-flight linter automatically. Refuses to write if errors exist unless force=True.
        """
        if filepath is None:
            filepath = f"GraydientWorkflow-{self.name}.json"

        data = self.to_dict()
        is_valid, issues = lint_workflow(data)

        report = format_lint_report(issues)
        print(report)

        if not is_valid and not force:
            raise ValueError(
                f"[ERROR] Workflow pre-flight validation failed with errors. "
                f"Fix the issues listed above or pass force=True to bypass.\n\n{report}"
            )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"[SAVED] Successfully wrote verified workflow to: {filepath}")
        return filepath

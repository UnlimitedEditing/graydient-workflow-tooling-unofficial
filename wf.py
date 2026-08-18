#!/usr/bin/env python3
"""
Unified CLI for Graydient ComfyUI Workflow Engineering.
Search capabilities, stage models, lint workflows, and scaffold new builds.
"""

import os
import sys
import json
import glob
import argparse
import subprocess

# Ensure UTF-8 stdout for Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from graydient_builder.linter import lint_workflow, format_lint_report
from graydient_builder.blocks import load_concept_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_DIR = os.path.join(BASE_DIR, "comfyui-graydient-okf-catalog", "catalog")
KI_GRAVEYARD_PATH = os.path.join(CATALOG_DIR, "KI-007-runtime-constraints-and-graveyard.md")

TEMPLATES = {
    "video-audio": '''import json
from graydient_builder import GraydientWorkflow, stage_model, add_audio_duration_sync_block

# Initialize workflow
wf = GraydientWorkflow(
    name="{name}",
    description="Video generation synchronized with reference audio duration"
)

# 1. Pre-stage Model Weights
stage_model(wf, "ltx-2.5-i2v")

# 2. Add Audio Duration Sync Block
audio_block = add_audio_duration_sync_block(wf, load_audio_id=2, duration_node_id=4, math_node_id=5, fps=30)

# 3. Add Common Inputs
wf.add_field_mapping(node_id=1, node_input_name="prompt", local_field="prompt", help_text="Positive prompt")
wf.add_field_mapping(node_id=1, node_input_name="seed", local_field="seed", help_text="Random seed")

# 4. Define ComfyUI Graph
standard_workflow = {
    "nodes": [
        {"id": 1, "type": "KSampler", "widgets_values": ["prompt text", 12345]},
        audio_block["load_audio_node"],
        audio_block["audio_duration_node"],
        audio_block["math_node"]
    ],
    "links": []
}

api_workflow = {
    "1": {"class_type": "KSampler", "inputs": {"prompt": "prompt text", "seed": 12345}},
    "2": {"class_type": "Load Audio Any", "inputs": {"audio": ""}},
    "4": {"class_type": "Audio Duration", "inputs": {"audio": ["2", 0]}},
    "5": {"class_type": "ComfyMathExpression", "inputs": {"expression": "round(a * 30)", "a": ["4", 1]}}
}

wf.set_workflows(standard_workflow, api_workflow)

if __name__ == "__main__":
    wf.save()
''',
    "basic": '''import json
from graydient_builder import GraydientWorkflow

wf = GraydientWorkflow(
    name="{name}",
    description="Basic Graydient ComfyUI workflow"
)

wf.add_field_mapping(node_id=1, node_input_name="prompt", local_field="prompt")
wf.add_field_mapping(node_id=1, node_input_name="seed", local_field="seed")

standard_workflow = {
    "nodes": [
        {"id": 1, "type": "KSampler", "widgets_values": ["prompt text", 12345]}
    ],
    "links": []
}
api_workflow = {
    "1": {"class_type": "KSampler", "inputs": {"prompt": "prompt text", "seed": 12345}}
}

wf.set_workflows(standard_workflow, api_workflow)

if __name__ == "__main__":
    wf.save()
'''
}

def cmd_search(args):
    query = args.query.lower()
    print(f"🔎 Searching Graydient Catalog for: '{query}'\n" + "=" * 60)

    # Search concept staging DB
    db = load_concept_db()
    concept_matches = [k for k in db if query in k.lower()]
    if concept_matches:
        print(f"\n📦 Concept Staging Matches ({len(concept_matches)}):")
        for match in concept_matches:
            print(f"  • {match} ({len(db[match])} files staged)")

    # Search existing generator scripts and workflows
    wf_matches = []
    for f in os.listdir(BASE_DIR):
        if (f.startswith("gen_") or f.startswith("GraydientWorkflow-")) and query in f.lower():
            wf_matches.append(f)
    if wf_matches:
        print(f"\n📜 Existing Workflow Files ({len(wf_matches)}):")
        for f in wf_matches[:10]:
            print(f"  • {f}")

    # Search Graveyard
    if os.path.isfile(KI_GRAVEYARD_PATH):
        with open(KI_GRAVEYARD_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if query in content.lower():
            print("\n⚠️  [GRAVEYARD / ANTI-PATTERN MATCH]:")
            for line in content.splitlines():
                if query in line.lower() and (line.startswith("##") or line.startswith("*") or line.startswith(">")):
                    print(f"  {line}")

    print("\n" + "=" * 60)

def cmd_staging(args):
    db = load_concept_db()
    filter_q = (args.filter or "").lower()
    print("📦 Verified Model Weight Staging Database\n" + "=" * 60)
    for model_key, files in db.items():
        if filter_q and filter_q not in model_key.lower():
            continue
        print(f"\n🏷️  Model: {model_key}")
        for item in files:
            print(f"   ↳ Dest: {item['destination']}")
            print(f"     URL:  {item['url']}")
    print("\n" + "=" * 60)

def cmd_lint(args):
    target = args.target
    if not os.path.isfile(target):
        print(f"❌ Error: File not found: {target}")
        sys.exit(1)

    if target.endswith(".py"):
        print(f"🚀 Running generator script: {target}")
        json_before = {f: os.path.getmtime(f) for f in glob.glob("GraydientWorkflow-*.json")}
        result = subprocess.run([sys.executable, target], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        if result.returncode != 0:
            print(f"❌ Generator script failed with exit code {result.returncode}")
            sys.exit(result.returncode)

        # Running the .py alone doesn't lint anything -- find whichever
        # GraydientWorkflow-*.json it just wrote/touched and lint that too,
        # otherwise `wf lint gen_*.py` silently skips the actual check.
        candidates = glob.glob("GraydientWorkflow-*.json")
        written = [f for f in candidates if os.path.getmtime(f) != json_before.get(f)]
        if not written:
            print("⚠️  No GraydientWorkflow-*.json was created or modified by this script -- "
                  "nothing to lint. If this script writes JSON under a different naming "
                  "pattern, lint it directly: wf lint <output.json>")
            return
        target_json = max(written, key=os.path.getmtime)
        print(f"\n🔍 Linting generated output: {target_json}")
        with open(target_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        is_valid, issues = lint_workflow(data)
        print(format_lint_report(issues))
        if not is_valid:
            sys.exit(1)
        return

    if target.endswith(".json"):
        with open(target, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"❌ Failed to parse JSON: {e}")
                sys.exit(1)

        is_valid, issues = lint_workflow(data)
        print(format_lint_report(issues))
        if not is_valid:
            sys.exit(1)

def cmd_new(args):
    name = args.name
    template_key = args.template or "video-audio"
    if template_key not in TEMPLATES:
        print(f"❌ Unknown template '{template_key}'. Available: {list(TEMPLATES.keys())}")
        sys.exit(1)

    filename = f"gen_{name}.py"
    if os.path.exists(filename):
        print(f"❌ File '{filename}' already exists.")
        sys.exit(1)

    content = TEMPLATES[template_key].replace("{name}", name)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✨ Created new workflow generator script: {filename}")
    print(f"👉 Edit '{filename}' and run `python {filename}` to build and auto-lint.")

def cmd_bury(args):
    title = args.title
    reason = args.reason or "Failed on Graydient ephemeral runner."
    
    if not os.path.isfile(KI_GRAVEYARD_PATH):
        print(f"❌ Graveyard file not found at: {KI_GRAVEYARD_PATH}")
        sys.exit(1)

    entry = f"\n\n### ⚠️ {title}\n* **Platform Failure**: {reason}\n* **Rule**: Avoid this pattern in future builds.\n"
    with open(KI_GRAVEYARD_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"🪦 Buried anti-pattern '{title}' in KI-007 Graveyard.")

def main():
    parser = argparse.ArgumentParser(description="Graydient ComfyUI Workflow Engineering CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    p_search = subparsers.add_parser("search", help="Search nodes, concept staging, and graveyard constraints")
    p_search.add_argument("query", help="Keyword to search for")
    p_search.set_defaults(func=cmd_search)

    # Staging
    p_staging = subparsers.add_parser("staging", help="List verified model concept staging entries")
    p_staging.add_argument("filter", nargs="?", default="", help="Optional model family filter")
    p_staging.set_defaults(func=cmd_staging)

    # Lint
    p_lint = subparsers.add_parser("lint", help="Lint a workflow JSON or test a gen_*.py script")
    p_lint.add_argument("target", help="Path to .json or .py file")
    p_lint.set_defaults(func=cmd_lint)

    # New
    p_new = subparsers.add_parser("new", help="Scaffold a new workflow generator script")
    p_new.add_argument("name", help="Workflow slug/name")
    p_new.add_argument("--template", choices=list(TEMPLATES.keys()), default="video-audio", help="Template scaffold")
    p_new.set_defaults(func=cmd_new)

    # Bury
    p_bury = subparsers.add_parser("bury", help="Log a new failure mode / anti-pattern to the Graveyard")
    p_bury.add_argument("title", help="Short name of the failed approach")
    p_bury.add_argument("--reason", required=True, help="Why it failed on Graydient")
    p_bury.set_defaults(func=cmd_bury)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

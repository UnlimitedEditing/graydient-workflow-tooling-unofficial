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

DIAGNOSTIC_RULES = [
    {
        "pattern": r"(Allocation on device 0 would exceed allowed memory|CUDA out of memory)",
        "issue": "GPU Out of Memory (CUDA OOM)",
        "ki": "KI-005 (§1 VRAM Budgets) / KI-007 (§33 Wan 720p VRAM / TAEHV)",
        "advice": "Container exceeded ~22 GB physical VRAM limit. For Wan video, ensure TAEHV fast VAE decoder is used (from vae_approx/) instead of full BF16 VAE, reduce resolution/frames, or avoid concurrent heavy models."
    },
    {
        "pattern": r"(timed_out|Execution timed out|Prompt executed.*exceeded)",
        "issue": "Job Execution Timeout",
        "ki": "KI-005 (§2 Timeout Budget) / KI-007 (§0 ComfyUI ~180s Limit)",
        "advice": "ComfyUI execution exceeded the ~180s hard limit. Reduce sampling steps (e.g. use Turbo/distilled LoRA), lower canvas resolution, or prune redundant node passes."
    },
    {
        "pattern": r"sgm_uniform",
        "issue": "Flow-Matching Scheduler Mismatch",
        "ki": "KI-007 (§31 MOSS-Image / Flow Matching)",
        "advice": "MOSS-Image / FLUX flow matching strictly requires scheduler: 'simple'. 'sgm_uniform' fails to denoise the velocity field and produces raw multicolored static noise."
    },
    {
        "pattern": r"ModelSamplingSD3.*MOSS",
        "issue": "Redundant Flow Shift on MOSS-Image",
        "ki": "KI-007 (§31 Double-Shift Failure Mode)",
        "advice": "MOSSImage in ComfyUI core natively defines shift: 5.0. Wrapping with ModelSamplingSD3 double-shifts timesteps and distorts generated latents."
    },
    {
        "pattern": r"No @spaces\.GPU function detected",
        "issue": "ZeroGPU Cloud Space AST Missing Decorator",
        "ki": "KI-007 (§32 Cloud-to-Cloud Weight Conversion)",
        "advice": "Hugging Face ZeroGPU supervisor requires an explicit @spaces.GPU decorated function in the AST at startup (e.g. `import spaces; @spaces.GPU def _noop(): return None`)."
    },
    {
        "pattern": r"ModuleNotFoundError: No module named '([^']+)'",
        "issue": "Missing Python Package Dependency",
        "ki": "KI-007 (§19 Pip Install Constraints)",
        "advice": "A node requires an uninstalled package. Check `requirements.pip` in workflow configuration. Note: Packages requiring C++/Rust compilation (cargo/maturin) are banned on ephemeral runners."
    },
    {
        "pattern": r"Cannot execute because node ([^ ]+) does not exist",
        "issue": "Uninstalled Custom Node Class",
        "ki": "KI-007 (§18 Node Repository Packaging)",
        "advice": "ComfyUI cannot find the node class. Check that the custom node git repository is added to `requirements.github`, and ensure the repository has an __init__.py at its root."
    },
    {
        "pattern": r"locator\.waitFor: Timeout.*Changes saved",
        "issue": "Archive Meta Cover Upload Timeout",
        "ki": "KI-007 (§34 Playwright Cover Upload)",
        "advice": "Uploading full-size uncompressed PNGs can exceed the 20s Playwright timeout while Phoenix LiveView handles the upload. Pre-convert cover images to JPEG (~200 KB) before calling `archive meta --image`."
    }
]

def cmd_diagnose(args):
    import re
    target = args.target
    if not target:
        # Search Downloads for latest failure log
        downloads_dir = os.path.expanduser(r"~\Downloads")
        failure_files = glob.glob(os.path.join(downloads_dir, "workflow-failure-*.txt"))
        if failure_files:
            target = max(failure_files, key=os.path.getmtime)
            print(f"📂 Auto-detected most recent failure log: {target}")
        else:
            print("❌ No target log file specified and no workflow-failure-*.txt found in Downloads.")
            sys.exit(1)

    if not os.path.isfile(target):
        print(f"❌ File not found: {target}")
        sys.exit(1)

    with open(target, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    # Try parsing as JSON error payload from Graydient
    job_id = None
    machine = None
    messages = []
    traceback = ""
    try:
        data = json.loads(raw)
        job_id = data.get("job")
        machine = data.get("machine")
        messages = data.get("message", [])
        traceback = data.get("traceback", "")
    except Exception:
        traceback = raw

    print("\n" + "=" * 60)
    print(f"🩺 Graydient Job Diagnostic Report")
    if job_id:
        print(f"   ↳ Job ID:  {job_id}")
    if machine:
        print(f"   ↳ Machine: {machine}")
    print("=" * 60)

    matched = False
    full_text = raw + "\n" + "\n".join(messages) + "\n" + traceback
    for rule in DIAGNOSTIC_RULES:
        m = re.search(rule["pattern"], full_text, re.IGNORECASE)
        if m:
            matched = True
            print(f"\n🚨 Detected Issue: {rule['issue']}")
            print(f"📚 Catalog Rule:   {rule['ki']}")
            print(f"💡 Solution:       {rule['advice']}")
            if m.groups():
                print(f"🔍 Matched detail:  '{m.group(0)}'")

    if not matched:
        print("\n⚠️  No known pattern match in KI-007 Graveyard rules.")
        print("📄 Raw Error Preview:")
        lines = [line for line in full_text.splitlines() if "error" in line.lower() or "exception" in line.lower() or "traceback" in line.lower()]
        for l in lines[:10]:
            print(f"   {l.strip()}")
        print("\n👉 If this is a newly discovered container constraint, bury it using:")
        print(f"   python wf.py bury \"Short Failure Title\" --reason \"Explanation of why it failed\"")

    print("\n" + "=" * 60 + "\n")

def cmd_sync(args):
    import shutil
    repo_dir = args.repo_dir or os.path.join(BASE_DIR, "graydient-workflow-tooling-unofficial")
    if not os.path.isdir(repo_dir):
        print(f"❌ Target unified repository directory not found: {repo_dir}")
        print("Please clone https://github.com/UnlimitedEditing/graydient-workflow-tooling-unofficial first.")
        sys.exit(1)

    print(f"🔄 Syncing resident Graydient files to unified repository: {repo_dir}\n" + "=" * 60)

    # 1. Sync graydient_builder
    src_gb = os.path.join(BASE_DIR, "graydient_builder")
    dst_gb = os.path.join(repo_dir, "graydient_builder")
    os.makedirs(dst_gb, exist_ok=True)
    for f in os.listdir(src_gb):
        if f.endswith(".pyc") or f == "__pycache__": continue
        shutil.copy2(os.path.join(src_gb, f), os.path.join(dst_gb, f))
    print("✅ Synced graydient_builder (core, blocks, linter, concept_db, node_schema_db)")

    # 2. Sync comfyui-graydient-okf-catalog
    src_cat = os.path.join(BASE_DIR, "comfyui-graydient-okf-catalog")
    dst_cat = os.path.join(repo_dir, "comfyui-graydient-okf-catalog")
    for root, dirs, files in os.walk(src_cat):
        if ".git" in root: continue
        rel = os.path.relpath(root, src_cat)
        target_dir = os.path.join(dst_cat, rel)
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
    print("✅ Synced comfyui-graydient-okf-catalog (okf.yaml, catalog KI-001..KI-009, templates)")

    # 3. Sync Agent Skills (to both .agents/skills and .claude/skills)
    src_skills = os.path.join(BASE_DIR, ".agents", "skills")
    dst_agents_skills = os.path.join(repo_dir, ".agents", "skills")
    dst_claude_skills = os.path.join(repo_dir, ".claude", "skills")
    if os.path.isdir(src_skills):
        for s in os.listdir(src_skills):
            s_src = os.path.join(src_skills, s)
            if os.path.isdir(s_src):
                s_dst_a = os.path.join(dst_agents_skills, s)
                s_dst_c = os.path.join(dst_claude_skills, s)
                os.makedirs(s_dst_a, exist_ok=True)
                os.makedirs(s_dst_c, exist_ok=True)
                for f in os.listdir(s_src):
                    sf = os.path.join(s_src, f)
                    if os.path.isfile(sf):
                        shutil.copy2(sf, os.path.join(s_dst_a, f))
                        shutil.copy2(sf, os.path.join(s_dst_c, f))
        print("✅ Synced skills (preflight-plan, harvest-session, graydient-archive, graydient-concepts, higgs-voice, comfyui-workflow-porting)")

    # 4. Sync CLI source from D:\ForgeExpress\cli
    src_cli = r"D:\ForgeExpress\cli"
    dst_cli = os.path.join(repo_dir, "cli")
    if os.path.isdir(src_cli):
        # src
        for root, dirs, files in os.walk(os.path.join(src_cli, "src")):
            rel = os.path.relpath(root, src_cli)
            target_dir = os.path.join(dst_cli, rel)
            os.makedirs(target_dir, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
        # public
        for root, dirs, files in os.walk(os.path.join(src_cli, "public")):
            rel = os.path.relpath(root, src_cli)
            target_dir = os.path.join(dst_cli, rel)
            os.makedirs(target_dir, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
        # package.json & tsconfig
        for cf in ["package.json", "tsconfig.json"]:
            cpf = os.path.join(src_cli, cf)
            if os.path.isfile(cpf):
                shutil.copy2(cpf, os.path.join(dst_cli, cf))
        print("✅ Synced Graydient CLI (src/, public/, package.json, commands, archive, server)")

    # 5. Sync root references, studio, and wf scripts
    for rf in ["GRAYDIENT-COMPLETE-REFERENCE.md", "COMFYUI-REFERENCE.md", "wf.py", "wf.bat", "studio.py", "studio.bat"]:
        r_src = os.path.join(BASE_DIR, rf)
        if os.path.isfile(r_src):
            shutil.copy2(r_src, os.path.join(repo_dir, rf))
            
    # Sync studio/ directory
    src_studio = os.path.join(BASE_DIR, "studio")
    dst_studio = os.path.join(repo_dir, "studio")
    if os.path.isdir(src_studio):
        for root, dirs, files in os.walk(src_studio):
            if "__pycache__" in root: continue
            rel = os.path.relpath(root, src_studio)
            target_dir = os.path.join(dst_studio, rel)
            os.makedirs(target_dir, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
    print("✅ Synced Graydient Studio desktop app (studio/, studio.py, studio.bat)")
    print("✅ Synced root references and wf.py CLI")

    # 6. Optional Git Add, Commit & Push
    if args.push:
        print("\n🚀 Pushing updates to GitHub...")
        msg = args.message or "Sync: updated Graydient tooling, knowledge catalog, and skills"
        res_add = subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, text=True)
        res_status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        if not res_status.stdout.strip():
            print("✨ Working tree clean. Repository is already up to date.")
        else:
            res_commit = subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, capture_output=True, text=True)
            print(res_commit.stdout.strip())
            res_push = subprocess.run(["git", "push", "origin", "master"], cwd=repo_dir, capture_output=True, text=True)
            if res_push.returncode == 0:
                print("🎉 Successfully pushed updates to GitHub!")
            else:
                print(f"❌ Git push failed: {res_push.stderr}")
                sys.exit(res_push.returncode)

    print("\n" + "=" * 60)

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

    # Diagnose
    p_diag = subparsers.add_parser("diagnose", help="Diagnose a workflow failure log or error JSON against KI-007")
    p_diag.add_argument("target", nargs="?", default="", help="Path to error log / failure JSON (auto-detects from Downloads if omitted)")
    p_diag.set_defaults(func=cmd_diagnose)

    # Sync
    p_sync = subparsers.add_parser("sync", help="Sync resident Graydient files to the unified repository")
    p_sync.add_argument("--repo-dir", default="", help="Path to unified repository directory")
    p_sync.add_argument("--push", "-p", action="store_true", help="Automatically commit and git push to GitHub")
    p_sync.add_argument("--message", "-m", default="", help="Custom git commit message")
    p_sync.set_defaults(func=cmd_sync)

    # Studio Desktop App
    p_studio = subparsers.add_parser("studio", help="Launch the Graydient Studio desktop app & M3DS viewer")
    p_studio.add_argument("--port", type=int, default=8765, help="Server port (default 8765)")
    p_studio.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")
    p_studio.set_defaults(func=lambda a: subprocess.run([sys.executable, os.path.join(BASE_DIR, "studio.py"), "--port", str(a.port)] + (["--no-browser"] if a.no_browser else [])))

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

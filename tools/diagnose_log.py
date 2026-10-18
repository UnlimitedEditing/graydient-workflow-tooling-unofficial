#!/usr/bin/env python3
"""
Graydient Job Failure Diagnostics & KI-007 Log Analyzer.
Parses container logs and Graydient error JSON payloads (workflow-failure-R*.txt),
extracts tracebacks and exceptions, and cross-references them against KI-007 Graveyard rules.
"""

import sys
import os
import re
import json
import glob

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
        "advice": "Hugging Face ZeroGPU supervisor requires an explicit @spaces.GPU decorated function in the AST at startup (e.g., `import spaces; @spaces.GPU def _noop(): return None`)."
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

def diagnose(target: str = None):
    if not target:
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

if __name__ == "__main__":
    target_arg = sys.argv[1] if len(sys.argv) > 1 else None
    diagnose(target_arg)

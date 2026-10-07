"""
Pre-Flight Linter for Graydient ComfyUI Workflows.
Catches quota-burning mistakes locally before deploying to ephemeral SaaS GPU instances.
"""

import json
import os
import re
from typing import Dict, Any, List, Tuple

_SCHEMA_DB_PATH = os.path.join(os.path.dirname(__file__), "node_schema_db.json")


def _load_schema_db() -> Dict[str, Any]:
    try:
        with open(_SCHEMA_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# Packages strictly forbidden or known to fail compilation on ephemeral runners.
# NOTE: `ninja` was removed from this list -- confirmed a FALSE POSITIVE. `ninja`
# ships pre-built manylinux wheels on PyPI (it's a build tool other packages
# sometimes shell out to, not something that itself needs compiling), and
# `ninja~=1.11.1.4` appears in the pip install list of real, successful
# Graydient jobs for the LTX-2.5 workflow in this project (gen_ltx2.5_i2v.py,
# confirmed against real job logs, not assumed). A blanket ban here would have
# blocked a workflow already proven to work.
BANNED_PIP_PATTERNS = [
    r"^cargo",
    r"^rust",
    r"^maturin",
    r"^cmake",
    r"^setuptools-rust",
]

KNOWN_PROBLEMATIC_PACKAGES = {
    "flash-attn": "Requires CUDA compilation headers during pip install. Use torch.nn.functional.scaled_dot_product_attention instead.",
    "deepspeed": "Requires local C++ compilation. Use native PyTorch FSDP/bf16.",
    "triton": "Linux runner wheels may mismatch CUDA driver. Ensure PyPI wheel availability.",
}

class LintIssue:
    def __init__(self, level: str, code: str, message: str, node_id: Any = None):
        self.level = level  # "ERROR", "WARNING", "INFO"
        self.code = code
        self.message = message
        self.node_id = node_id

    def __repr__(self):
        node_str = f" [Node {self.node_id}]" if self.node_id is not None else ""
        return f"[{self.level}] {self.code}{node_str}: {self.message}"

class GraydientLinter:
    def __init__(self):
        self.issues: List[LintIssue] = []
        self.schema_db = _load_schema_db()

    def lint(self, workflow_data: Dict[str, Any]) -> List[LintIssue]:
        self.issues = []
        
        # 1. Root structure check
        if "graydient_workflow" not in workflow_data:
            self.issues.append(LintIssue("ERROR", "ROOT_KEY_MISSING", "Missing top-level 'graydient_workflow' key."))
            return self.issues

        gw = workflow_data["graydient_workflow"]

        # 2. Dual workflow parsing
        standard_wf, api_wf = self._parse_dual_workflows(gw)

        # 3. Pip Requirements check (The Pure-Python / Graveyard Rule)
        self._check_requirements(gw)

        # 4. Concept Mapping check
        self._check_concept_mapping(gw)

        # 5. Field Mapping check
        if standard_wf and api_wf:
            self._check_field_mapping(gw, standard_wf, api_wf)

        # 6. Anti-pattern & Node graph analysis
        if standard_wf and api_wf:
            self._check_anti_patterns(gw, standard_wf, api_wf)

        # 7. Verified node-signature cross-check (KI-007/node_schema_db.json)
        if api_wf:
            self._check_node_schemas(api_wf)

        return self.issues

    def _check_node_schemas(self, api_wf: Dict[str, Any]):
        """
        Cross-references every node's inputs in the API graph against
        node_schema_db.json -- a hand-verified registry of real ComfyUI
        node signatures, populated only from nodes actually confirmed
        against source (see that file's _readme). This exists because the
        single biggest source of burned Graydient quota historically was
        guessed input key names (LTXVSeparateAVLatent.samples instead of
        av_latent, ComfyMathExpression.a instead of values.a, etc.) that
        passed local flattening/dangling-link checks fine but failed on a
        real cloud job. Known class_type + unknown input key -> ERROR
        (this would have caught every one of those bugs before deploy).
        Unknown class_type -> INFO (not wrong, just unverified -- confirm
        against source before spending quota, don't treat silence as
        confirmation).
        """
        if not self.schema_db:
            return

        seen_unverified = set()
        for node_id, node in api_wf.items():
            class_type = node.get("class_type")
            if not class_type or class_type.startswith("_"):
                continue

            entry = self.schema_db.get(class_type)
            if entry is None:
                if class_type not in seen_unverified:
                    seen_unverified.add(class_type)
                    self.issues.append(LintIssue(
                        "INFO",
                        "SCHEMA_UNVERIFIED_NODE",
                        f"class_type '{class_type}' has no verified entry in node_schema_db.json. "
                        f"Its input keys were not checked. Confirm against real ComfyUI/custom-node "
                        f"source before deploying, don't treat this silence as confirmation.",
                        node_id
                    ))
                continue

            known_inputs = set(entry.get("inputs", {}).keys())
            if not known_inputs:
                continue

            for input_key in node.get("inputs", {}).keys():
                if input_key not in known_inputs:
                    self.issues.append(LintIssue(
                        "ERROR",
                        "SCHEMA_UNKNOWN_INPUT_KEY",
                        f"class_type '{class_type}' does not have a verified input '{input_key}'. "
                        f"Known inputs: {sorted(known_inputs)}. Source: {entry.get('source', '?')}. "
                        f"This is the exact bug class that has repeatedly burned real Graydient quota "
                        f"-- verify against source, don't guess.",
                        node_id
                    ))

    def _parse_dual_workflows(self, gw: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        standard_wf = None
        api_wf = None

        if "workflow" not in gw or not gw["workflow"]:
            self.issues.append(LintIssue("ERROR", "MISSING_STANDARD_WF", "Missing 'workflow' (UI format)."))
        else:
            try:
                standard_wf = json.loads(gw["workflow"]) if isinstance(gw["workflow"], str) else gw["workflow"]
            except Exception as e:
                self.issues.append(LintIssue("ERROR", "INVALID_STANDARD_JSON", f"Failed to parse 'workflow' JSON: {e}"))

        if "workflow_2" not in gw or not gw["workflow_2"]:
            self.issues.append(LintIssue("ERROR", "MISSING_API_WF", "Missing 'workflow_2' (API prompt format)."))
        else:
            try:
                api_wf = json.loads(gw["workflow_2"]) if isinstance(gw["workflow_2"], str) else gw["workflow_2"]
            except Exception as e:
                self.issues.append(LintIssue("ERROR", "INVALID_API_JSON", f"Failed to parse 'workflow_2' JSON: {e}"))

        return standard_wf, api_wf

    def _check_requirements(self, gw: Dict[str, Any]):
        pip_reqs = gw.get("requirements", {}).get("pip", [])
        github_reqs = gw.get("requirements", {}).get("github", [])

        # Check pip packages
        for pkg in pip_reqs:
            pkg_clean = pkg.strip().lower()
            # OBSERVED live (R20163116, 2026-10-04): in that job's printed COMMAND block the entries
            # 'diffusers>=0.36.0', 'transformers>=5.2.0', 'optimum-quanto>=0.2.4', 'imageio[ffmpeg]' and
            # 'git+...MoGe.git@<sha>' were all ABSENT; bare names, '==' pins and bare URLs were present.
            # NOT established that Graydient always drops these (100+ older workflows use >=, [extras]
            # or ' @ ' and some ran fine), so this is INFO only. Check the job's COMMAND block. KI-007 sec 19.
            if re.search(r"[<>\[\]]|@", pkg.strip()):
                self.issues.append(LintIssue(
                    "INFO",
                    "PIP_SPEC_MAYBE_DROPPED",
                    f"Pip entry '{pkg}' contains <, >, [extras] or @ -- one real job's COMMAND block omitted such entries (KI-007 sec 19). If the package matters, confirm it appears in the job's COMMAND; a bare name, '==' pin or commit .zip URL is known to survive."
                ))
            for pattern in BANNED_PIP_PATTERNS:
                if re.search(pattern, pkg_clean):
                    self.issues.append(LintIssue(
                        "ERROR",
                        "GRAVEYARD_BANNED_PIP",
                        f"Package '{pkg}' violates the Pure Python rule (KI-007). Graydient runners lack C/Rust compiler toolchains."
                    ))
            for prob_pkg, reason in KNOWN_PROBLEMATIC_PACKAGES.items():
                if pkg_clean.startswith(prob_pkg):
                    self.issues.append(LintIssue("WARNING", "PROBLEMATIC_PIP_DEP", f"Package '{pkg}': {reason}"))

        # Check github repos
        for repo in github_reqs:
            if not repo.startswith("https://github.com/"):
                self.issues.append(LintIssue("WARNING", "INVALID_GITHUB_URL", f"Git repo URL '{repo}' should be a direct HTTPS URL."))

    def _check_concept_mapping(self, gw: Dict[str, Any]):
        concept_mapping = gw.get("concept_mapping", [])
        for entry in concept_mapping or []:
            # Dynamic-LoRA slots (type "local", allow_dynamic true, no url/destination) are
            # resolved by Graydient at request time. False positive fixed 2026-10-02:
            # pinkcherry-ltx25 completed a real Graydient job with five of these, and the
            # live Ltx2/H3 workflows (e.g. redgraft-ltx25) store the identical shape.
            if entry.get("allow_dynamic") and entry.get("type") == "local":
                continue
            url = entry.get("url", "")
            dest = entry.get("destination", "")

            if not url or not (url.startswith("http://") or url.startswith("https://")):
                self.issues.append(LintIssue("ERROR", "INVALID_CONCEPT_URL", f"Concept mapping URL '{url}' is invalid."))

            if not dest or dest.startswith("/") or ".." in dest:
                self.issues.append(LintIssue("ERROR", "INVALID_CONCEPT_DEST", f"Destination '{dest}' must be relative to {{ComfyUI}}/models/."))

    def _check_field_mapping(self, gw: Dict[str, Any], standard_wf: Dict[str, Any], api_wf: Dict[str, Any]):
        field_mappings = gw.get("field_mapping", [])
        
        # Build node maps
        std_nodes = {str(n.get("id")): n for n in standard_wf.get("nodes", [])}
        api_nodes = {str(k): v for k, v in api_wf.items()}

        for fm in field_mappings:
            node_id = str(fm.get("node_id"))
            input_name = fm.get("node_input_name", "")
            input_idx = fm.get("node_input_index")
            local_field = fm.get("local_field", "")

            # Stated by Jacob 2026-10-04: slot4..slot8 accept NUMBERS ONLY (and there is no slot9) from users (slot1..slot3 take strings).
            # INFO, not WARNING/ERROR: 23 existing workflows ship non-numeric DEFAULTS in slot4-9 ('htdemucs', 'True',
            # ...) and several are live, so a string default evidently works -- but a user can't type a different one.
            # A string CHOICE on slot4+ should be a numeric slot driving a lazy ComfySwitchNode (KI-007 sec 23).
            _m = re.match(r"slot(\d+)$", str(local_field))
            if _m and int(_m.group(1)) > 8:
                # Stated by Jacob 2026-10-04: Graydient has slot1..slot8 only; a mapping to slot9+ never receives a value.
                self.issues.append(LintIssue(
                    "WARNING", "SLOT_DOES_NOT_EXIST",
                    f"'{local_field}' does not exist: Graydient has slot1..slot8 only, so this mapping can never be set at run time (KI-007 sec 23)."))
            if _m and 4 <= int(_m.group(1)) <= 8:
                _dv = str(fm.get("default_value", ""))
                try:
                    float(_dv)
                except ValueError:
                    if _dv != "":
                        self.issues.append(LintIssue(
                            "INFO", "SLOT4_9_NON_NUMERIC_DEFAULT",
                            f"'{local_field}' has the non-numeric default {_dv[:30]!r}: slots 4-8 only accept numbers from users, so this can never be changed at run time (KI-007 sec 23)."))

            if node_id not in std_nodes:
                self.issues.append(LintIssue("ERROR", "FM_NODE_NOT_IN_STANDARD", f"Field mapped node {node_id} ('{local_field}') not found in 'workflow'.", node_id))
            if node_id not in api_nodes:
                self.issues.append(LintIssue("ERROR", "FM_NODE_NOT_IN_API", f"Field mapped node {node_id} ('{local_field}') not found in 'workflow_2'.", node_id))

            # Widget index check
            if node_id in std_nodes:
                std_node = std_nodes[node_id]
                widgets_values = std_node.get("widgets_values", [])
                if isinstance(input_idx, int):
                    if input_idx < 0:
                        self.issues.append(LintIssue("ERROR", "FM_NEGATIVE_INDEX", f"node_input_index {input_idx} is invalid.", node_id))
                    elif len(widgets_values) <= input_idx:
                        self.issues.append(LintIssue(
                            "WARNING",
                            "FM_INDEX_OUT_OF_BOUNDS",
                            f"node_input_index {input_idx} exceeds widgets_values length ({len(widgets_values)}). Check socket vs widget counting rule (KI-003).",
                            node_id
                        ))

    def _check_anti_patterns(self, gw: Dict[str, Any], standard_wf: Dict[str, Any], api_wf: Dict[str, Any]):
        field_mappings = gw.get("field_mapping", [])
        std_nodes = {str(n.get("id")): n for n in standard_wf.get("nodes", [])}

        # Confirmed live (2026-10-07, ripple-ltx25): concept_mapping's field_mapping /
        # weight_field_mapping strings are "<node_id>-<node title>.<index>-<input name>".
        # A node titled "Load LTX-2.5 Transformer" made the job fail at job PREPARATION
        # (status failure, Error details = a bare "ValueError", no ComfyUI process ever started,
        # and the CLI never noticed -- it waited its whole --timeout). Renaming ONLY that title to
        # "Load Diffusion Model" made the same submission succeed (render 39yNVD, 37.36 s).
        # Only the combination "-" + "." was ever observed failing, so the dot is the prime suspect
        # (it collides with the "." delimiter): ERROR on a dot. A hyphen alone is only WARN --
        # "Load JoyAI-Echo DiT Model" in joyaiecho-t2voice has one and was never confirmed live
        # either way. 156 titles in the existing GraydientWorkflow-*.json had neither character.
        import re as _re_title
        title_re = _re_title.compile(r"^(\d+)-(.*)\.(\d+)-([^.]+)$")
        for cm in (gw.get("concept_mapping") or []):
            for key in ("field_mapping", "weight_field_mapping"):
                fm_str = cm.get(key) or ""
                m = title_re.match(fm_str)
                if not m:
                    continue
                title = m.group(2)
                if "." in title:
                    self.issues.append(LintIssue(
                        "ERROR",
                        "CONCEPT_MAPPING_TITLE_HAS_DOT",
                        f"concept_mapping {key} '{fm_str}' references a node titled '{title}', which "
                        f"contains '.'. The string format is '<node_id>-<title>.<index>-<input>', and a "
                        f"title with '.' + '-' ('Load LTX-2.5 Transformer') made a real job fail at "
                        f"preparation with a bare ValueError (ripple-ltx25, 2026-10-07; KI-007). "
                        f"Rename the node (e.g. 'Load Diffusion Model').",
                        m.group(1)))
                elif "-" in title:
                    self.issues.append(LintIssue(
                        "WARN",
                        "CONCEPT_MAPPING_TITLE_HAS_HYPHEN",
                        f"concept_mapping {key} '{fm_str}' references a node titled '{title}' with a "
                        f"'-'. Unconfirmed either way on its own: a title with BOTH '-' and '.' failed "
                        f"live (KI-007). Safest to use a plain title like 'Load Diffusion Model'.",
                        m.group(1)))

        # Confirmed live (2026-09-01, hunyuanworld-mirror-v1): unlike init_image_url
        # (real URL passthrough), Graydient's numbered image1..image9 slots do NOT
        # accept an "_url" suffixed variant at all -- only the bare name. A real
        # submission to "image6_url" never even reached the node; only bare
        # "image6" does, and it arrives as a Graydient-staged local filename, not
        # a raw URL (see KI-007's "arrive as staged filenames" entry for the
        # node-side handling that requires). This mirrors the init_video/init_audio
        # numbered-slot pattern too, per the same confirmed vocabulary gap.
        import re as _re
        numbered_url_pattern = _re.compile(r"^(image|video|audio)[1-9]_url$")
        for fm in field_mappings:
            local_field = fm.get("local_field", "")
            if numbered_url_pattern.match(local_field):
                self.issues.append(LintIssue(
                    "ERROR",
                    "GRAYDIENT_INVALID_NUMBERED_MEDIA_URL_FIELD",
                    f"local_field '{local_field}' is not a field Graydient accepts -- "
                    f"the numbered image1..9/video1..9/audio1..9 slots only exist as "
                    f"bare names (e.g. 'image6', not 'image6_url'). Unlike init_image_url, "
                    f"there is no confirmed '_url' suffixed variant for these. Confirmed "
                    f"live 2026-09-01 (KI-007) -- the node consuming this slot must also "
                    f"handle a Graydient-staged local filename, not just a URL.",
                    str(fm.get("node_id"))
                ))

        # Confirmed live (2026-09-24, rig-track): a field_mapping with local_field "prompt" never
        # delivered the API prompt to the node -- render ZVzPB9's record held the full prompt
        # (clean_prompt) but the node received "" (track had zero emotion events). The identical
        # workflow re-restored with local_field "prompt_positive" delivered it (render PZJPBn, 12
        # emotion events). prompt_positive is the platform standard (390 deployed workflows vs 25
        # on "prompt"); lyric-llm (id 3210, local_field "prompt") shows the same "{}" symptom.
        for fm in field_mappings:
            if fm.get("local_field") == "prompt":
                self.issues.append(LintIssue(
                    "WARNING",
                    "GRAYDIENT_PROMPT_FIELD_NOT_DELIVERED",
                    "local_field 'prompt' was confirmed NOT to deliver the API prompt to the node "
                    "(2026-09-24, rig-track v1 vs v2). Use 'prompt_positive' (KI-007 section 15).",
                    str(fm.get("node_id"))
                ))

        for fm in field_mappings:
            local_field = fm.get("local_field", "")
            node_id = str(fm.get("node_id"))
            if local_field in ["init_audio", "init_audio_url"]:
                if node_id in std_nodes:
                    node_type = std_nodes[node_id].get("type", "")
                    if node_type == "LoadAudio":
                        self.issues.append(LintIssue(
                            "WARNING",
                            "GRAVEYARD_LOAD_AUDIO_AMBIGUITY",
                            f"Node {node_id} uses built-in 'LoadAudio' for '{local_field}'. Graydient often resolves this as a remote HTTP URL which will crash. Use 'Load Audio Any' (KI-007).",
                            node_id
                        ))

        # VHS_VideoCombine + audio input writes 3 candidate output files (metadata
        # PNG, video-only intermediate, final -audio.mp4) unless the workflow's
        # top-level 'extra' dict explicitly suppresses the extras. Confirmed the hard
        # way: Graydient's output-picker non-deterministically returned the PNG
        # instead of the final mp4 on one real job, then the correct mp4 on an
        # identical retry (KI-007). Only fires when audio is actually wired in --
        # a silent VHS_VideoCombine (images only) never writes the extra files.
        for node in api_wf.values():
            if not isinstance(node, dict) or node.get("class_type") != "VHS_VideoCombine":
                continue
            if not node.get("inputs", {}).get("audio"):
                continue
            extra = standard_wf.get("extra", {}) or {}
            missing = [k for k in ("VHS_MetadataImage", "VHS_KeepIntermediate")
                       if extra.get(k) is not False]
            if missing:
                self.issues.append(LintIssue(
                    "WARNING",
                    "VHS_NONDETERMINISTIC_OUTPUT_PICK",
                    f"VHS_VideoCombine has an audio input but the workflow's top-level "
                    f"'extra' dict doesn't set {missing} to false. Without these, VHS "
                    f"writes 3 candidate output files (metadata PNG, video-only "
                    f"intermediate, final -audio.mp4) and Graydient's output-picker can "
                    f"non-deterministically return the wrong one (confirmed: returned a "
                    f"PNG instead of the video on a real job). Set both to false in the "
                    f"standard workflow's 'extra' dict (KI-007).",
                    None
                ))


def lint_workflow(workflow_data: Dict[str, Any]) -> Tuple[bool, List[LintIssue]]:
    """Runs the linter. Returns (is_valid, list_of_issues)."""
    linter = GraydientLinter()
    issues = linter.lint(workflow_data)
    has_errors = any(issue.level == "ERROR" for issue in issues)
    return (not has_errors), issues


def format_lint_report(issues: List[LintIssue]) -> str:
    """Formats issues into a clear terminal report."""
    if not issues:
        return "[PASS] No issues detected! Workflow complies with all Graydient constraints."
    
    errors = [i for i in issues if i.level == "ERROR"]
    warnings = [i for i in issues if i.level == "WARNING"]
    infos = [i for i in issues if i.level == "INFO"]

    lines = []
    lines.append(f"[LINT] Pre-Flight Results: {len(errors)} Errors, {len(warnings)} Warnings")
    lines.append("=" * 60)
    
    for err in errors:
        lines.append(f"[ERROR] {err.code}" + (f" [Node {err.node_id}]" if err.node_id else "") + f": {err.message}")
    for warn in warnings:
        lines.append(f"[WARN]  {warn.code}" + (f" [Node {warn.node_id}]" if warn.node_id else "") + f": {warn.message}")
    for info in infos:
        lines.append(f"[INFO]  {info.code}" + (f" [Node {info.node_id}]" if info.node_id else "") + f": {info.message}")
        
    lines.append("=" * 60)
    return "\n".join(lines)

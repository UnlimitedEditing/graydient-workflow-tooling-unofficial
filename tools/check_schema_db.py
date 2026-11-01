#!/usr/bin/env python3
"""
Integrity check for the two JSON databases in graydient_builder/.

Why this exists
---------------
`node_schema_db.json` contains DUPLICATE top-level keys. As of 2026-11-01 there are
seven: LoadWanVideoT5TextEncoder, WanVideoModelLoader, WanVideoTextEncode,
WanVideoEmptyEmbeds, WanVideoSampler, WanVideoVAELoader, WanVideoDecode. JSON permits
this and Python's json.load silently keeps the LAST occurrence of each, discarding the
first.

That is a data-loss trap, and it was sprung for real while building
gen_anima_role_ref_kv.py: two new entries were added with the obvious

    db = json.load(open(p)); db["New"] = {...}; json.dump(db, open(p, "w"))

round-trip. The write silently deleted the first copy of all seven duplicated keys --
60 lines of harvested schema detail, including the fuller COMBO option lists
(e.g. WanVideoModelLoader's 10-value `quantization` enum collapsed to 3 values, and
`base_precision: fp32|bf16|fp16|fp16_fast` collapsed to `bf16|fp16|fp32`). Nothing
errored: json.load still returned 153 unique keys, `wf.py lint` still passed, and the
loss only showed up as an unexplained 141-line deletion in `git diff --stat`.

So: NEVER round-trip either database through json.load/json.dump. Add entries by
splicing text in front of the closing brace. Run this script afterwards -- it fails if
a duplicate was collapsed, if an entry disappeared, or if the file stopped parsing.

Usage
-----
    python tools/check_schema_db.py             # check both DBs against git HEAD
    python tools/check_schema_db.py --no-git    # structure only, no HEAD comparison
"""

import argparse
import collections
import io
import json
import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILES = [
    os.path.join(BASE_DIR, "graydient_builder", "node_schema_db.json"),
    os.path.join(BASE_DIR, "graydient_builder", "concept_db.json"),
]

# Duplicated top-level keys in node_schema_db.json as of 2026-11-01. Recorded, not
# fixed: deciding which copy of each pair is authoritative means re-reading
# kijai/ComfyUI-WanVideoWrapper's real source, and guessing would be worse than
# leaving both. This list is what stops the next round-trip from eating them quietly.
KNOWN_DUPLICATE_KEYS = {
    "LoadWanVideoT5TextEncoder", "WanVideoModelLoader", "WanVideoTextEncode",
    "WanVideoEmptyEmbeds", "WanVideoSampler", "WanVideoVAELoader", "WanVideoDecode",
}


def top_level_keys(text):
    """Top-level keys in document order, INCLUDING duplicates, without parsing.

    json.load cannot report duplicates -- they are gone by the time it returns -- so
    they are counted straight off the text. Relies on the file's 2-space top-level
    indent, which both databases use.
    """
    return re.findall(r'^  "([^"]+)":', text, re.M)


def duplicate_keys(text):
    counts = collections.Counter(top_level_keys(text))
    return {k: v for k, v in counts.items() if v > 1}


def entry_shape(text, key):
    """Every occurrence of `key`'s object body, so duplicates can be compared."""
    bodies = []
    for match in re.finditer(r'^  "%s": \{' % re.escape(key), text, re.M):
        depth, i = 0, match.end() - 1
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(text[match.start():i + 1])
                    break
            i += 1
    return bodies


def git_head(path):
    rel = os.path.relpath(path, BASE_DIR).replace(os.sep, "/")
    result = subprocess.run(["git", "-C", BASE_DIR, "show", f"HEAD:{rel}"],
                            capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def check(path, use_git=True):
    name = os.path.basename(path)
    problems, notes = [], []

    if not os.path.isfile(path):
        return [f"{name}: file not found"], []

    text = io.open(path, encoding="utf-8").read()

    # --- parses at all -------------------------------------------------------------
    try:
        loaded = json.loads(text)
    except Exception as exc:
        return [f"{name}: does not parse -- {exc}"], []

    keys = top_level_keys(text)
    dupes = duplicate_keys(text)
    notes.append(f"{name}: {len(keys)} top-level key occurrences, {len(loaded)} unique "
                 f"after json.load, {len(dupes)} duplicated")

    # --- duplicates survived -------------------------------------------------------
    if name == "node_schema_db.json":
        missing = {k for k in KNOWN_DUPLICATE_KEYS if dupes.get(k, 0) < 2}
        if missing:
            problems.append(
                f"{name}: duplicate top-level keys {sorted(missing)} were COLLAPSED -- "
                f"each should still occur twice. A json.load/json.dump round-trip did "
                f"this: restore from git and splice new entries in as text. See this "
                f"script's docstring for the 2026-11-01 incident.")
        unexpected = {k for k in dupes if k not in KNOWN_DUPLICATE_KEYS}
        if unexpected:
            notes.append(f"{name}: newly duplicated keys not in KNOWN_DUPLICATE_KEYS: "
                         f"{sorted(unexpected)} -- add them there once intentional")

    # --- nothing lost versus HEAD --------------------------------------------------
    if use_git:
        head = git_head(path)
        if head is None:
            notes.append(f"{name}: no git HEAD to compare against (new file?)")
        else:
            head_keys = top_level_keys(head)
            lost = collections.Counter(head_keys) - collections.Counter(keys)
            if lost:
                problems.append(
                    f"{name}: {sum(lost.values())} top-level key occurrence(s) present at "
                    f"HEAD are gone: {dict(lost)}. This is silent data loss -- restore and "
                    f"re-apply the change as a text splice.")
            gained = collections.Counter(keys) - collections.Counter(head_keys)
            if gained:
                notes.append(f"{name}: added since HEAD: {sorted(gained)}")
            try:
                json.loads(head)
            except Exception:
                pass
            else:
                head_loaded = json.loads(head)
                gone = set(head_loaded) - set(loaded)
                if gone:
                    problems.append(f"{name}: entries lost after json.load: {sorted(gone)}")

    # --- every entry is well formed ------------------------------------------------
    if name == "node_schema_db.json":
        for key, entry in loaded.items():
            if key == "_readme":
                if not isinstance(entry, str):
                    problems.append(f"{name}: _readme should be a string")
                continue
            if not isinstance(entry, dict):
                problems.append(f"{name}: entry '{key}' is {type(entry).__name__}, not an object")
                continue
            for field in ("source", "inputs", "outputs"):
                if field not in entry:
                    problems.append(f"{name}: entry '{key}' has no '{field}' -- the _readme "
                                    f"requires source/inputs/outputs on every entry")
            if not isinstance(entry.get("inputs", {}), dict):
                problems.append(f"{name}: entry '{key}' 'inputs' is not an object")
    else:
        for key, entry in loaded.items():
            if not isinstance(entry, list) or not entry:
                problems.append(
                    f"{name}: '{key}' must be a non-empty LIST of {{url, destination}} dicts "
                    f"-- blocks.py stage_model() iterates it and indexes entry['url']. A "
                    f"dict here raises TypeError at build time.")
                continue
            for item in entry:
                if not isinstance(item, dict):
                    problems.append(f"{name}: '{key}' contains a non-dict entry: {item!r}")
                    continue
                for field in ("url", "destination"):
                    if field not in item:
                        problems.append(f"{name}: '{key}' has an item with no '{field}'")

    # --- duplicate copies differ, which is the actual hazard -----------------------
    if name == "node_schema_db.json":
        for key in sorted(set(dupes) & KNOWN_DUPLICATE_KEYS):
            bodies = entry_shape(text, key)
            if len(bodies) > 1 and len(set(bodies)) > 1:
                notes.append(
                    f"{name}: the {len(bodies)} copies of '{key}' DIFFER. json.load keeps the "
                    f"last one, so the linter validates against that copy -- check which is "
                    f"authoritative before trusting a SCHEMA_UNKNOWN_INPUT_KEY verdict for it.")

    return problems, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-git", action="store_true",
                        help="skip the comparison against git HEAD")
    parser.add_argument("-q", "--quiet", action="store_true", help="only print problems")
    args = parser.parse_args()

    all_problems = []
    for path in DB_FILES:
        problems, notes = check(path, use_git=not args.no_git)
        all_problems.extend(problems)
        if not args.quiet:
            for note in notes:
                print(f"[ok]   {note}")
        for problem in problems:
            print(f"[FAIL] {problem}")

    print()
    if all_problems:
        print(f"FAILED: {len(all_problems)} problem(s) in the graydient_builder databases.")
        return 1
    print("PASSED: both databases parse, keep their duplicate keys, and lost nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

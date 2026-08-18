---
name: preflight-plan
description: Run BEFORE writing any code for a new or speculative Graydient/ComfyUI workflow build. Separates the user's functional intent from their proposed technical vehicle, checks the vehicle against the catalog's Graveyard/schema/concept DBs for known blockers, and triggers the Intent-vs-Vehicle Pivot Protocol (KI-009) if one is found. Use this at the start of a build task, not after something has already failed — harvest-session is the post-build counterpart, this is the pre-build one.
---

### Preflight Plan — catch known blockers before spending quota, not after

This is the gate KI-009 (`comfyui-graydient-okf-catalog/catalog/KI-009-intent-vs-vehicle-pivot-protocol.md`)
describes, made runnable instead of prose-only. It exists because past sessions in this
project burned real quota building things that a five-second catalog check would have
flagged before any code was written (a Rust node, a guessed node signature that had
already been confirmed wrong once, a gated HF repo with no ungated mirror check).

## When to run this

At the start of any request to build, extend, or port a Graydient workflow — especially
one where the user proposes a specific implementation approach ("let's use a Rust crate
for...", "add a custom C++ node that...", "just hit this HTTP endpoint directly...").
Also worth running on vaguer requests ("make it faster", "add audio support") once you've
formed a mental plan for *how*, before writing the first line of `gen_*.py`.

Do NOT skip this because the request "seems simple." The costliest mistake in this
project's history (building the wrong audio-conditioning architecture entirely) came from
skipping a five-minute prior-art check, not from a hard technical problem.

## The process

### Step 1: Isolate intent from vehicle

State them separately, explicitly, before doing anything else:
- **Intent**: the functional outcome the user actually wants (e.g. "video motion synced
  to a reference audio clip's rhythm").
- **Vehicle**: the specific method proposed or implied to get there (e.g. "a Rust crate
  for fast audio analysis", "bolt audio encoding onto the plain i2v template", "write a
  brand-new custom node from scratch").

If the user only stated intent with no vehicle, form the vehicle yourself before
proceeding to Step 2 — "I'll build X using Y" is always the actual plan, even if Y was
implicit.

### Step 2: Check the vehicle against the catalog, not memory

Actually run these, don't rely on recalling what you already know:

```bash
python wf.py search "<key terms from the vehicle>"
python wf.py staging "<model/family name>"
```

Also check directly:
- `graydient_builder/node_schema_db.json` — is there already a verified (or
  known-wrong) signature for any node the vehicle would use?
- `comfyui-graydient-okf-catalog/catalog/KI-007-runtime-constraints-and-graveyard.md` —
  does the vehicle collide with a documented constraint (compiled dependencies, gated
  repos, filename-vs-URL ambiguity, package-identity collisions)?
- Existing `gen_*.py` scripts in the project root and official ComfyUI template repos
  (`Comfy-Org/workflow_templates` on GitHub) — has this problem already been solved by
  an official template or a prior script in this project? Search before writing a new
  node or architecture from scratch. This project has repeatedly built things by hand
  that already existed (a proven audio-loader pattern in `ComfyUI-HiggsV3Glue`, an
  official `ia2v` template with the correct audio-sync architecture) — check first.

### Step 3: If a blocker is found, run the 3-step Pivot Protocol (KI-009)

1. **Acknowledge & isolate the intent** — confirm you understood the goal correctly,
   separate from the vehicle that's about to be rejected.
2. **Explain the specific failure mode** — name the exact constraint (missing compiler
   toolchain, gated repo with no token, a node signature already confirmed wrong,
   filename-vs-URL ambiguity), not a vague "that won't work."
3. **Offer 1-2 concrete, pre-validated alternative routes** — cite the actual working
   pattern from the catalog/prior gen_*.py scripts, not a hypothetical.

Do this in chat, before writing code — this is a conversation checkpoint, not a silent
redirect.

### Step 4: If clean, proceed — but say what you checked

If no blocker is found, say so briefly ("checked the graveyard/schema DB for X, no
known blockers") and proceed. This isn't extra ceremony for its own sake — it's the
difference between "I didn't think of a problem" and "I checked and there isn't one
that we know of," which matters when something does go wrong later and you're trying to
figure out whether it was a known-and-missed risk or a genuinely new discovery.

## Relationship to harvest-session

This skill and `harvest-session` are the two ends of the same loop: `preflight-plan`
spends the catalog's accumulated knowledge before building; `harvest-session` deposits
new knowledge into it after a build is confirmed working. A session that runs
`preflight-plan` at the start and `harvest-session` at the end (once confirmed) is the
complete cycle this project's tooling is meant to support.

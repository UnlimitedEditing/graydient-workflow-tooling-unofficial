---
name: harvest-session
description: Harvest confirmed node signatures, Graydient runtime gotchas, and concept_mapping fixes from THIS session into the graydient_builder linter/catalog. Invoke on a session that just delivered a working build confirmed by a real Graydient job — never on a session that hasn't produced a real confirmed result yet, since unconfirmed sessions only add speculative noise to the catalog.
---

### Harvest Session — turn a hard-won debugging session into a permanent, checkable rule

## When to invoke

Only after the user confirms — in this same session, from a real Graydient job result,
not from a local `wf lint` pass alone — that a workflow now actually works. A session
still mid-struggle (guessing node keys, waiting on a job result, not yet confirmed) has
nothing to harvest yet: only hypotheses, not evidence. Running this skill on such a
session pollutes the catalog with unverified guesses that look as authoritative as
confirmed facts once written down — worse than not writing anything.

If the user asks "should we harvest this session" and it hasn't produced a confirmed
result yet, say so and decline, rather than harvesting speculatively.

## What counts as harvestable, and what doesn't

Only capture things this session **actually confirmed**, by one of:
- A real Graydient job log (success or a specific, diagnosed failure) pasted into the
  conversation.
- Reading real source code directly (ComfyUI core `comfy_extras/*.py`, a custom node
  repo's actual files) — not remembered, not assumed from a similar node's pattern.
- A `curl`/`gh api` check against a real URL/repo (e.g. confirming a mirror is ungated).

Do NOT harvest:
- Node signatures you're fairly confident about but never actually verified this
  session — leave those nodes unlisted; the linter's `SCHEMA_UNVERIFIED_NODE` (INFO,
  not ERROR) is the correct outcome for them, not a guessed entry.
- Architecture opinions or preferences that weren't validated against a real job
  (e.g. "single-pass is better" — only write this down if a real job's timing/quality
  actually confirmed it, with the numbers).
- Anything from a different, unconfirmed line of investigation still open at end of
  session.

## What to update, and how

Read `D:\tripostl\graydient_builder\node_schema_db.json`'s own `_readme` field and the
existing entries first, to match tone/format — every entry has a `source`, `inputs`
(exact keys, with type/shape notes for anything non-obvious like dotted Autogrow
sub-fields), `outputs`, and a `note` explaining *why* it's recorded (what bug it
prevents, what the confirmation evidence was). Follow this pattern exactly.

1. **New/wrong node signatures** (`graydient_builder/node_schema_db.json`): for every
   ComfyUI node class_type whose real input/output keys got confirmed this session
   (including negatively — "we guessed X, source says Y"), add or correct an entry.
   Before writing an entry from memory of "what we fixed," re-check the actual
   evidence in this session's transcript rather than trusting recollection — a prior
   harvest in this project got a node's schema wrong on the first pass by doing
   exactly that (recording only the old broken guess-fields instead of the full real
   signature), and the linter itself caught it by then flagging the correct usage as
   an error. Re-run `python wf.py lint <the gen_*.py just confirmed working>` after
   editing the schema DB — it must come back 0 errors, since the workflow that
   generated it is now known-good; any error means the schema entry is wrong, not the
   workflow.

2. **Runtime/platform gotchas** (`comfyui-graydient-okf-catalog/catalog/KI-007-*.md`):
   append a new numbered section (`## <N>. <Title>`) for anything about Graydient's
   own behavior (field resolution ambiguity, staging quirks, package-identity
   collisions, gated repos, etc.) discovered this session — follow the existing
   sections' `**Failure Mode**:` / `**The Rule**:` (or `**The Reconstruction**:`,
   `**Reference implementation**:`) structure. If the linter has a targeted rule that
   could now catch this class of mistake (see `graydient_builder/linter.py`'s
   `_check_anti_patterns`), add it there too — one rule per specific discovered
   gotcha, not a generic heuristic.

3. **Model file / concept_mapping fixes** (`graydient_builder/concept_db.json` +
   `comfyui-graydient-okf-catalog/catalog/KI-008-*.md`): if this session found a
   correct model URL/destination, an ungated mirror for a gated repo, or discovered
   an existing catalog entry was stale/wrong (check — a prior harvest left one
   pointing at the wrong model family entirely), fix it in both files together, they
   must stay in sync. Verify every URL you write with a real `curl -sI` (302/200,
   not 401) before committing it — don't copy from the workflow file without
   re-checking, since the workflow file itself might have been storing a since-moved
   URL.

4. **Linter false positives/negatives** (`graydient_builder/linter.py`): if a lint
   rule blocked something this session confirmed actually works (e.g. a banned-pip
   pattern that's too broad), or missed something that should have been caught,
   fix the rule and record *why* in a code comment with the confirming evidence
   (which real job, which package) — not just fix it silently.

## After harvesting

Run `python wf.py lint <the confirmed-working gen_*.py>` one final time. It must
return 0 errors. If it doesn't, something in the harvest is wrong — fix the harvest,
never loosen a check just to make a known-good workflow pass.

Report back concisely: what was added/fixed in each of the four files, and confirm
the final lint pass. Don't pad this with restating the whole session's history — the
catalog files themselves are the durable record now, the chat summary just needs to
confirm they're accurate and consistent.

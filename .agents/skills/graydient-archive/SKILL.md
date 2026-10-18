---
name: graydient-archive
description: Manage Graydient workflows in the community archive web UI (the page behind Telegram `/archive`) with the `graydient archive` CLI — deploy a gen_*.py backup JSON (restore or create), set description/cover image, check flags, and prepare a workflow for going public. Use after a gen_*.py writes a GraydientWorkflow-*.json that needs deploying, or when asked to edit a workflow's public-facing details. Not for submitting renders (that is `graydient render` / `q`).
---

# Graydient archive (deploy + describe workflows)

The archive UI has no API. `graydient archive …` (in `D:\ForgeExpress\cli`, run as
`node D:\ForgeExpress\cli\dist\index.js archive …` or `graydient archive …` if linked) drives it with
Playwright. The login (graydient.ai cookies only) is kept in `~/.graydient/archive-session.json`.

## 0. Login (the one manual step)

Every command fails with "not logged in" when the session is missing or expired (sessions do NOT
last overnight). When that happens:

1. Ask Jacob: "Send `/archive` to the Graydient bot and paste me the magic link."
2. `graydient archive login "<link>"`. The link is a credential: do not echo it back, log it, or save it anywhere. It may be single-use.
3. `graydient archive status` confirms.

## 1. Commands

| Task | Command |
|---|---|
| List my workflows | `archive list [--json]` (ids look like `WF7vGQ0X`; **names are not unique** — prefer ids) |
| Read details | `archive show <id>` |
| Deploy onto an existing workflow | `archive restore <id> <GraydientWorkflow-*.json> --fix` (REPLACES its graph, fields and models) |
| Create a new workflow | `archive new <json> --name <name>` (makes a stub, restores, names, fixes flags; private) |
| Name / description / cover | `archive meta <id> --name … --description-file d.txt --image cover.jpg` |
| Read another tab | `archive dump <id> --tab Fields` (also Models, Logs, Use, Details) |

Always read the output: `restore` prints flags that did not carry over.

## 2. Rules learned the hard way

- **A restore does not reliably carry feature flags or the description.** It left `supports_txt2wav` off,
  `install_detected_nodes` on (must be OFF for video/diffusion workflows) and the description blank. Use `--fix`
  and read the report; never assume the JSON's values landed.
- **Never click New Workflow casually.** It instantly creates a stub on the account. Use `archive new` deliberately, and tell Jacob what you created.
- **JSON has no slug or name.** A backup restores onto a workflow you choose; it cannot tell you which one. Confirm the target id with Jacob when the filename does not obviously match (e.g. `ltx25-sfx-v3.json` → `sfx-ltx25`, but `joyaiecho-t2voice` had no obvious target).
- **Restoring overwrites.** Check `archive show` first (name, version) so you do not replace the wrong workflow.
- **One render at a time per account.** Test runs and cover-image renders must be sequential.
- **First run of a freshly restored workflow can take up to ~2000 s.** Use `graydient render … --timeout 45`; never a short timeout.
- **Fields tab = ground truth for field mappings.** `archive dump <id> --tab Fields` returns each mapping (field -> node, default, min/max, help text) and the dropdown of platform fields the UI accepts: `prompt_positive`, `prompt_negative` (NOT `negative_prompt`), `raw_prompt`, `seed`, `steps`, `guidance`, `length`, `fps`, `width`, `height`, `strength`, `slot1`-`slot8`, `image1-8`, `audio1-8`, `video1-8`, `init_image_url/filename`, `init_audio_url/filename`, `init_video_url/filename`, `mask_image_url/filename`, `sampler`, `scheduler`, `vae`, `num_images`, `model_family` and a few more. Check a gen_*.py's `local_field` names against this list before restoring. Note: many older scripts use `negative_prompt`; whether the backend aliases it is unconfirmed.
- Check `archive show` for `public:` before touching a workflow; Jacob may have already published or edited it by hand. Do not overwrite his edits (restore does not touch name/description unless you pass `--fix` on an empty description).

- **A restore onto a PUBLIC workflow un-publishes it and drops its cover** (iris3b, 2026-10-13: `public: null`, `example image: false` after restore, even with "Flag differences: none"). After any restore of a live workflow: `archive show`, re-upload the cover (`archive meta <id> --image ...`), run a real test render through the slug on the new version, then re-publish. Graydient says "Workflow not eligible to go public yet" until then; `meta --public` fails with a locator timeout on `is_public`. Replace a public workflow only when Jacob said to; otherwise restore onto a private copy. Details: KI-007 section 30.
- **`archive meta --description-file` can overwrite a non-empty description, but set it in its own call**: combined with `--image` in one call (iris3b-studio, 2026-10-13) the description did NOT change (`archive show` still had the restore's text); the same flag alone a moment later did. Always `archive show` after `meta` to confirm what landed.
- **No CLI delete.** Deleting = the Basics page `del-workflow` link + accepting a browser `confirm()`; do it only on Jacob's explicit say-so, and assert the workflow name first. The first attempt may look like a no-op; re-list after a few seconds.
- **Image-input workflows via CLI**: `/image1:URL1` in the prompt + `--placeholder URL1=<https url>` (a prior render's public S3 URL works; no upload host needed).

## 3. Going public: criteria (all three) and permission

A workflow can only go public when:

1. **It works** — one successful real run. Run it via the CLI and check the output exists and is sensible (duration/size). You cannot judge audio/visual quality: say so and ask Jacob to check.
2. **It has a description** — human-friendly, minimal jargon, brief: what it does, what controls it has, what it is made of. Do not claim behaviour that has not been tested (e.g. "same seed gives the same voice" was written for joyaiecho-t2voice and turned out unsupported).
3. **It has a picture** — a frame from its own output where that fits, otherwise a krea2 cover: a bold, limited-palette, high-contrast poster built on a moniker of the workflow title, with stylised text (example: audio2animate-ltx25 = audio streaming in from the sides onto floating lips, a film reel spooling from the mouth). Generate with the Graydient `krea2` skill style prompt (`/workflow /run:krea2 /size:1024x1024 …`, single paragraph per `C:\Users\jacob\Downloads\krea2-v10.txt`), or use an image Jacob supplies.

**Publishing is Jacob's decision.** `meta --public` additionally requires `--confirm-public`, which you may only pass after Jacob explicitly says to publish that workflow. Meeting the criteria is not permission.

## 4. Typical deploy loop

```
python gen_x.py                                   # writes GraydientWorkflow-x-vN.json (linter runs)
graydient archive show <id>                       # confirm target
graydient archive restore <id> GraydientWorkflow-x-vN.json --fix
graydient render "<prompt> /run:<name> /seed:42" --out test_out/ --timeout 45
# then description + cover via `archive meta`, then ask Jacob about publishing
```

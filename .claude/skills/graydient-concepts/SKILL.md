---
name: graydient-concepts
description: Install and manage Graydient Concepts (LoRAs etc.) in the community web UI (the page behind Telegram `/concept /edit`) with the `graydient archive concept` CLI. Use when asked to add a LoRA/concept from Civitai or Hugging Face to Graydient, e.g. "install this concept for H3". Covers hosting the weights on Hugging Face, filling the form, and checking the concept works. Not for workflows (use graydient-archive) or for submitting renders.
---

# Graydient concepts (install a LoRA)

A Concept = a name + prompt token + a **public Hugging Face direct URL** to a weights file + model family. Graydient
downloads it to its servers; users then write `<concept-name:0.7>` in a prompt. There is no API, so
`graydient archive concept …` (bundled in this repo's `cli/`; build once with `cd cli && npm ci && npm run build`, then `node cli/dist/index.js archive concept …`)
drives the form with Playwright. It shares the login in `~/.graydient/archive-session.json` with `graydient-archive`.

**Missing a dependency (Node, browser, `hf`, CLI build, logins)?** Run `python setup_wizard.py --check` from the repo root, then `python setup_wizard.py`.

## 0. Login (the one manual step)

If any command says "not logged in": ask the user to send **`/concept /edit`** (or `/archive`) to the Graydient bot and
paste the magic link, then `graydient archive login "<link>"`. The link is a credential: never echo, log or save it. It
may be single-use. A `/concept /edit` link lands on `/concepts/edit`; login accepts that.

## 1. Install workflow

1. **Read the source page** (Civitai blocks WebFetch with 403: use the built-in browser, `get_page_text`). Note: base model
   (-> model family), type (LORA), file name + size, trigger words, recommended strength, license, NSFW flag.
2. **Check the model family exists** in the form: Anima, Chroma, Cosmos, Flux, Flux2, H3, Hidream, Huny, Ideogram, Krea2,
   Ltx2, Lumina, SD15, SDXL, Qwen, Qwen2, Wan, Zimage. Families cannot be mixed.
3. **Host the file on Hugging Face** (never hotlink Civitai: files get deleted or need login). `hf auth whoami` shows the
   logged-in account. Upload to a PUBLIC repo, e.g. `hf upload <user>/<repo> <local file> <file>` and use
   `https://huggingface.co/<user>/<repo>/resolve/main/<file>`.
   **Both the download and the public upload need the user's explicit yes (state filename, source, size, destination repo).**
   Mention the licence if it restricts redistribution.
4. **Create the concept:**
   ```
   graydient archive concept new --name <unique-name> --token <token> --url <HF resolve URL> --family H3 --type lora \
     --description "<creator, what it does, recommended strength>" --info-url <civitai page> [--example-url <img>] \
     [--tags video,effects] [--nsfw]
   ```
   This SAVES for real (installs on the account). Name must be unique: add month+year if taken. If the source gives no
   trigger word, still supply a short token.
5. **Wait**: ~3-5 min install, then ~3-5 more min after "Concept Saved successfully" to replicate across servers.
6. **Verify** with `graydient concepts list --search <name>` (public API list) and a real render using `<name:1.0>` at the
   creator's strength. You cannot judge visual quality: ask the user to look.

## 2. Notes

- Commands: `archive concept list` (dumps My Concepts), `new`, `edit <name|id> [--field …]` (only passed fields change; `--tags`
  REPLACES the tag set), `delete <name|id> --confirm-delete` (permanent: only when the user asks; the delete confirm step is untested live).
- **Sharing needs a description and a picture** (like workflows). Description is a form field. The picture is the *Example Image URL*,
  a URL not an upload, so host it publicly (a frame from the concept's own output, or a splash art rendered with the LoRA, on the
  same HF repo) and `edit --example-url`. The user prefers a real sample of the concept or LoRA-generated art. A civitai `.webm` URL
  was accepted by the field, but whether the public page plays it is unverified, and Civitai CDN links can rot.
- No public/share toggle was found on the concepts page (only Enabled); ask the user where publishing lives before assuming.
- Form fields (mapped 2026-10-08): name, token, url, description, info_url, example_url, Enabled, NSFW, tags[], model_family, type
  (lora / style=Base Model / inversion / inpainting / instruct).
- First live install (restore-enhance-improve, H3, 2026-10-08): the Enabled box did NOT persist on the first save (concept listed
  DISABLED); `new` now re-opens it and saves again with Enabled checked. The "EDIT" button text is CSS-uppercased: select by
  `[phx-click^="edit-concept-"]`, not by text. Civitai download URLs return 401 without a login: the user downloads the file by hand
  into a local folder, then the agent does the HF upload (`hf upload`, to the user's own account) and `concept new`.
- Weight in prompts: 0-2 after a colon, `<name:0.3>`; default 0.7 when omitted.
- One render at a time per account; first run of a new concept can be slow.
- Tag list is site-defined (e.g. `-video`, `effects`, `edits`, `realistic`); unknown tags are rejected by the CLI.

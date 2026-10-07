# graydient-cli

A command-line client for [Graydient.ai](https://graydient.ai) — render images/video, chat with personas, and manage jobs from any terminal, script, or coding agent.

It's a small, dependency-light Node package (just [Commander](https://github.com/tj/commander.js)) factored out of the [ForgeExpress](../) Electron app, so the same request/streaming logic that powers the GUI is available headlessly.

> [!NOTE]
> This CLI talks to Graydient's hosted API. You'll need a Graydient account and API key — see [Auth](#auth) below.

## Install

```sh
cd cli
npm install
npm run build
npm link      # puts `graydient` on PATH globally
```

Re-run `npm run build` after pulling changes to this folder. `npm link` only needs to be run once (or again if you delete/recreate `node_modules`).

Requires Node.js 22+.

## Auth

Get an API key from https://app.graydient.ai/dashboard/token/, then either:

```sh
graydient auth login --key <your-key>
```

which stores it in `~/.graydient/config.json`, or, for scripts/CI/agents, skip storage entirely:

```sh
export GRAYDIENT_API_KEY=<your-key>
```

An environment variable always takes priority over a stored key.

`graydient auth status` shows the masked key and does a live check against the API. `graydient auth logout` deletes the stored key.

> [!IMPORTANT]
> This is a **separate credential store from the ForgeExpress app**. The app uses Electron's OS-level `safeStorage`, which a plain Node process can't reach, so the CLI keeps its own config file instead (plaintext, `chmod 600`).

## Quick start

```sh
graydient auth login --key <your-key>
graydient workflows list --search sdxl
graydient render "a red fox in a snowy forest" --workflow sdxl --out ./fox.png
```

## Commands

| Command | What it does |
|---|---|
| `graydient auth login\|status\|logout` | manage the stored API key |
| `graydient workflows list [--search q]` | list available workflows |
| `graydient workflows show <slug>` | full workflow detail, incl. field mappings |
| `graydient concepts list [--model-family f] [--search q]` | list LoRA/concept models |
| `graydient skills list` / `show <slug>` | list/inspect skills |
| `graydient render "<prompt>" [options]` | submit a render, wait for it, optionally download it |
| `graydient q "<telegram command>"` (alias `quick`) | same as `render`, but forwards raw Telegram/PirateDiffusion syntax unparsed |
| `graydient skill-run "<prompt>" [--skill slug]` | auto-select (or specify) a skill, then render |
| `graydient status <renderHash>` | check on a previously submitted render |
| `graydient download <renderHash> --out path` | pull down a render's media without re-rendering |
| `graydient chat <persona> "<prompt>"` | one-shot message to a chat persona (e.g. `polly`) |
| `graydient upload <file> [--expiry 1h\|12h\|24h\|72h]` | upload a local file to a temporary host and print its URL |
| `graydient config get` / `set-base-url <url>` | inspect/override the API base URL |
| `graydient ui` (alias `kanban`) | launch the RenderFlow Kanban web workspace with pipeline chaining, Omni-Russ animation, and remote Cloudflare tunnel |

Add `--json` to any read/render command for machine-readable output. Run `graydient <command> --help` for the full flag list on any command.

### `render` options

| Flag | Meaning |
|---|---|
| `--workflow <slug>` | workflow to use (same as `/run:slug` in the prompt) |
| `--negative <text>` | negative prompt (same as `[text]` in the prompt) |
| `--init-image <url-or-path>` | source image — an `http(s)` URL or a local file (auto-uploaded for you) |
| `--init-video <url-or-path>` | source video, for vid2vid/lipsync workflows |
| `--init-audio <url-or-path>` | source audio |
| `--placeholder <key=url-or-path>` | extra reference media for multi-image workflows (repeatable) |
| `--out <path>` | download the result to this file, or to this directory for multi-output renders |
| `--timeout <minutes>` | give up waiting after this long (default 20) |
| `--json` | emit a single JSON result object |

## Output contract

**stdout always carries exactly one thing** — a human-readable summary, or with `--json` a single JSON object. All progress/log lines (`render_queued`, `rendering_started`, etc.) go to **stderr**, in every mode. That means scripts and agents can always do:

```sh
graydient render "a red fox in a snowy forest" --workflow sdxl --json | jq -r '.media[0].url'
```

without progress noise leaking into the parsed output.

## Local files as render input

Graydient's own render API only accepts URLs for `init_image`/`init_audio`/`init_video`, not local file uploads. Point any `--init-*` or `--placeholder` flag at a local path and the CLI uploads it to a temporary expiring host for you and substitutes the resulting URL automatically — no extra step needed. Use `graydient upload <file>` directly if you just want a shareable URL without also submitting a render.

## The prompt mini-language

`render`'s `<prompt>` argument accepts the same syntax as the ForgeExpress input box:

- `/run:slug` — pick a workflow (equivalent to `--workflow`)
- `/key:value` — extra render options (e.g. `/images:2`, `/seed:123`)
- `[negative text]` — negative prompt (equivalent to `--negative`)
- `<concept:weight>` — LoRA/concept tokens

```sh
graydient render "a cyberpunk alley /run:sdxl /images:2 [blurry, low quality]" --out ./out/
```

`render`'s parser only understands the four constructs above, and silently drops anything else (bare flags like `/nofix`, `/karras`, `#recipe` hashtags, `/compose` zones, etc.). For the full native syntax — the same nomenclature used by Graydient's Telegram bot, documented at https://graydient.ai/pirate-diffusion-guide/ — use `graydient q` instead:

```sh
graydient q "/wf /run:video-wan22 cinematic low angle shot of a fox running through snow /length:97 /fps:24" --out ./out/fox.mp4
```

`q` (alias `quick`) sends the command string straight through in the `prompt` field with no CLI-side parsing — Graydient's backend parses it exactly as it would Telegram/web UI input. See [`docs/telegram-prompt-syntax.md`](docs/telegram-prompt-syntax.md) for a syntax catalog to pull real examples from. `render`/`skill-run` are unchanged and still the right choice when you want this CLI's own `--workflow`/`--negative`/`--init-*` flags instead of raw command strings.

## For coding agents

- **Without `--out`, nothing is saved to disk.** `render`/`skill-run` return media as a remote URL by default. If you need a local file to open/inspect/attach, pass `--out <path>`.
- **`status: incomplete` means the CLI stopped waiting, not that the render failed.** Video renders especially can finish on the backend after the CLI's retry window closes. Re-run the command the output gives you (`graydient status <renderHash> --json`) after waiting a bit — it re-queries live state and costs nothing.
- **Find real workflow slugs before guessing.** Slugs like `sdxl` or `video-wan22` change over time — run `graydient workflows list --search <keyword>` to confirm the current slug rather than reusing one from an old example.
- **`--json` output is the contract to parse**, not the human-readable text. Every render/skill-run/status result includes `renderHash`; incomplete results include a literal `nextCommand` string you can run as-is.
- **For prompt-quality and pipeline-reliability tips** (strength/denoising, multi-image `placeholders` vs `init_image`, video quirks, workflow-slug churn, concurrency limits), see [`docs/render-quality-notes.md`](docs/render-quality-notes.md) before wiring this CLI into anything automated.
- **For real prompt syntax to imitate**, see [`docs/telegram-prompt-syntax.md`](docs/telegram-prompt-syntax.md) and send it unparsed via `graydient q`.

## Documentation

- [`docs/render-quality-notes.md`](docs/render-quality-notes.md) — prompt/pipeline reliability notes
- [`docs/telegram-prompt-syntax.md`](docs/telegram-prompt-syntax.md) — full Telegram/PirateDiffusion syntax catalog
- [`docs/graydient-api-support-notes.md`](docs/graydient-api-support-notes.md) — API quirks and support-channel notes

## RenderFlow Kanban Workspace & Remote Tunnel

Launch the local web UI:

```sh
graydient ui
# or: npm run ui
# with remote access tunnel: graydient ui --tunnel
# with custom port and browser auto-launch: graydient ui --port 7860 --open
```

### Features:
- **Kanban Pipeline**: Track and manage renders across 6 columns (`Prompt Backlog`, `Render Queue`, `Rendering`, `Image Review`, `Animating`, `Finished Library`).
- **Chained Pipelines**: Automatically feed generated images into **Omni-Russ** (`omni-russ`) to produce animated videos with custom soundscapes and camera motions.
- **1-Click Animate**: Any image in the Review or Library columns can be turned into an Omni-Russ animation with 1 click.
- **Raw Telegram Syntax Compatibility**: Paste `/wf /run:...`, `/render...`, and `#recipes` directly.
- **Batch Queueing**: Paste multiple prompts at once to queue or backlog.
- **Collate & Video Reel Compilation (FFmpeg)**: Select finished animations and combine them into a single continuous montage MP4 reel with title/prompt sidecars.
- **ZIP Export**: Export media files bundled with metadata `.txt` sidecars and `manifest.json`.
- **Prompt Library & Content Descriptions**: Skim clean, human-readable content descriptions (technical flags stripped) for quick copy-pasting to social media or video captions.
- **Remote Access Tunnel (Cloudflare)**: 1-click Cloudflare tunnel with live URL and on-screen QR Code to monitor and manage your render queue from your phone anywhere.

## Notes

- `render`/`skill-run` default to a 20-minute wait (`--timeout <minutes>` to change) before giving up and printing the `render_hash` so you can check on it later with `graydient status`.
- `--out` accepts either a specific file path (single-output renders) or a directory (auto-named files, collision-safe) for multi-output renders.


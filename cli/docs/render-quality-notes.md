# Render quality & pipeline reliability notes

Distilled from `docs/graydient-api-support-notes.md` (Graydient's own support channel) into
actionable rules — written for a coding agent that is prompting `graydient render`/`skill-run`
directly, or wiring this CLI into an automated pipeline. Skip the source doc unless you need the
original quotes; this is the "so what do I actually do" version.

## Getting a good render, not just *a* render

- **Be specific and visual, not vague.** Short, generic prompts ("a woman in a red dress") lean
  entirely on the model's defaults. Long, concrete prompts with explicit visual keywords steer it
  — each keyword nudges the output in one direction. If you don't know what a *good* prompt for a
  given model looks like, prefer `graydient skill-run` over raw `render`: skills carry their own
  prompt-enhancing instructions and pick sane default settings (size, guidance, steps) for the
  model they target, instead of relying on you to guess them.
- **Pin your parameters for anything you intend to reproduce or run repeatedly.** Graydient fills
  in random values for anything you don't specify (`/seed`, `/sampler`, `/guidance`, `/steps`,
  `/size`). Fine for one-off exploration, bad for a pipeline — two runs of the "same" prompt will
  differ. Explicitly set `/seed:<n>` plus whatever else the workflow exposes once you've found
  settings that work.
- **Negative prompts go in square brackets inside the prompt string** — `graydient render`'s
  `--negative` flag is sugar for exactly that, use whichever is more convenient.
- **img2img/vid2vid "strength" (denoising strength) is the single most important knob** and the
  easiest to get wrong: too low and the model barely touches the source image (asking for "hell"
  on a photo of snowy mountains at strength 0.2 will not visibly change it); too high and you lose
  the source entirely. There's no universal right value — it varies per prompt and per source
  image. If a render "did nothing" or "changed too much," adjust strength before touching anything
  else.
- **Check a workflow's docs before you rely on it.** `graydient workflows show <slug>` returns the
  field mappings and defaults; the Telegram-equivalent `/wf /show:<slug>` also shows average
  render time. Cheaper models/workflows that are "good enough" often render much faster — worth
  checking before defaulting to the heaviest model available.
- **New / less-optimized models often want fewer steps, not more.** E.g. the `ernie` workflow
  defaults to `/steps:20` but support staff recommend trying `/steps:10` first — higher isn't
  always better, especially on newer models that aren't tuned yet.
- **When you're not sure a prompt is right, verify it cheaply before wiring it into a pipeline.**
  Support staff repeatedly point people at trying the exact same command on Telegram/the web UI
  first — same command syntax works in both places — specifically to remove doubt about whether a
  failure is the prompt or the plumbing before you debug your integration code.

## Multi-image / reference workflows

- **`init_image` is the "reply target"** — the single primary input image (or video, via
  `init_video`), equivalent to replying to a photo on Telegram. It is *not* how you supply
  additional reference images for a workflow that takes several.
- **Extra reference images go through the `placeholders` mechanism**, referenced in the prompt as
  `/image1:URL1 /image2:URL2 ...` with a `placeholders: {"URL1": "https://...", "URL2": "..."}`
  object (the CLI's `--placeholder key=url` flag maps directly to this). Passing a second image as
  `init_image` when the workflow wants `image1`/`image2` is the most common cause of "unhandled
  error occurred" for multi-image workflows.
- **Refer to reference images by name in the prompt text**, not by implicit description — write
  "image1 is wearing a black sweater, image2 is standing behind them" rather than "the man... the
  woman...". The model does not reliably infer which image is which subject on its own.
- **Combining more than 2 reference subjects degrades identity fidelity.** Workflows built for
  2-image blending (`blend2-*`, `deepfake-z`, `pose2people`, etc.) will either ignore a third image
  or dilute all identities when forced. If a pipeline needs 3+ subjects composited, doing it as
  sequential 2-image faceswap/blend passes has worked better in practice than one 3-image call.

## Video specifics

- Video renders take meaningfully longer than images (documented up to ~3 minutes server-side, vs
  seconds-to-tens-of-seconds for images) and their media can be recorded as "done" slightly before
  it's actually downloadable — this CLI already retries for a couple of minutes after
  `rendering_done` to absorb that lag (see `resolveFinalMedia` in `src/client.ts`); don't add your
  own polling loop on top, `graydient status <hash>` is enough if you do need to check later.
- Resolution and length matter more for video than image workflows: very small (below ~320x320) or
  very large sizes both cause problems; a commonly cited social-friendly sweet spot is around
  512x640 (or the equivalent landscape size). `/length:<frames>` and `/fps:<n>` control duration —
  push both up together deliberately, not by accident.
- If a video render is stuck well past the ~3 minute mark, the fix is usually to lower settings
  (resolution, steps, length) or strip special characters/excess whitespace from the prompt, not to
  wait longer.
- "Image-to-video" workflows (`animate-*`) need `init_image`; "video-to-video" (`vid2vid`,
  faceswap-style `wanimate-*`) need `init_video`, sometimes combined with an `image1` reference
  face via `placeholders`. Check `workflows show <slug>` — the field name isn't consistent across
  the video workflow families.

## Configuring this CLI as part of a pipeline

- **Workflow slugs are not stable long-term.** Workflows get renamed, replaced, or removed
  (support channel has multiple reports of a previously-working slug suddenly 400ing as
  `unknown \`/run:<slug>\``). A pipeline config that hardcodes a slug should periodically
  re-validate it against `graydient workflows list --search <keyword>` rather than assuming it
  still exists; fail loudly and specifically on an "unknown workflow" error rather than retrying
  it blindly.
- **Respect the concurrency limit.** Personal/Pro API plans are limited to one simultaneous render;
  firing many parallel `graydient render` calls from a pipeline will queue (not fail) but won't
  actually run in parallel — serialize pipeline stages accordingly, or budget for a Business-tier
  plan if true concurrency is required.
- **Treat `status: incomplete` as "still might finish," never as a hard failure**, and don't retry
  by resubmitting the same render — resubmitting duplicates cost and output. Re-check with the
  `nextCommand` this CLI prints (`graydient status <hash> --json`) after a delay instead.
- **A render that never completes and never errors is rare but real** (~5 minute watchdog is a
  reasonable timeout to treat something as truly dead, per the support channel's own internal
  convention, given renders cap out around 3 minutes server-side). If a pipeline needs a hard
  cutoff beyond this CLI's own `--timeout`, model it on that: 3 min max render + buffer, not
  minutes-long polling.
- **Local file input always needs to be a real, direct, publicly-reachable URL** — Graydient has no
  upload endpoint of its own, can't dereference an HTML page that merely embeds an image, and a
  URL-encoded URL will fail (`init_image` etc. want a raw URL, not percent-encoded). This CLI's
  `resolveMediaInput`/`--init-image` local-path handling already deals with this by uploading to a
  temporary host — prefer that over hand-rolling your own upload step.

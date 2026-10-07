# Telegram/PirateDiffusion command syntax reference

This is a catalog of Graydient's native "Telegram-speak" slash-command syntax — the same
nomenclature used across hundreds of thousands of real renders on their Telegram bot and web UI.
Distilled from https://graydient.ai/pirate-diffusion-guide/ (fetch that page directly for the full
prose explanations; this file is the quick-reference version).

**Why this exists:** don't invent prompt syntax from scratch, and don't route everything through
this CLI's own reduced mini-language parser (`--workflow`/`--negative`/`/run:`/`/key:value` — see
`parseTelegramPrompt` in `src/client.ts`, which only understands a subset and silently drops
anything it doesn't recognize). Use `graydient q "<telegram command>"` (alias `quick`) to send any
of the syntax below completely unparsed — Graydient's backend already knows how to read it, the
same parser it uses for Telegram and the web UI. Reach for `render`/`skill-run` instead only when
you specifically want this CLI's own flag-based ergonomics.

## Core structure

- `/render <description>` — direct image generation, full manual parameter control. Bare `/render`
  with no workflow selection uses SD1.5/SDXL-family models.
- `/wf /run:<slug>` or `/workflow /run:<slug>` — run a named workflow (video, animation, audio,
  specialized editing). Equivalent forms.
- `//<description>` — Skills shorthand: an LLM picks the workflow and enhances the prompt for you.
  This CLI's `skill-run` command hits the same underlying skills API directly.

## Images

```
/render a close-up photo of a gorilla jogging in the park
/render /adetailer a close-up photo of a gorilla jogging in the park      # auto-fix hands/faces
/render /translate un perro muy guapo                                     # non-English input
/render ((high quality, masterpiece, masterwork)) [low resolution, worst quality, blurry] Takoyaki on a plate
/render a dog <realvis4-xl>                                                # base model/LoRA trigger
/render /blend:chicken:1 /blend:zelda:-0.4 a magical scene                 # blend multiple concepts
```

- Positive emphasis: `(word)` ≈ 1.1×, stacks — `(((word)))` ≈ 1.33×, `((((word))))` ≈ 1.46×. Too
  many brackets causes visible glitching/pixelation — 2-3 deep is usually the practical ceiling.
- Negative emphasis: `[word]` reduces, stacks the same way. Applied inline in the same string —
  there's no separate "negative field" over the raw API; the CLI's `--negative` flag is just sugar
  that wraps text in `[...]` for you.
- Negative *inversions* (embeddings trained specifically on bad output) go in double brackets as a
  quality boost, e.g. `[[<verybad-negative>]]`.
- Concepts/LoRAs: written as `<trigger_word>`, optionally weighted `<trigger_word:0.8>`. These are
  full checkpoints or LoRAs, distinct from workflows — pull real trigger names from
  `graydient concepts list --search <term>`, don't guess them.
- `/parser:new (blue cat:0.1) (green bird:0.2) [(blue cat:2), (red dog:0.1)]` — explicit numeric
  weights (0-2 range) instead of bracket-stacking; negatives go inside `[...]` in this mode.
- `/lpw` — Long Prompt Weights, extends past the default ~77 token limit. Requires guidance ≤ 7;
  incompatible with heavy bracketing, LoRAs, or `/sampler:lcm`.

## Common parameters (image)

```
/render /size:768x768 ...          # explicit resolution
/render /portrait ... | /landscape ... | /tall ... | /wide ...    # aspect shortcuts
/render /steps:25 ...              # iteration count (also: wayless=15, less=25, more=100, waymore=200)
/render /guidance:7 ...            # prompt adherence, 7 is a typical default
/render /seed:123456 ...           # reproducibility — always pin this for a pipeline
/render /sampler:dpm2m /karras ... # sampler + Karras scheduling
/render /sampler:lcm /guidance:1.5 /steps:6 /nofix ...   # fast/cheap mode
/render /vae:GraydientPlatformAPI__bright-vae-xl ...
/render /clipskip:2 ...
/render /nofix ...                 # disable SDXL refiner pass
/render ... /vass                  # SDXL HDR mode
/render /freeu:1.1,1.2,0.9,0.2 ...  # experimental detail tuning (4 values, 0-2 range each)
/render /format:png ...
/render ... /project:xyz           # tag into a project folder
```

Recipes (`#quick`, `#nfix`, `#eggs`, `#boost`, `#everythingbad`, `#sdxlreal`, ...) are
preset parameter bundles appended as a hashtag — `/render a cool dog #quick`. List them with
`/recipes` on Telegram; there's no CLI equivalent yet, so these only work through `graydient q`.

## Video

```
/wf /run:video-wan22 cinematic low angle video of ... /length:120
/wf /run:video-ltx23 camera slowly pans across ... /length:97
/wf /run:animate-wan22 a woman makes silly faces towards the camera    # image-to-video, needs init_image
/wf /run:animate-ltx23 camera video slightly changes angle ...
/wf /run:extend-wan22 he turns around and runs into the building /length:120   # extend existing video
/wf /run:video-upscale
/wf /run:mmaudio funny music and clown voices, burger eating sounds     # add audio track to a video
```

- `/length:<n>` — frame count. Documented "safe" values: 89, 97, 105, 113, 121, 137, 153, 185, 201,
  225, 241, 257. Off-list values are more likely to misbehave.
- `/fps:<n>` — 24 is the general recommendation, 18 for turbo/fast models, 30+ for realism-focused
  output.
- Model families in the wild: Wan (2.1/2.2), LTX, HunYuan, SkyReels — each has its own quirks and
  optimal size/step ranges; check `graydient workflows show <slug>` before assuming settings that
  worked for one family carry over to another.

## Multi-image / regional composition

```
/compose /size:2000x700 /left:The tower of Thai food /center:Jungles of Thailand, tropical rainforest [blurry] /right:Castle made of stone, castle in the jungle
/compose /size:1000x2000 /top:Lion roaring /center:Apartment building /bottom:Dirty city streets [[ugly]] [[blurry]] /images:1 /guidance:7
```

- Named zones: `background`, `top`, `topleft`, `topcenter`, `topright`, `left`, `center`, `right`,
  `bottom`, `bottomleft`, `bottomcenter`, `bottomright`. Fill with `/top:`, `/center:`, etc.
- For reference-image workflows (not `/compose`): `init_image`/`init_video` is the single primary
  "reply target"; extra reference images are `/image1:URL1 /image2:URL2 ...` in the text paired
  with a `placeholders` map — the CLI's `--placeholder key=url` flag on `render`/`q` maps directly
  onto this. **Refer to subjects by name in the prompt** ("image1 is wearing a black sweater,
  image2 is standing behind them") — the model does not reliably infer which image is which
  subject from natural-language pronouns alone.

## Editing / manipulation (reply-style commands — need init_image)

```
/edit add fireworks to the sky
/edit /workflow /run:edit-kontext-flux add fireworks to the sky
/highdef                                    # 2x upscale
/facelift | /facelift /photo | /facelift /anime | /facelift /size:2000x2000
/remix a portrait                           # style transfer
/more                                        # variations
/faceswap myfavoriteguy2                    # needs a saved /control preset
/faceswap /strength:0.5 myfavoriteguy2
/render a man eating a sandwich /facepush:myfavoriteguy2
/render a portrait /cg:0.5                  # ControlNet guidance strength, 0.1-2 range, 0.1-0.5 sweet spot
/inpaint /size:512x768 /strength:1 /guidance:7 fireflies at (night)
/bg | /bg /anime | /bg /format:png | /bg /replace:Bedroom /blur:10
/workflow /run:zoomout-flux fireflies at night /slot1:200 /slot2:50 /slot3:100 /slot4:300
/outpaint /side:top fireflies at night
/outpaint /blur:10 /zoom:6 /contract:50 the moon is exploding
/trace /color /gradient:32 /corner:1        # raster-to-SVG
```

## Audio

```
/makesong Write a song about being chased by a California rattlesnake     # AI-written lyrics
/workflow /run:music-ace15 [verse] gonna make some songs [bridge] gonna make em [chorus] with pirate diffusion yeah!
```

## Quick reference: what maps to what in this CLI

| Telegram syntax | CLI equivalent |
|---|---|
| `/run:slug` / `/wf /run:slug` | `--workflow slug`, or just leave it in the string for `render`/`q` |
| `[negative text]` | `--negative "text"` (render only — `q` sends it inline as-is) |
| `<concept>` / `<concept:weight>` | leave inline — works unparsed via `q`; `render` passes it through as `options_text` |
| reply-to-image (`init_image`) | `--init-image <url-or-path>` |
| `/image1:URL1` + `placeholders` | `--placeholder URL1=<url-or-path>` |
| everything else on this page (`/nofix`, `/karras`, `#recipe`, `/compose`, `/cg:`, `/facepush:`, ...) | not understood by `render`'s parser — use `graydient q "<full command>"` |

## A future source of real examples

The account behind this CLI has its own history of tens of thousands of past renders on
Graydient — a much richer, 1:1-relevant example set than any public guide, since it's actual
prompts that produced actual output this pipeline cared about. There is no confirmed CLI/API
endpoint yet for listing that render history/archive (the web dashboard has a "render archive"
view, but the underlying API route it calls hasn't been verified) — worth checking Graydient's API
docs (https://cloud.graydient.ai/api-help/) for a listing endpoint before building against a
guessed URL.

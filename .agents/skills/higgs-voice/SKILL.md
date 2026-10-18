---
name: higgs-voice
description: Write Graydient prompts for Higgs Audio v3 speech — either audio-higgs (plain text-to-speech in a named preset voice) or clone-higgs (clone a given source voice and have it speak). Use whenever the user wants text spoken aloud, with or without a supplied voice/audio file to clone.
---

### Higgs Voice — TTS and Voice Cloning

The purpose is to turn text into spoken audio using Higgs Audio v3, either as a plain
preset voice, or cloned from a source audio file the user supplies.

###

Decision: is a source audio file given?

Check first, before writing anything, whether the user has supplied or attached a source
voice/audio file (an uploaded voice recording, a voice message reply, a linked audio URL).
This decides everything else.

**Source audio given → clone-higgs.** The parameter is `/initaudio` (no underscore — do not
write `/init_audio`, `/init_audio_url`, `/initvideo`, or `/initimage`). How you reference
the file depends on what you were given:

- **An already-uploaded Graydient file ID** (e.g. `ABC123`, same as any other Graydient
  upload): pass it directly — `/initaudio:ABC123`.
- **A raw URL** (a Telegram file link, an S3/CDN link, anything with `http://`/`https://`
  in it): **do NOT put the URL directly after the colon.** URLs contain `:` and `/`
  characters that collide with the prompt parser's own delimiters and get silently
  dropped — this was a confirmed, repeatedly-reproduced failure mode. Instead, register the
  URL under a top-level `placeholders` object in the request body, and reference it by name
  in the prompt:
  ```json
  {
    "placeholders": { "URL1": "<the actual URL>" },
    "prompt": "/workflow /run:clone-higgs /initaudio:URL1 <spoken text>"
  }
  ```
  Never write `/initaudio:https://...` directly in the prompt string.

**No source audio → audio-higgs.** Pick a preset voice and pass it as `/slot1:<voice>`.
Valid voices: `jake`, `chloe`, `eleanor`, `marcus`, `nora`, `oliver`. If the user didn't name
one, pick whichever best matches the requested tone, or default to `jake`.

### IMPORTANT — DO NOT mix these up ###

`clone-higgs` has **no** `/slot1` — it only ever speaks in the cloned voice from
`/initaudio`. `audio-higgs` has **no** `/initaudio` — it only ever speaks in one of the
six named presets via `/slot1`. Sending `/slot1` to `clone-higgs`, or `/initaudio` to
`audio-higgs`, does nothing on that workflow — pick the workflow first, based on whether a
source file exists, then only use the parameter that workflow actually has.

If the user asks to clone a voice but supplied no file, do not guess or fall back to a
preset silently — say a source audio file is needed and ask for one.

### IMPORTANT — NEVER put a raw URL directly in the prompt string ###

This is the single most-confirmed failure mode for clone-higgs: a URL written directly as
`/initaudio:https://...` gets silently dropped by the prompt parser (the URL's own `:` and
`/` characters collide with the parser's delimiters) — the render fails with an empty
reference clip and no error pointing at why. Any URL MUST go through a top-level
`placeholders` object and be referenced by name instead. See the file-handling section
below for the exact shape. This does not apply to a bare Graydient file ID (no `:`/`/` in
it) — that can go inline.

###

File handling (clone-higgs only):

The parameter is `/initaudio` (no underscore) — DO NOT FORGET to pass it or the render will
fail. A good source clip is roughly 5–20 seconds, one speaker, clean audio with minimal
background noise.

**Already-uploaded file (has a Graydient file ID)** — pass the ID directly:
```
/wf /run:clone-higgs /initaudio:ABC123 <spoken text>
```

**Raw URL (Telegram link, S3/CDN link, anything with `http://`/`https://`)** — register it
as a placeholder, reference it by name, never inline it:
```json
{
  "placeholders": { "URL1": "<the actual URL>" },
  "prompt": "/workflow /run:clone-higgs /initaudio:URL1 <spoken text>"
}
```

###

Control tags — both workflows

Tags describe delivery (emotion, style, sound effects, pacing) and are written directly
in the spoken text, never as literal `<` or `>` characters.

Single tag block, at the front of the line:

```
<tag>:<value>:: <spoken text>
```

Example: `emotion:relief:: Finally, this is working!`

Multiple delivery changes in one message — every block AFTER the first needs `::` on BOTH
sides:

```
<tag>:<value>:: <first part> ::<tag>:<value>:: <second part>
```

A later block missing its leading `::` gets spoken as literal text instead of applied — get
this right.

Emotion (pick at most one per block): elation, amusement, enthusiasm, determination, pride,
contentment, affection, relief, contemplation, confusion, surprise, awe, longing, arousal,
anger, fear, disgust, bitterness, sadness, shame, helplessness

Style (pick at most one per block): singing, shouting, whispering

Sound effects (own block, placed where the sound happens, paired with matching
onomatopoeia): cough (Ahem), laughter (Haha), crying (Boohoo), screaming (Ahh), burping
(Burp), humming (Hmm), sigh (Uh), sniff (Sff), sneeze (Achoo)

Prosody (multiple can combine): speed_very_slow, speed_slow, speed_fast, speed_very_fast,
pitch_low, pitch_high, pause, long_pause, expressive_high, expressive_low

###

Examples:

User input: "Read this out loud, sound excited" (no file attached)

Command:

`/wf /run:audio-higgs /slot1:jake emotion:enthusiasm:: We actually pulled this off, first try!`

---

User input: "Clone this voice and have it say hello" (voice file attached, given Graydient
file ID ABC123)

Command:

`/wf /run:clone-higgs /initaudio:ABC123 emotion:contentment:: Hey, it's really great to finally meet you.`

---

User input: "Use my recording to say this, whisper the first bit then shout the second" (voice
file attached, given Graydient file ID XYZ789)

Command:

`/wf /run:clone-higgs /initaudio:XYZ789 style:whispering:: Come closer, I have a secret. ::style:shouting:: I GOT THE JOB!!!`

---

User input: "Clone this voice and say hello" (given a raw URL, not an uploaded file ID —
e.g. a Telegram file link or S3 link)

Command (URL goes in `placeholders`, referenced by name — NEVER inline):

```json
{
  "placeholders": { "URL1": "<the actual URL>" },
  "prompt": "/workflow /run:clone-higgs /initaudio:URL1 emotion:contentment:: Hey, it's really great to finally meet you."
}
```

###

Don't forget: check for a source file FIRST. File given → clone-higgs + /initaudio (file ID
inline, but a raw URL MUST go through placeholders). No file → audio-higgs + /slot1. Never
send /slot1 to clone-higgs or /initaudio to audio-higgs. Never write /initaudio:https://...
directly in the prompt string!!!

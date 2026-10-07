# Notes for building an LLM-driven harness on top of this CLI

Findings from actually building an agent/orchestrator prototype that shells out to
`graydient` (see the ForgeExpress session that produced this file) — things that looked
like they'd work from reading the docs, tested empirically, with the real result.

## Windows: don't pass multi-line or `<>`/`|`-bearing text as a raw argument

`graydient` is installed as an npm `.cmd` shim on Windows. Launching a `.cmd` via
`subprocess`/`CreateProcess` routes through `cmd.exe`, and its command-line re-quoting
corrupts arguments that combine:
- literal newlines, or
- `<...>` and `|` together with quotes in the same argument

Symptom: the subprocess fails with a spurious `The system cannot find the file specified`
(a generic Windows "couldn't launch/parse this" error) — nothing in that message points at
quoting. Confirmed by bisection: the same content split into pieces launches fine; recombined
with those characters present, it breaks. Newlines alone are also enough to trigger it.

This is a Windows/npm-shim issue, not a Graydient API issue — the same content posted
directly over HTTP (bypassing the CLI) would not have this problem.

**If you're piping LLM-generated or template text into any `graydient` subcommand as an
argument on Windows:** flatten newlines to spaces, and replace `<`, `>`, `|` with
non-metachar equivalents (e.g. `(`, `)`, `/`) before building the argv list. None of that
punctuation is meaningful to a chat persona anyway.

## `graydient q` (raw render endpoint) syntax scope — tested, not assumed

`q`/`quick` posts the exact string you give it into the `render/` endpoint's `prompt`
field. What that endpoint actually accepts, tested directly (not inferred from docs):

| Syntax | Works via `graydient q`? |
|---|---|
| `/render ...` (bare, no workflow) | Yes — documented and this is the default path |
| `/wf /run:<slug> ...` / `/workflow /run:<slug> ...` | Yes |
| `/skill /run:<slug> ...` | **No — `403: unknown \`/skill\``.** This slash-command exists (seen in Graydient support-channel examples, e.g. `/skill /run:ernie ...`), but it's Telegram-bot-layer syntax the bot translates into a call to the *separate* skills API before anything reaches `render/`. The raw render endpoint has no idea what `/skill` means. |
| `//<description>` (skills shorthand) | **No — silently mangled, not rejected.** Sent `"//a lighthouse in a storm, oil painting"`; the API received `"prompt":"/a lighthouse in a storm, oil painting"` (confirmed from the actual queued payload, not inferred) — the double slash was collapsed to one somewhere before the render backend saw it, turning skills-shorthand into a malformed single-slash prompt. This is the worse failure mode of the two: `/skill` at least errors loudly (403), `//` fails silently and would render *something* (just not the skill-enhanced version you asked for) unless you're checking output quality closely. |

**Practical takeaway:** for "auto-pick the workflow and enhance the prompt" behavior, use
`graydient skill-run <prompt>` (or `skills/auto` / `skills/{slug}/invoke` directly) — it's
a genuinely different endpoint from `render/`, not just different syntax on the same one.
Neither skills-invocation syntax survives the raw `render/` endpoint intact. Don't assume
slash-syntax parity between what Telegram's bot accepts and what the raw API accepts — the
bot does translation work in front of the API that the API itself doesn't do, and one of
the two failure modes here (`//`) won't even tell you it happened.

## anima-v2 persona-driven render path — tested SFW, works end to end

Dispatchi's FDE pipeline pairs `anima-v2` with a dedicated persona
(`PERSONA_FDE_IMAGE`/"FetishPromptbot") whose system prompt is adult-content-specific
(`SystemPrompts_FDE_Image.txt`). To test the *mechanism* — persona writes an
anima-v2-formatted prompt, harness submits it, render comes back correct — without running
that persona or producing explicit output, the same technical path was tested with a
generic persona and an SFW scene instead. Result: works cleanly, first try — persona output
matched anima-v2's documented tag-list-then-paragraph format closely enough to render
correctly with no retry needed.

Two persona-reliability findings surfaced in the same test, worth remembering generally
(not anima-v2-specific):

- **A persona can return `responseText: ""` — a clean 200, valid JSON, empty content.**
  `polly` did this twice in a row for the same prompt. This is a silent-failure mode
  distinct from every other failure seen in this session (which all at least errored or
  produced *wrong* text) — a harness must check for empty string, not just check for an
  HTTP/JSON error, or it will silently treat "nothing happened" as success.
- **A persona's own conditioning can override an explicit task instruction in the prompt.**
  Asked to write an anima-v2 image prompt, `SpeechWriterbot` (Dispatchi's dedicated
  monologue-writing persona) ignored that and wrote a monologue anyway — its baked-in
  system prompt won the conflict. `ProductionAssistantbot` (a more general-purpose persona)
  followed the instruction correctly on the first try. Lesson: persona choice is part of
  the reliability surface, not just prompt wording — a persona tuned hard for one task will
  resist being redirected to a different one even with a clear one-off instruction, which
  argues for routing to a general-purpose persona (or a dedicated one built for exactly
  this) rather than repurposing an unrelated specialist.

## Personas are fully configurable — and this CLI exposes none of that, which is the real gap

This is the single biggest correction to everything else in this file, and it's a genuine
documentation hole: `graydient chat <persona> <prompt>` treats "persona" as an opaque
string, but personas are actually a configurable layer on top of a base LLM, set up on the
my.graydient.ai dashboard (outside this CLI entirely):

- **Backing model varies per persona.** `polly` is reportedly backed by an older Mixtral —
  fine for a narrow, well-documented task, not a strong general reasoner. Custom personas
  can be configured against much stronger models (Grok 4.5, MiniMax 3, etc.). A persona's
  reliability ceiling is a function of *which model backs it*, not a property of Graydient
  chat as a whole — this file's earlier findings about `polly` returning empty responses,
  or `SpeechWriterbot` refusing to redirect off-task, are consistent with "this particular
  persona is narrowly tuned / backed by a weaker model," not with "Graydient personas are
  unreliable" as a general claim. There was no way to tell the difference from the CLI
  alone — this is the actual gap.
- **System prompt is fully injectable/toggleable per persona**, plus few-shot input/output
  examples for the first message and for replies. A persona that ignores an inline
  instruction (like `SpeechWriterbot` did with an image-prompt request in testing above)
  may simply not have been configured for that task at all — the fix is dashboard-side
  persona setup, not harness-side prompt engineering.
- **Personas can be given a `<skill>` capability that routes their own output directly into
  a skill call.** This directly supersedes the "personas are text-in/text-out only, no
  evidence of action-issuing" conclusion earlier drafts of this file reached from the
  outside (support-channel history + Dispatchi's own scripts, which only ever showed the
  persona-writes-text-then-harness-submits pattern). That pattern is what you get with a
  *default* persona with skill-routing off — it is not a platform ceiling. A persona
  configured with `<skill>` routing genuinely can collapse "write a prompt, then separately
  submit it" into one step.

**Practical implication:** before concluding a persona is unreliable for some task, check
its dashboard configuration (model, system prompt, skill-routing) rather than treating the
CLI-observed behavior as the platform's ceiling — the CLI surface can't distinguish
"Graydient chat can't do X" from "this specific persona wasn't set up for X." Any harness
built purely against `graydient chat <persona>` inherits this blind spot: it can observe a
persona's behavior but not why it behaves that way.

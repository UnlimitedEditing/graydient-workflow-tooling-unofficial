// Node-native Graydient.ai API client — ported from ForgeExpress's
// src/api/graydient.ts (Electron/React app). Same request shapes and stream
// parsing, no Zustand/Electron dependency: auth + base URL come from config.ts.
import { getApiKey, getBaseUrl } from './config.js'

function baseUrl(): string {
  return getBaseUrl()
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface WorkflowFieldMapping {
  local_field: string
  default_value: string | number | null
  help_text: string
  minimum_value: number | null
  maximum_value: number | null
  node_id?: string | null
}

export interface Workflow {
  id: string
  slug: string
  name: string
  description: string
  thumbnail_url?: string | null
  image_url?: string | null
  avg_elapsed?: number | null
  platform?: string | null
  is_public?: boolean
  field_mapping: WorkflowFieldMapping[]
  concept_mapping: Record<string, string>
  supports_dynamic_concepts: boolean
  supports_txt2img: boolean
  supports_img2img: boolean
  supports_txt2vid: boolean
  supports_img2vid: boolean
  supports_vid2vid: boolean
  supports_vid2img: boolean
  supports_txt2wav: boolean
  supports_vid2wav: boolean
  supports_wav2txt: boolean
}

export interface Concept {
  concept_hash: string
  name: string
  description?: string
  example_url?: string | null
  info_url?: string | null
  is_nsfw?: boolean
  model_family?: string
  tags?: string[]
  token: string
}

export interface Skill {
  id: string
  name: string
  slug: string
  description?: string
  thumbnail_url?: string | null
  is_public?: boolean
  allows_input_media?: boolean
  owner?: boolean
  editable?: boolean
  is_open_source?: boolean
  category?: string
  content?: string
  source_visible?: boolean
  version?: number
  price_cents?: number
  user_id?: number
  inserted_at?: string
  updated_at?: string
}

export interface SkillInvokeResult {
  command: string
  explanation: string
  safe: boolean
  skill: Skill | null
  error?: string
}

export interface ParsedPrompt {
  prompt: string
  negative: string
  workflowSlug: string
  optionsDict: Record<string, string>
  optionsText: string
  initImage: string | null
}

export interface RenderMedia {
  url: string
  media_type?: string
}

export interface RenderInfo {
  render_hash: string
  has_been_rendered?: boolean
  images: Array<{ url?: string; media?: RenderMedia[] }>
}

export interface ResolvedMedia {
  url: string
  mediaType: string | null
  thumbnailUrl: string | null
}

/**
 * Source media for a render. init_image/init_video/init_audio are the
 * original, always-worked "reply target" fields. The _url/_filename variants
 * exist because a custom workflow's OWN field_mapping (e.g. clone-higgs's
 * init_audio_url) doesn't get populated by those base fields at all -- per
 * D:\tripostl\HIGGS-CLONE-HANDOFF.md section 2, HiggsV3VoicePreset checks
 * init_audio / init_audio_url / init_audio_filename in that order, and which
 * one actually arrives non-empty depends on the submission path, not on
 * anything the caller chooses. Set every variant a workflow might read
 * rather than guessing which one applies -- confirmed 2026-08-02 that the
 * API accepts and echoes unknown top-level keys without validating them
 * (silently doing nothing if the wrong one), so there's no cost to setting
 * more than one.
 *
 * IMPORTANT: as of 2026-08-02 the actual server-side mechanism that routes a
 * top-level JSON key into a specific workflow's field_mapping entry is
 * UNCONFIRMED -- setting init_audio_url this way was tested live and did NOT
 * reach the ComfyUI node (confirmed via the node's own debug log showing no
 * value received). These fields are wired through as the best currently-known
 * shape, ready to fix in one place once the real mechanism is confirmed
 * (by Graydient support, or a node-graph-side accommodation).
 *
 * initMeshUrl (added 2026-08-29) is the same pattern for the 'shape2texture-hy3d'
 * workflow's init_mesh_url field_mapping entry (gen_hy3d21_texture_v1.py) -- a
 * GLB uploads fine via the same litterbox mechanism as image/video/audio
 * (resolveMediaInput doesn't inspect content type), but whether Graydient
 * actually routes a raw init_mesh_url top-level key into that field_mapping
 * entry is UNCONFIRMED -- same caveat as init_audio_url above, verify on a
 * live run before trusting this silently worked.
 */
export interface SourceMedia {
  initImage?: string
  initVideo?: string
  initAudio?: string
  initImageUrl?: string
  initImageFilename?: string
  initVideoUrl?: string
  initVideoFilename?: string
  initAudioUrl?: string
  initAudioFilename?: string
  initMeshUrl?: string
  placeholders?: Record<string, string>
  optionPairs?: string[]
}

/** Applies every SourceMedia field present onto a render request body, using
 * the exact key names each field's own docstring/handoff doc specifies. */
function applySourceMediaFields(bodyObj: Record<string, unknown>, sourceMedia?: SourceMedia): void {
  if (!sourceMedia) return
  if (sourceMedia.initImageUrl) bodyObj.init_image_url = sourceMedia.initImageUrl
  if (sourceMedia.initImageFilename) bodyObj.init_image_filename = sourceMedia.initImageFilename
  if (sourceMedia.initVideoUrl) bodyObj.init_video_url = sourceMedia.initVideoUrl
  if (sourceMedia.initVideoFilename) bodyObj.init_video_filename = sourceMedia.initVideoFilename
  if (sourceMedia.initAudioUrl) bodyObj.init_audio_url = sourceMedia.initAudioUrl
  if (sourceMedia.initAudioFilename) bodyObj.init_audio_filename = sourceMedia.initAudioFilename
  if (sourceMedia.initMeshUrl) bodyObj.init_mesh_url = sourceMedia.initMeshUrl
}

export interface SubmitRenderResult {
  renderHash: string
  estimatedRenderTime: number | null
  estimatedWaitTime: number | null
  doneImages: Array<{ url?: string; media?: RenderMedia[] }> | null
}

export interface GraydientChatResult {
  responseId: string
  responseText: string
}

// Commands that act as implicit workflow aliases (no /run:slug needed)
const COMMAND_WORKFLOW_ALIASES: Record<string, string> = {
  render: 'sdxl',
}

export function parseTelegramPrompt(rawInput: string, fallbackWorkflowSlug?: string): ParsedPrompt {
  let input = rawInput.trim()

  // Strip leading /wf
  input = input.replace(/^\/wf\s*/i, '')

  // Detect leading command alias e.g. /render → resolves to a workflow slug
  let workflowSlug = fallbackWorkflowSlug ?? ''
  const aliasMatch = input.match(/^\/(\w+)\b/)
  if (aliasMatch) {
    const alias = aliasMatch[1].toLowerCase()
    if (COMMAND_WORKFLOW_ALIASES[alias]) {
      workflowSlug = COMMAND_WORKFLOW_ALIASES[alias]
      input = input.slice(aliasMatch[0].length).trim()
    }
  }

  // Extract /run:<slug> (overrides alias if both present)
  const runMatch = input.match(/\/run:(\S+)/)
  if (runMatch) {
    workflowSlug = runMatch[1]
    input = input.replace(runMatch[0], '').trim()
  }

  // Extract [negative prompt]
  let negative = ''
  const negMatch = input.match(/\[([^\]]*)\]/)
  if (negMatch) {
    negative = negMatch[1].trim()
    input = input.replace(negMatch[0], '').trim()
  }

  // Extract /key:value pairs into dict
  const optionsDict: Record<string, string> = {}
  const kvRegex = /\/(\w+):(\S+)/g
  let kvMatch
  while ((kvMatch = kvRegex.exec(input)) !== null) {
    optionsDict[kvMatch[1]] = kvMatch[2]
  }
  input = input.replace(/\/\w+:\S+/g, '').trim()

  // Extract /init_image: from options so it goes into the body field, not the options string
  const initImage = optionsDict.init_image ?? null
  delete optionsDict.init_image

  // Extract concepts <name:weight> or <name> into options_text, remove from prompt
  const conceptMatches = input.match(/<[^>]+>/g) ?? []
  const optionsText = conceptMatches.join(' ')
  input = input.replace(/<[^>]+>/g, '').trim()

  const prompt = input.replace(/\s+/g, ' ').trim()

  return { prompt, negative, workflowSlug, optionsDict, optionsText, initImage }
}

// ── Internal helpers ─────────────────────────────────────────────────────────

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return {
    'Content-Type': 'application/vnd.api+json',
    Accept: 'application/vnd.api+json',
    Authorization: `Bearer ${getApiKey()}`,
    ...extra,
  }
}

// ── Workflows / Concepts / Skills ───────────────────────────────────────────

let workflowCache: Workflow[] | null = null

export async function fetchWorkflows(): Promise<Workflow[]> {
  if (workflowCache) return workflowCache

  const res = await fetch(`${baseUrl()}workflows/`, { headers: headers() })
  if (!res.ok) throw new Error(`fetchWorkflows failed: ${res.status}`)

  const json = await res.json()
  const items: Workflow[] = (json.data ?? json).map((item: { id: string; attributes: Omit<Workflow, 'id'> }) => ({
    id: item.id,
    ...(item.attributes ?? item),
  }))

  workflowCache = items
  return items
}

export async function fetchConcepts(modelFamily?: string, search?: string): Promise<Concept[]> {
  const params = new URLSearchParams({ per_page: '1000' })
  if (modelFamily) params.set('model_family', modelFamily)
  if (search) params.set('search', search)
  const res = await fetch(`${baseUrl()}concepts/?${params}`, { headers: headers() })
  if (!res.ok) return []
  const json = await res.json()
  const items: unknown[] = json.data ?? json
  if (!Array.isArray(items)) return []
  return items.map((item: unknown) => {
    const raw = item as Record<string, unknown>
    const attrs = (raw.attributes ?? raw) as Record<string, unknown>
    return {
      concept_hash: (attrs.concept_hash ?? raw.id ?? '') as string,
      name: (attrs.name ?? '') as string,
      description: attrs.description as string | undefined,
      example_url: attrs.example_url as string | null | undefined,
      info_url: attrs.info_url as string | null | undefined,
      is_nsfw: attrs.is_nsfw as boolean | undefined,
      model_family: attrs.model_family as string | undefined,
      tags: attrs.tags as string[] | undefined,
      token: (attrs.token ?? '') as string,
    }
  })
}

export async function fetchSkills(): Promise<Skill[]> {
  const res = await fetch(`${baseUrl()}skills/`, { headers: headers() })
  if (!res.ok) return []
  const json = await res.json()
  const items: unknown[] = json.data ?? json
  if (!Array.isArray(items)) return []
  return items.map((item: unknown) => {
    const raw = item as Record<string, unknown>
    const attrs = (raw.attributes ?? raw) as Record<string, unknown>
    return {
      id: (raw.id ?? attrs.id ?? '') as string,
      name: (attrs.name ?? '') as string,
      slug: (attrs.slug ?? '') as string,
      description: attrs.description as string | undefined,
      thumbnail_url: attrs.thumbnail_url as string | null | undefined,
      is_public: attrs.is_public as boolean | undefined,
      allows_input_media: attrs.allows_input_media as boolean | undefined,
      owner: attrs.owner as boolean | undefined,
      editable: attrs.editable as boolean | undefined,
      is_open_source: attrs.is_open_source as boolean | undefined,
      category: attrs.category as string | undefined,
    }
  })
}

export async function fetchSkillDetail(slug: string): Promise<Skill | null> {
  const res = await fetch(`${baseUrl()}skills/${slug}`, { headers: headers() })
  if (!res.ok) return null
  const json = await res.json()
  const raw = (json.data ?? json) as Record<string, unknown>
  const attrs = (raw.attributes ?? raw) as Record<string, unknown>
  return {
    id: (raw.id ?? attrs.id ?? '') as string,
    name: (attrs.name ?? '') as string,
    slug: (attrs.slug ?? '') as string,
    description: attrs.description as string | undefined,
    thumbnail_url: attrs.thumbnail_url as string | null | undefined,
    is_public: attrs.is_public as boolean | undefined,
    allows_input_media: attrs.allows_input_media as boolean | undefined,
    owner: attrs.owner as boolean | undefined,
    editable: attrs.editable as boolean | undefined,
    is_open_source: attrs.is_open_source as boolean | undefined,
    category: attrs.category as string | undefined,
    content: attrs.content as string | undefined,
    source_visible: attrs.source_visible as boolean | undefined,
    version: attrs.version as number | undefined,
    price_cents: attrs.price_cents as number | undefined,
    user_id: attrs.user_id as number | undefined,
    inserted_at: attrs.inserted_at as string | undefined,
    updated_at: attrs.updated_at as string | undefined,
  }
}

// ── Render submit + stream ──────────────────────────────────────────────────

export type StreamEventHandler = (name: string, data: Record<string, unknown>) => void

/**
 * Open a WebSocket to stream render events for a known render_hash, as a
 * fallback path. The SSE stream read by submitRender() can close before
 * `rendering_done` fires (server-side quirk) — the WS is the reliable
 * completion signal in that case. Returns a cleanup function.
 */
function connectRenderWebSocket(
  renderHash: string,
  onDone: (images: Array<{ url?: string; media?: RenderMedia[] }> | null) => void
): () => void {
  const wsBase = baseUrl().replace(/^https?:\/\//, 'wss://').replace(/\/api\/.*$/, '')
  const url = `${wsBase}/render-events/${renderHash}?token=${getApiKey()}`
  let ws: WebSocket | null = null
  try {
    ws = new WebSocket(url)
  } catch {
    return () => {}
  }

  ws.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data as string) as { event: string; data: Record<string, unknown> }
      if (parsed.event === 'done') {
        onDone((parsed.data?.images as Array<{ url?: string; media?: RenderMedia[] }>) ?? null)
      }
    } catch {
      /* ignore */
    }
  }

  const pingTimer = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ command: 'ping' }))
    }
  }, 25000)

  return () => {
    clearInterval(pingTimer)
    try {
      ws?.close()
    } catch {
      /* ignore */
    }
  }
}

/**
 * Submit a render and stream events until rendering_done.
 * onStreamEvent is called for each event as it arrives (for progress output).
 * Resolves when the stream closes or rendering_done fires.
 */
export async function submitRender(
  rawInput: string,
  fallbackWorkflowSlug: string | undefined,
  onStreamEvent: StreamEventHandler,
  sourceMedia?: SourceMedia,
  signal?: AbortSignal
): Promise<SubmitRenderResult> {
  const parsed = parseTelegramPrompt(rawInput, fallbackWorkflowSlug)

  let options = parsed.workflowSlug ? `/run:${parsed.workflowSlug}` : ''
  const extraOptions = Object.entries(parsed.optionsDict).map(([k, v]) => `/${k}:${v}`)
  if (extraOptions.length) options += ' ' + extraOptions.join(' ')
  if (sourceMedia?.optionPairs?.length) {
    options += ' ' + sourceMedia.optionPairs.join(' ')
  }

  const bodyObj: Record<string, unknown> = {
    prompt: parsed.prompt,
    task: 'workflow',
    progressive_return: true,
    stream: true,
    options_text: parsed.optionsText,
    options: options.trim(),
    placeholders: sourceMedia?.placeholders ?? {},
    session_id: `cli-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  }

  const initImage = sourceMedia?.initImage ?? parsed.initImage
  if (initImage) bodyObj.init_image = initImage
  if (sourceMedia?.initVideo) bodyObj.init_video = sourceMedia.initVideo
  if (sourceMedia?.initAudio) {
    bodyObj.init_audio = sourceMedia.initAudio
    // Audio-only workflows (no image/video field) rely on init_image as the
    // generic "reply target" — but don't clobber a real init_image/init_video
    // when this is an image+audio (e.g. lipsync) render.
    if (!initImage && !sourceMedia?.initVideo) bodyObj.init_image = sourceMedia.initAudio
  }
  applySourceMediaFields(bodyObj, sourceMedia)
  if (parsed.negative) bodyObj.negative_prompt = parsed.negative

  return streamRenderBody(bodyObj, onStreamEvent, signal)
}

/**
 * Submit a render passing `rawInput` straight through as the `prompt` field,
 * untouched — no client-side mini-language parsing at all. This is the raw
 * Telegram/PirateDiffusion command syntax path: Graydient's own backend
 * already parses the full slash-command nomenclature (documented in bulk at
 * https://graydient.ai/pirate-diffusion-guide/ and in
 * docs/telegram-prompt-syntax.md) out of a plain `prompt` string, the same
 * parser used for Telegram/webui input — confirmed in the wild by API users
 * posting things like `prompt: "/workflow /run:animate-wan22 /size:704x1024
 * /length:81 /fps:16 she smiles..."` with no separate `options` field and
 * having it work (see docs/graydient-api-support-notes.md, Ape Agent
 * 29.08.2025). submitRender()'s own parseTelegramPrompt only understands a
 * reduced subset (/run:, /key:value, [neg], <concept>) and silently drops
 * anything else (bare flags like /nofix, /karras, #recipe hashtags, /compose
 * zone params, etc.) — this path exists so any syntax from the guide works
 * without the CLI needing to know about it first.
 */
export async function submitRenderRaw(
  rawInput: string,
  onStreamEvent: StreamEventHandler,
  sourceMedia?: SourceMedia,
  signal?: AbortSignal
): Promise<SubmitRenderResult> {
  const bodyObj: Record<string, unknown> = {
    prompt: rawInput.trim(),
    task: 'workflow',
    progressive_return: true,
    stream: true,
    placeholders: sourceMedia?.placeholders ?? {},
    session_id: `cli-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  }

  if (sourceMedia?.initImage) bodyObj.init_image = sourceMedia.initImage
  if (sourceMedia?.initVideo) bodyObj.init_video = sourceMedia.initVideo
  if (sourceMedia?.initAudio) {
    bodyObj.init_audio = sourceMedia.initAudio
    if (!sourceMedia?.initImage && !sourceMedia?.initVideo) bodyObj.init_image = sourceMedia.initAudio
  }
  applySourceMediaFields(bodyObj, sourceMedia)

  return streamRenderBody(bodyObj, onStreamEvent, signal)
}

async function streamRenderBody(
  bodyObj: Record<string, unknown>,
  onStreamEvent: StreamEventHandler,
  signal?: AbortSignal
): Promise<SubmitRenderResult> {
  const res = await fetch(`${baseUrl()}render/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getApiKey()}`,
      Accept: 'application/vnd.api+json',
    },
    body: JSON.stringify(bodyObj),
    signal,
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || `render/ failed: ${res.status}`)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let renderHash: string | null = null
  let estimatedRenderTime: number | null = null
  let estimatedWaitTime: number | null = null
  let doneImages: Array<{ url?: string; media?: RenderMedia[] }> | null = null
  let renderingError: string | null = null

  signal?.addEventListener('abort', () => {
    // Not awaited — but must be caught, or Node treats this as an unhandled
    // rejection and crashes the whole process (the underlying fetch stream
    // that .cancel() rejects with is the same abort we just triggered).
    reader.cancel().catch(() => {})
  })

  // WS fallback is armed as soon as we have a render_hash, in case the SSE
  // stream closes before rendering_done fires.
  let wsCleanup: (() => void) | null = null
  let wsResolveDone: ((images: Array<{ url?: string; media?: RenderMedia[] }> | null) => void) | null = null
  const wsDonePromise = new Promise<Array<{ url?: string; media?: RenderMedia[] }> | null>((resolve) => {
    wsResolveDone = resolve
  })

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const raw = line.startsWith('data:') ? line.slice(5).trim() : line.trim()
      if (!raw || raw === '[DONE]') continue
      try {
        const parsed2 = JSON.parse(raw) as Record<string, unknown>

        let evtName: string
        let evtData: Record<string, unknown>
        if (typeof parsed2.event === 'string') {
          evtName = parsed2.event
          evtData = (parsed2.data as Record<string, unknown>) ?? {}
        } else if (parsed2.render_queued) {
          evtName = 'render_queued'
          evtData = parsed2.render_queued as Record<string, unknown>
        } else if (parsed2.rendering_started) {
          evtName = 'rendering_started'
          evtData = parsed2.rendering_started as Record<string, unknown>
        } else if (parsed2.rendering_done) {
          evtName = 'rendering_done'
          evtData = parsed2.rendering_done as Record<string, unknown>
        } else if (parsed2.rendering_error) {
          evtName = 'rendering_error'
          evtData = parsed2.rendering_error as Record<string, unknown>
        } else {
          evtName = Object.keys(parsed2)[0] ?? 'unknown'
          evtData = {}
        }

        if (evtName === 'render_queued') {
          renderHash = (evtData.render_hash ?? null) as string | null
          estimatedRenderTime = (evtData.estimated_render_time ?? null) as number | null
          estimatedWaitTime = (evtData.estimated_wait_time ?? null) as number | null
          onStreamEvent('render_queued', evtData)
          if (renderHash && !wsCleanup) {
            wsCleanup = connectRenderWebSocket(renderHash, (images) => wsResolveDone?.(images))
          }
        } else if (evtName === 'rendering_started' || evtName === 'started') {
          onStreamEvent('rendering_started', evtData)
        } else if (evtName === 'rendering_done' || evtName === 'done') {
          if (!renderHash) renderHash = (evtData.render_hash ?? null) as string | null
          doneImages = (evtData.images ?? null) as Array<{ url?: string; media?: RenderMedia[] }> | null
          onStreamEvent('rendering_done', evtData)
          reader.cancel().catch(() => {})
          break
        } else if (evtName === 'rendering_error' || evtName === 'error') {
          renderingError = String(evtData.message ?? evtData.error ?? 'Rendering failed')
          onStreamEvent('rendering_error', evtData)
          reader.cancel().catch(() => {})
          break
        } else {
          onStreamEvent(evtName, evtData)
        }
      } catch {
        /* non-JSON stream line — skip */
      }
    }
    if (renderingError || doneImages) break
  }

  if (renderingError) {
    wsCleanup?.()
    throw new Error(renderingError)
  }

  // The SSE stream can close before rendering_done fires, or rendering_done
  // can fire without a populated images field (both observed in practice) —
  // either way, give the WebSocket a short window to deliver images, then
  // give up rather than blocking for the caller's full render timeout.
  // Callers (render/skill-run commands) fall back to a direct
  // fetchRenderInfo() status check via resolveFinalMedia() when this comes
  // back empty, which is fast and reliable — no need to hold the connection
  // open any longer waiting on the WS.
  if (!doneImages && renderHash) {
    const shortWindow = new Promise<null>((resolve) => setTimeout(() => resolve(null), 20_000))
    const abortedPromise = new Promise<null>((resolve) => {
      signal?.addEventListener('abort', () => resolve(null))
    })
    doneImages = await Promise.race([wsDonePromise, shortWindow, abortedPromise])
  }
  wsCleanup?.()

  if (!renderHash) throw new Error('No render_hash in stream response')

  return { renderHash, estimatedRenderTime, estimatedWaitTime, doneImages }
}

// ── Skills flow ──────────────────────────────────────────────────────────────

export async function invokeSkill(
  prompt: string,
  skillSlug?: string,
  inputMedia?: { type: 'image' | 'audio' | 'video'; reference: string },
  signal?: AbortSignal
): Promise<SkillInvokeResult> {
  const url = skillSlug ? `${baseUrl()}skills/${skillSlug}/invoke` : `${baseUrl()}skills/auto`

  const bodyObj: Record<string, unknown> = { prompt }
  if (inputMedia) bodyObj.input_media = inputMedia

  const res = await fetch(url, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(bodyObj),
    signal,
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText)
  }

  const json = await res.json()
  const data = (json.data ?? json) as Record<string, unknown>

  return {
    command: (data.command ?? '') as string,
    explanation: (data.explanation ?? '') as string,
    safe: (data.safe ?? true) as boolean,
    skill: (data.skill ?? null) as Skill | null,
    error: data.error as string | undefined,
  }
}

export async function submitSkill(
  rawPrompt: string,
  onStreamEvent: StreamEventHandler,
  skillSlug?: string,
  sourceMedia?: { initImage?: string },
  signal?: AbortSignal
): Promise<SubmitRenderResult> {
  let prompt = rawPrompt.trim()
  let resolvedSlug = skillSlug

  const skillsRunMatch = prompt.match(/^\/skills\s+\/run:(\S+)\s*(.*)/i)
  if (skillsRunMatch) {
    resolvedSlug = skillsRunMatch[1]
    prompt = skillsRunMatch[2].trim() || prompt
  } else if (prompt.startsWith('//')) {
    prompt = prompt.slice(2).trim()
    resolvedSlug = undefined
  } else if (/^\/skills\s+/i.test(prompt)) {
    prompt = prompt.replace(/^\/skills\s+/i, '').trim()
  }

  const inputMedia = sourceMedia?.initImage
    ? { type: 'image' as const, reference: sourceMedia.initImage }
    : undefined

  const invoked = await invokeSkill(prompt, resolvedSlug, inputMedia, signal)

  if (invoked.error) throw new Error(`Skill error: ${invoked.error}`)
  if (!invoked.safe) throw new Error('Skill generated an unsafe command')
  if (!invoked.command) throw new Error('Skill returned no command')

  return submitRender(invoked.command, undefined, onStreamEvent, sourceMedia, signal)
}

// ── Render info / media resolution ──────────────────────────────────────────

export async function fetchRenderInfo(renderHash: string): Promise<RenderInfo> {
  const res = await fetch(`${baseUrl()}render/${renderHash}/`, { headers: headers(), cache: 'no-store' })
  if (!res.ok) throw new Error(`fetchRenderInfo failed: ${res.status}`)
  const json = await res.json()
  return (json.data?.attributes ?? json) as RenderInfo
}

export function resolveAllMedia(info: RenderInfo): ResolvedMedia[] {
  return (info.images ?? []).flatMap((img) => {
    if (img.media && img.media.length > 0) {
      return img.media.map((m) => ({
        url: m.url,
        mediaType: m.media_type ?? null,
        thumbnailUrl: img.url ?? null,
      }))
    }
    if (img.url) return [{ url: img.url, mediaType: null, thumbnailUrl: null }]
    return []
  })
}

/**
 * Resolve final media for a completed submitRender()/submitSkill() result.
 * The stream's own done-payload doesn't always carry `images` (seen in
 * practice even on a genuine rendering_done) — same gap the Electron app
 * works around in renderQueue.ts by falling back to a direct fetchRenderInfo
 * once the stream is exhausted. Do the same here rather than reporting the
 * render as incomplete when it actually finished.
 *
 * A single immediate fetchRenderInfo can still race the backend: video
 * renders in particular can fire `rendering_done` slightly before the row's
 * media metadata is persisted, so one empty GET isn't proof the render
 * failed. Retry with backoff for a short window before giving up.
 */
export async function resolveFinalMedia(result: SubmitRenderResult): Promise<ResolvedMedia[]> {
  let media = result.doneImages?.length ? resolveAllMedia({ render_hash: result.renderHash, images: result.doneImages }) : []
  // Video renders in particular have been observed (see docs/graydient-api-support-notes.md)
  // to persist their media row noticeably later than rendering_done fires — a
  // ~30s window is enough for images but not reliably enough for video, so the
  // tail keeps retrying out to ~2 minutes total before giving up. This only
  // costs time in the genuinely-still-processing case; it returns immediately
  // once media shows up.
  const delaysMs = [1000, 2000, 3000, 5000, 8000, 13000, 20000, 30000, 45000]
  for (let attempt = 0; !media.length && attempt <= delaysMs.length; attempt++) {
    if (attempt > 0) await new Promise((resolve) => setTimeout(resolve, delaysMs[attempt - 1]))
    try {
      const info = await fetchRenderInfo(result.renderHash)
      media = resolveAllMedia(info)
    } catch {
      // fetchRenderInfo failed — retry on the next attempt, or give up after the last one
    }
  }
  return media
}

export async function cancelRender(renderHash: string): Promise<void> {
  try {
    await fetch(`${baseUrl()}render/${renderHash}/cancel/`, { method: 'POST', headers: headers() })
  } catch {
    // best-effort
  }
}

// ── Chat / Personas ──────────────────────────────────────────────────────────

export async function callGraydientChat(
  persona: string,
  prompt: string,
  options?: { imageUrl?: string; replyTo?: string }
): Promise<GraydientChatResult> {
  const body: Record<string, unknown> = {
    persona,
    prompt,
    sync: true,
    session_id: `cli-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
  }
  if (options?.imageUrl) body.image_url = options.imageUrl
  if (options?.replyTo) body.reply_to = options.replyTo

  const res = await fetch(`${baseUrl()}chat/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getApiKey()}`,
      Accept: 'application/vnd.api+json',
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Chat API ${res.status}: ${err}`)
  }

  const json = await res.json()
  const rawData = json.data ?? json
  const item = (Array.isArray(rawData) ? rawData[0] : rawData) as Record<string, unknown> | undefined
  const attrs = (item?.attributes ?? item ?? {}) as Record<string, unknown>
  const responseText = String(attrs.response_text ?? '').replace(/<\/?[a-z][a-z0-9]*>/gi, '').trim()
  return {
    responseId: String(attrs.response_id ?? item?.id ?? ''),
    responseText,
  }
}

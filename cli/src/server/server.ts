import { createServer, IncomingMessage, ServerResponse } from 'node:http'
import { existsSync, createReadStream, statSync, readFileSync } from 'node:fs'
import { join, extname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { KanbanStore, RENDERS_DIR, REELS_DIR, extractCleanDescription } from './store.js'
import { RenderWorker } from './worker.js'
import { TunnelManager } from './tunnel.js'
import { compileVideoReel } from './ffmpeg.js'
import { createZipBuffer, ZipEntry } from './zip.js'
import { fetchWorkflows, fetchSkills } from '../client.js'

export const PUBLIC_DIR = join(process.cwd(), 'public')

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
}

function parseJsonBody(req: IncomingMessage): Promise<Record<string, any>> {
  return new Promise((resolve, reject) => {
    let body = ''
    req.on('data', (chunk) => {
      body += chunk
      if (body.length > 10 * 1024 * 1024) {
        req.destroy()
        reject(new Error('Request payload too large'))
      }
    })
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {})
      } catch (err) {
        reject(new Error('Invalid JSON format'))
      }
    })
    req.on('error', reject)
  })
}

function sendJson(res: ServerResponse, data: unknown, status = 200): void {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
  })
  res.end(JSON.stringify(data))
}

function sendError(res: ServerResponse, message: string, status = 400): void {
  sendJson(res, { error: message }, status)
}

function streamFileWithRanges(filePath: string, req: IncomingMessage, res: ServerResponse): void {
  if (!existsSync(filePath)) {
    res.writeHead(404, { 'Content-Type': 'text/plain' })
    res.end('Not Found')
    return
  }

  const stat = statSync(filePath)
  const fileSize = stat.size
  const ext = extname(filePath).toLowerCase()
  const mime = MIME_TYPES[ext] || 'application/octet-stream'
  const range = req.headers.range

  if (range) {
    const parts = range.replace(/bytes=/, '').split('-')
    const start = parseInt(parts[0], 10)
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1
    const chunkSize = end - start + 1

    res.writeHead(206, {
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunkSize,
      'Content-Type': mime,
      'Access-Control-Allow-Origin': '*',
    })

    createReadStream(filePath, { start, end }).pipe(res)
  } else {
    res.writeHead(200, {
      'Content-Length': fileSize,
      'Content-Type': mime,
      'Accept-Ranges': 'bytes',
      'Access-Control-Allow-Origin': '*',
    })
    createReadStream(filePath).pipe(res)
  }
}

export function createRenderServer(port = 7860): {
  server: ReturnType<typeof createServer>
  store: KanbanStore
  worker: RenderWorker
  tunnel: TunnelManager
  start: () => Promise<number>
  stop: () => void
} {
  const store = new KanbanStore()
  const worker = new RenderWorker(store)
  const tunnel = new TunnelManager()

  const sseClients = new Set<ServerResponse>()

  const broadcastEvent = (eventType: string, payload: unknown) => {
    const data = `event: ${eventType}\ndata: ${JSON.stringify(payload)}\n\n`
    for (const client of sseClients) {
      try {
        client.write(data)
      } catch {
        sseClients.delete(client)
      }
    }
  }

  worker.on('card-updated', (card) => {
    broadcastEvent('card-updated', card)
    broadcastEvent('state-updated', store.getState())
  })

  worker.on('render-progress', (progress) => {
    broadcastEvent('render-progress', progress)
  })

  tunnel.on('tunnel-started', (status) => {
    store.setTunnelState(status)
    broadcastEvent('tunnel-updated', status)
  })

  tunnel.on('tunnel-stopped', (status) => {
    store.setTunnelState(tunnel.getStatus())
    broadcastEvent('tunnel-updated', tunnel.getStatus())
  })

  const server = createServer(async (req, res) => {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*')
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Range')

    if (req.method === 'OPTIONS') {
      res.writeHead(204)
      res.end()
      return
    }

    const parsedUrl = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`)
    const pathname = parsedUrl.pathname

    // ── Static Media Serving ────────────────────────────────────────────────
    if (pathname.startsWith('/api/media/reels/')) {
      const filename = decodeURIComponent(pathname.replace('/api/media/reels/', ''))
      const filePath = join(REELS_DIR, basename(filename))
      streamFileWithRanges(filePath, req, res)
      return
    }

    if (pathname.startsWith('/api/media/')) {
      const filename = decodeURIComponent(pathname.replace('/api/media/', ''))
      const filePath = join(RENDERS_DIR, basename(filename))
      streamFileWithRanges(filePath, req, res)
      return
    }

    // ── SSE Endpoint ────────────────────────────────────────────────────────
    if (pathname === '/api/events') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      })
      res.write(`data: ${JSON.stringify({ type: 'connected', state: store.getState() })}\n\n`)
      sseClients.add(res)

      req.on('close', () => {
        sseClients.delete(res)
      })
      return
    }

    // ── API: State & Info ───────────────────────────────────────────────────
    if (req.method === 'GET' && pathname === '/api/state') {
      sendJson(res, store.getState())
      return
    }

    if (req.method === 'GET' && pathname === '/api/system/info') {
      try {
        const [workflows, skills] = await Promise.all([
          fetchWorkflows().catch(() => []),
          fetchSkills().catch(() => []),
        ])
        sendJson(res, {
          workflows: workflows.map((w) => ({ slug: w.slug, name: w.name })),
          skills: skills.map((s) => ({ slug: s.slug, name: s.name, allows_input_media: s.allows_input_media })),
          tunnel: tunnel.getStatus(),
        })
      } catch (err) {
        sendError(res, err instanceof Error ? err.message : String(err))
      }
      return
    }

    // ── API: Prompts Skim / Library ─────────────────────────────────────────
    if (req.method === 'GET' && pathname === '/api/prompts/skim') {
      const cards = store.getCards()
      const format = parsedUrl.searchParams.get('format') || 'markdown'

      if (format === 'json') {
        sendJson(res, cards.map((c) => ({
          title: c.title,
          prompt: c.prompt,
          contentDescription: c.contentDescription,
          tags: c.tags,
          motionPrompt: c.chain?.step2Prompt,
          status: c.status,
          mediaUrls: c.media?.map((m) => m.url),
        })))
        return
      }

      // Markdown / Text export for quick cheap content descriptions
      const lines = cards.map((c, i) => {
        const title = `### ${i + 1}. ${c.title}`
        const desc = `**Content Description:** ${c.contentDescription || extractCleanDescription(c.prompt)}`
        const prompt = `**Visual Prompt:** \`${c.prompt}\``
        const motion = c.chain?.step2Prompt ? `**Animation Motion:** \`${c.chain.step2Prompt}\`` : ''
        const tags = c.tags?.length ? `**Tags:** #${c.tags.join(' #')}` : ''
        return [title, desc, prompt, motion, tags].filter(Boolean).join('\n\n')
      })

      res.writeHead(200, { 'Content-Type': 'text/markdown; charset=utf-8' })
      res.end(lines.join('\n\n---\n\n'))
      return
    }

    // ── API: Cards CRUD & Batch ─────────────────────────────────────────────
    if (req.method === 'POST' && pathname === '/api/cards') {
      try {
        const body = await parseJsonBody(req)

        // Support batch queueing: { batch: ["prompt 1", "prompt 2", ...] }
        if (Array.isArray(body.batch)) {
          const added = []
          for (const raw of body.batch) {
            const p = String(raw).trim()
            if (!p) continue
            const card = store.addCard({
              prompt: p,
              renderType: body.renderType || 'quick',
              status: body.status || 'queued',
              workflowSlug: body.workflowSlug,
              skillSlug: body.skillSlug,
              chain: body.chain,
            })
            added.push(card)
          }
          worker.notifyNewJob()
          broadcastEvent('state-updated', store.getState())
          sendJson(res, { addedCount: added.length, cards: added })
          return
        }

        // Single card creation
        const card = store.addCard(body)
        if (card.status === 'queued') {
          worker.notifyNewJob()
        }
        broadcastEvent('card-created', card)
        broadcastEvent('state-updated', store.getState())
        sendJson(res, card, 201)
      } catch (err) {
        sendError(res, err instanceof Error ? err.message : String(err))
      }
      return
    }

    const cardIdMatch = pathname.match(/^\/api\/cards\/([a-zA-Z0-9_-]+)/)
    if (cardIdMatch) {
      const cardId = cardIdMatch[1]

      // 1-Click Animate Image with omni-russ
      if (req.method === 'POST' && pathname.endsWith('/animate')) {
        try {
          const body = await parseJsonBody(req)
          const sourceCard = store.getCard(cardId)
          if (!sourceCard) {
            sendError(res, 'Card not found', 404)
            return
          }

          const skillSlug = body.skillSlug || 'omni-russ'
          const fps = body.fps || 24
          const size = body.size || '1024x704'
          const length = body.length || 144
          const basePrompt =
            body.prompt ||
            `integrated_multimodal_description: cinematic camera motion, organic detailed lighting and motion\noverall_soundscape: ambient environmental sounds`

          const allImages = (sourceCard.media || []).filter((m) => m.mediaType === 'image' && m.localPath)
          if (allImages.length === 0) {
            sendError(res, 'Source card has no locally downloaded image to animate', 400)
            return
          }

          // Decide whether to animate all images or a specific image
          const targetImages = (typeof body.imageIndex === 'number' && allImages[body.imageIndex])
            ? [allImages[body.imageIndex]]
            : allImages

          const isDialogue = !!body.isDialogue
          const dialogueLines: string[] = Array.isArray(body.dialogueLines) ? body.dialogueLines : []
          const motionPrompts: string[] = Array.isArray(body.prompts) && body.prompts.length > 0 ? body.prompts : [basePrompt]

          const createdCards = []

          for (const promptTemplate of motionPrompts) {
            for (let i = 0; i < targetImages.length; i++) {
              const img = targetImages[i]
              let finalPrompt = promptTemplate.trim()

              // Append dialogue in quotes if in dialogue mode
              if (isDialogue && dialogueLines.length > 0) {
                const line = dialogueLines[i % dialogueLines.length].trim()
                const cleanQuote = line.replace(/^["']|["']$/g, '')
                finalPrompt = `${finalPrompt} "${cleanQuote}"`
              }

              if (!finalPrompt.includes('/fps:')) finalPrompt += ` /fps:${fps}`
              if (!finalPrompt.includes('/size:')) finalPrompt += ` /size:${size}`
              if (!finalPrompt.includes('/length:')) finalPrompt += ` /length:${length}`

              const dialogueSuffix = isDialogue && dialogueLines[i]
                ? ` ("${dialogueLines[i].replace(/^["']|["']$/g, '').slice(0, 24)}...")`
                : ''

              const newCard = store.addCard({
                title: `${sourceCard.title} - Clip ${i + 1}${dialogueSuffix}`,
                status: 'queued',
                prompt: finalPrompt,
                contentDescription: `Omni-Russ animation of Clip ${i + 1}: ${finalPrompt.slice(0, 100)}`,
                renderType: 'skill',
                skillSlug,
                tags: [...(sourceCard.tags || []), 'omni-russ', 'animation', `clip-${i + 1}`],
                media: [img], // keep reference to source image
                chain: {
                  enabled: true,
                  step: 2,
                  step1Type: 'image',
                  step2Type: 'skill',
                  step2Skill: skillSlug,
                  step2Prompt: finalPrompt,
                  fps,
                  length,
                  size,
                  parentCardId: sourceCard.id,
                  sourceImageIndex: i + 1,
                  sourceImageMedia: img,
                },
              })

              createdCards.push(newCard)
            }
          }

          worker.notifyNewJob()
          broadcastEvent('state-updated', store.getState())
          sendJson(res, { queuedCount: createdCards.length, cards: createdCards })
        } catch (err) {
          sendError(res, err instanceof Error ? err.message : String(err))
        }
        return
      }

      // Move to Queue
      if (req.method === 'POST' && pathname.endsWith('/queue')) {
        const updated = store.updateCard(cardId, { status: 'queued', error: undefined })
        if (!updated) {
          sendError(res, 'Card not found', 404)
          return
        }
        worker.notifyNewJob()
        broadcastEvent('state-updated', store.getState())
        sendJson(res, updated)
        return
      }

      // Update Card
      if (req.method === 'PATCH') {
        try {
          const body = await parseJsonBody(req)
          const updated = store.updateCard(cardId, body)
          if (!updated) {
            sendError(res, 'Card not found', 404)
            return
          }
          if (updated.status === 'queued') {
            worker.notifyNewJob()
          }
          broadcastEvent('card-updated', updated)
          broadcastEvent('state-updated', store.getState())
          sendJson(res, updated)
        } catch (err) {
          sendError(res, err instanceof Error ? err.message : String(err))
        }
        return
      }

      // Delete Card
      if (req.method === 'DELETE') {
        const deleted = store.deleteCard(cardId)
        if (!deleted) {
          sendError(res, 'Card not found', 404)
          return
        }
        broadcastEvent('state-updated', store.getState())
        sendJson(res, { success: true })
        return
      }
    }

    // ── API: Queue Reordering ───────────────────────────────────────────────
    if (req.method === 'POST' && pathname === '/api/queue/reorder') {
      try {
        const body = await parseJsonBody(req)
        if (Array.isArray(body.orderedIds)) {
          store.reorderQueue(body.orderedIds)
          broadcastEvent('state-updated', store.getState())
          sendJson(res, { success: true })
          return
        }
        sendError(res, 'orderedIds array required')
      } catch (err) {
        sendError(res, err instanceof Error ? err.message : String(err))
      }
      return
    }

    // ── API: Render Cancel ──────────────────────────────────────────────────
    if (req.method === 'POST' && pathname === '/api/render/cancel') {
      const cancelled = await worker.cancelCurrent()
      sendJson(res, { cancelled })
      return
    }

    // ── API: Compile Video Reel (FFmpeg) ────────────────────────────────────
    if (req.method === 'POST' && pathname === '/api/reel/compile') {
      try {
        const body = await parseJsonBody(req)
        const cards = store.getCards()

        // Find video clips to stitch
        let targetCards = cards.filter((c) => c.status === 'done' && c.media?.some((m) => m.mediaType === 'video'))
        if (Array.isArray(body.cardIds) && body.cardIds.length > 0) {
          targetCards = targetCards.filter((c) => body.cardIds.includes(c.id))
        }

        const videoPaths: string[] = []
        const clipInfo: Array<{ filename: string; prompt?: string }> = []

        for (const c of targetCards) {
          const vid = c.media?.find((m) => m.mediaType === 'video' && m.localPath)
          if (vid && vid.localPath && existsSync(vid.localPath)) {
            videoPaths.push(vid.localPath)
            clipInfo.push({
              filename: vid.filename,
              prompt: c.chain?.step2Prompt || c.prompt,
            })
          }
        }

        if (videoPaths.length === 0) {
          sendError(res, 'No finished video files available to compile into a reel', 400)
          return
        }

        const reelResult = await compileVideoReel(videoPaths, clipInfo)
        sendJson(res, reelResult)
      } catch (err) {
        sendError(res, err instanceof Error ? err.message : String(err))
      }
      return
    }

    // ── API: Export ZIP ─────────────────────────────────────────────────────
    if (req.method === 'POST' && pathname === '/api/export/zip') {
      try {
        const body = await parseJsonBody(req)
        const cards = store.getCards()
        let targetCards = cards.filter((c) => c.media && c.media.length > 0)
        if (Array.isArray(body.cardIds) && body.cardIds.length > 0) {
          targetCards = targetCards.filter((c) => body.cardIds.includes(c.id))
        }

        const entries: ZipEntry[] = []
        const manifest: Record<string, any>[] = []

        for (const card of targetCards) {
          if (!card.media) continue
          for (const m of card.media) {
            if (m.localPath && existsSync(m.localPath)) {
              try {
                const bytes = readFileSync(m.localPath)
                entries.push({ name: `media/${m.filename}`, data: bytes })

                // Add prompt text sidecar file
                const stem = m.filename.replace(/\.[^.]+$/, '')
                const sidecarText = `Title: ${card.title}\nStatus: ${card.status}\nModel/Skill: ${card.skillSlug || card.workflowSlug || 'default'}\nCreated: ${card.createdAt}\n\nPrompt:\n${card.prompt}\n\n${card.chain?.step2Prompt ? `Animation Prompt (Omni-Russ):\n${card.chain.step2Prompt}\n\n` : ''}Content Description:\n${card.contentDescription || ''}\n\nTags: ${(card.tags || []).join(', ')}\n`
                entries.push({
                  name: `prompts/${stem}_prompt.txt`,
                  data: Buffer.from(sidecarText, 'utf-8'),
                })

                manifest.push({
                  filename: m.filename,
                  title: card.title,
                  mediaType: m.mediaType,
                  prompt: card.prompt,
                  motionPrompt: card.chain?.step2Prompt,
                  contentDescription: card.contentDescription,
                  tags: card.tags,
                })
              } catch {
                /* skip file if read error */
              }
            }
          }
        }

        // Add manifest.json
        entries.push({
          name: 'manifest.json',
          data: Buffer.from(JSON.stringify(manifest, null, 2), 'utf-8'),
        })

        const zipBuf = createZipBuffer(entries)
        res.writeHead(200, {
          'Content-Type': 'application/zip',
          'Content-Disposition': `attachment; filename="renderflow_export_${Date.now()}.zip"`,
          'Content-Length': zipBuf.length,
        })
        res.end(zipBuf)
      } catch (err) {
        sendError(res, err instanceof Error ? err.message : String(err))
      }
      return
    }

    // ── API: Tunnel Control ─────────────────────────────────────────────────
    if (req.method === 'POST' && pathname === '/api/tunnel/start') {
      try {
        const activeUrl = await tunnel.start(port)
        const status = tunnel.getStatus()
        store.setTunnelState(status)
        broadcastEvent('tunnel-updated', status)
        sendJson(res, status)
      } catch (err) {
        sendError(res, err instanceof Error ? err.message : String(err))
      }
      return
    }

    if (req.method === 'POST' && pathname === '/api/tunnel/stop') {
      tunnel.stop()
      store.setTunnelState(tunnel.getStatus())
      broadcastEvent('tunnel-updated', tunnel.getStatus())
      sendJson(res, tunnel.getStatus())
      return
    }

    // ── Static Frontend Serving ─────────────────────────────────────────────
    let staticPath = pathname === '/' ? 'index.html' : pathname.replace(/^\//, '')
    let localFile = join(PUBLIC_DIR, staticPath)

    if (existsSync(localFile) && statSync(localFile).isFile()) {
      streamFileWithRanges(localFile, req, res)
      return
    }

    // Fallback to index.html for SPA routes
    const indexFile = join(PUBLIC_DIR, 'index.html')
    if (existsSync(indexFile)) {
      streamFileWithRanges(indexFile, req, res)
      return
    }

    res.writeHead(404, { 'Content-Type': 'text/plain' })
    res.end('Not Found')
  })

  return {
    server,
    store,
    worker,
    tunnel,
    start: () =>
      new Promise<number>((resolve, reject) => {
        let currentPort = port
        const maxAttempts = 10

        const tryListen = (p: number, attemptsLeft: number) => {
          const onError = (err: any) => {
            server.removeListener('error', onError)
            if (err.code === 'EADDRINUSE' && attemptsLeft > 0) {
              process.stdout.write(`  ⚠️  Port ${p} in use, trying ${p + 1}...\n`)
              tryListen(p + 1, attemptsLeft - 1)
            } else if (err.code === 'EADDRINUSE') {
              reject(new Error(`Port ${port} is already in use. Please specify another port with --port <number>.`))
            } else {
              reject(err)
            }
          }

          server.once('error', onError)
          server.listen(p, '0.0.0.0', () => {
            server.removeListener('error', onError)
            worker.start()
            resolve(p)
          })
        }

        tryListen(currentPort, maxAttempts)
      }),
    stop: () => {
      tunnel.stop()
      worker.stop()
      server.close()
    },
  }
}

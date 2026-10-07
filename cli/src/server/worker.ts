import { EventEmitter } from 'node:events'
import { basename, extname } from 'node:path'
import { KanbanStore, RENDERS_DIR } from './store.js'
import { RenderCard, RenderMediaItem } from './types.js'
import {
  submitRender,
  submitRenderRaw,
  submitSkill,
  invokeSkill,
  resolveFinalMedia,
  cancelRender,
  SourceMedia,
  ResolvedMedia,
  SubmitRenderResult,
} from '../client.js'
import { downloadFile } from '../output.js'
import { resolveMediaInput } from '../upload.js'

export class RenderWorker extends EventEmitter {
  private store: KanbanStore
  private isRunning = false
  private currentAbortController: AbortController | null = null
  private currentCard: RenderCard | null = null

  constructor(store: KanbanStore) {
    super()
    this.store = store
  }

  public start(): void {
    if (this.isRunning) return
    this.isRunning = true
    this.loop()
  }

  public stop(): void {
    this.isRunning = false
    this.cancelCurrent()
  }

  public notifyNewJob(): void {
    if (this.isRunning && !this.currentCard) {
      setImmediate(() => this.loop())
    }
  }

  public async cancelCurrent(): Promise<boolean> {
    if (this.currentAbortController) {
      this.currentAbortController.abort()
      if (this.currentCard?.renderHash) {
        await cancelRender(this.currentCard.renderHash).catch(() => {})
      }
      if (this.currentCard) {
        this.store.updateCard(this.currentCard.id, {
          status: 'failed',
          error: 'Render cancelled by user',
        })
        this.emit('card-updated', this.store.getCard(this.currentCard.id))
      }
      this.currentCard = null
      this.store.setActiveRender(null)
      return true
    }
    return false
  }

  private async loop(): Promise<void> {
    if (!this.isRunning) return

    const nextCard = this.store.getNextQueued()
    if (!nextCard) {
      this.store.setActiveRender(null)
      return
    }

    this.currentCard = nextCard
    this.store.setActiveRender(nextCard.id)

    try {
      await this.processCard(nextCard)
    } catch (err) {
      console.error(`Error processing card ${nextCard.id}:`, err)
      const errorMsg = err instanceof Error ? err.message : String(err)
      this.store.updateCard(nextCard.id, {
        status: 'failed',
        error: errorMsg,
      })
      this.store.incrementStats(false)
      this.emit('card-updated', this.store.getCard(nextCard.id))
    } finally {
      this.currentCard = null
      this.currentAbortController = null
      this.store.setActiveRender(null)
      if (this.isRunning) {
        setTimeout(() => this.loop(), 500)
      }
    }
  }

  private detectMediaType(filenameOrUrl: string, detectedType?: string | null): 'image' | 'video' | 'audio' | 'unknown' {
    if (detectedType) {
      if (detectedType.startsWith('video/')) return 'video'
      if (detectedType.startsWith('image/')) return 'image'
      if (detectedType.startsWith('audio/')) return 'audio'
    }
    const ext = extname(new URL(filenameOrUrl, 'https://dummy.local').pathname).toLowerCase()
    if (['.mp4', '.webm', '.mov', '.avi'].includes(ext)) return 'video'
    if (['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(ext)) return 'image'
    if (['.mp3', '.wav', '.ogg'].includes(ext)) return 'audio'
    return 'unknown'
  }

  private async processCard(card: RenderCard): Promise<void> {
    const isStep2 = card.chain?.enabled && card.chain.step === 2
    const targetStatus = isStep2 ? 'animating' : 'rendering'

    this.store.updateCard(card.id, {
      status: targetStatus,
      error: undefined,
      progress: {
        stage: isStep2 ? 'Starting Omni-Russ animation' : 'Starting image render',
        percent: 0,
        logs: [`[${new Date().toLocaleTimeString()}] Job started: ${card.title}`],
        startedAt: new Date().toISOString(),
      },
    })
    this.emit('card-updated', this.store.getCard(card.id))

    this.currentAbortController = new AbortController()
    const signal = this.currentAbortController.signal

    const onStreamEvent = (name: string, data: Record<string, unknown>) => {
      const liveCard = this.store.getCard(card.id)
      if (!liveCard || !liveCard.progress) return

      let stage = name
      let percent = liveCard.progress.percent ?? 0
      let etaSeconds = liveCard.progress.etaSeconds

      if (name === 'render_queued') {
        stage = 'Queued on server'
        if (data.render_hash) liveCard.renderHash = String(data.render_hash)
        if (typeof data.estimated_render_time === 'number') {
          etaSeconds = data.estimated_render_time
        }
      } else if (name === 'rendering_started') {
        stage = 'Rendering in progress'
        percent = 25
      } else if (name === 'progress' && typeof data.percent === 'number') {
        percent = data.percent
      } else if (name === 'rendering_done') {
        stage = 'Finalizing media'
        percent = 95
      }

      const logLine = `[${new Date().toLocaleTimeString()}] ${name}: ${JSON.stringify(data).slice(0, 140)}`
      const logs = [...(liveCard.progress.logs || []), logLine].slice(-40)

      this.store.updateCard(card.id, {
        renderHash: liveCard.renderHash,
        progress: {
          stage,
          percent,
          etaSeconds,
          logs,
          startedAt: liveCard.progress.startedAt,
        },
      })
      this.emit('render-progress', { cardId: card.id, stage, percent, logs })
    }

    let result: SubmitRenderResult

    // Handle Step 2 Animation (Image-to-Video via Omni-Russ)
    if (isStep2) {
      const sourceImage = card.chain?.sourceImageMedia || card.media?.find((m) => m.mediaType === 'image') || card.media?.[0]
      if (!sourceImage?.localPath) {
        throw new Error('Animation card does not have a source image to animate.')
      }

      const uploadedUrl = await resolveMediaInput(sourceImage.localPath)
      const sourceMedia: SourceMedia = { initImage: uploadedUrl }
      const skillSlug = card.chain?.step2Skill || card.skillSlug || 'omni-russ'

      result = await submitSkill(card.prompt, onStreamEvent, skillSlug, sourceMedia, signal)
    } else if (card.rawTelegramCommand || card.renderType === 'quick') {
      const cmd = card.rawTelegramCommand || card.prompt
      result = await submitRenderRaw(cmd, onStreamEvent, undefined, signal)
    } else if (card.renderType === 'skill' || card.skillSlug) {
      // First frame skill call (e.g. 'anima-v2' or 'krea2')
      const skillSlug = card.skillSlug || 'anima-v2'

      // Invoke skill directly to capture the generated workflow command!
      const invoked = await invokeSkill(card.prompt, skillSlug, undefined, signal)
      if (invoked.error) throw new Error(`Skill error: ${invoked.error}`)
      if (!invoked.command) throw new Error('Skill returned no command')

      let finalCommand = invoked.command

      // Apply /images:x and /size:x if requested
      const imageCount = card.chain?.imageCount || 6
      const size = card.chain?.size || '1024x704'

      if (!finalCommand.includes('/images:') && imageCount > 1) {
        finalCommand += ` /images:${imageCount}`
      }
      if (!finalCommand.includes('/size:')) {
        finalCommand += ` /size:${size}`
      }

      // Store the generated command on the card for quick review, copying, and cheap workflow reuse!
      this.store.updateCard(card.id, {
        generatedCommand: invoked.command,
        skillExplanation: invoked.explanation,
      })
      this.emit('card-updated', this.store.getCard(card.id))

      // Submit the generated command to render
      result = await submitRender(finalCommand, undefined, onStreamEvent, undefined, signal)
    } else {
      let renderPrompt = card.prompt
      if (card.chain?.imageCount && !renderPrompt.includes('/images:')) {
        renderPrompt += ` /images:${card.chain.imageCount}`
      }
      if (card.chain?.size && !renderPrompt.includes('/size:')) {
        renderPrompt += ` /size:${card.chain.size}`
      }
      result = await submitRender(renderPrompt, card.workflowSlug, onStreamEvent, undefined, signal)
    }

    // Resolve media
    const resolvedMedia: ResolvedMedia[] = await resolveFinalMedia(result)
    if (!resolvedMedia.length) {
      throw new Error(`Render finished with hash ${result.renderHash}, but no media was returned within timeout.`)
    }

    // Download media locally
    const downloadedItems: RenderMediaItem[] = []
    for (let i = 0; i < resolvedMedia.length; i++) {
      const m = resolvedMedia[i]
      const savedPath = await downloadFile(m.url, RENDERS_DIR, { mediaType: m.mediaType, index: i })
      const filename = basename(savedPath)
      const mediaType = this.detectMediaType(filename, m.mediaType)
      downloadedItems.push({
        url: `/api/media/${encodeURIComponent(filename)}`,
        localPath: savedPath,
        mediaType,
        filename,
        thumbnailUrl: m.thumbnailUrl ? `/api/media/${encodeURIComponent(filename)}` : undefined,
      })
    }

    // ── Check if Step 1 needs to Fan Out to Omni-Russ Animations! ───────────
    if (card.chain?.enabled && card.chain.step === 1) {
      const imageItems = downloadedItems.filter((m) => m.mediaType === 'image')

      if (imageItems.length > 0) {
        const step2Skill = card.chain.step2Skill || 'omni-russ'
        const fps = card.chain.fps || 24
        const length = card.chain.length || 144
        const size = card.chain.size || '1024x704'
        const baseMotionPrompt = card.chain.step2Prompt || 'integrated_multimodal_description: cinematic smooth camera motion, subtle organic movement\noverall_soundscape: ambient environmental sounds'

        // Determine prompts to issue (supports multiple prompt batches across the set of images)
        const motionPrompts = card.chain.step2Prompts && card.chain.step2Prompts.length > 0
          ? card.chain.step2Prompts
          : [baseMotionPrompt]

        const childCardIds: string[] = []

        for (const promptTemplate of motionPrompts) {
          for (let i = 0; i < imageItems.length; i++) {
            const currentImg = imageItems[i]
            let clipPrompt = promptTemplate.trim()

            // Dialogue Render Mode: append dialogue in quotes at the end!
            if (card.chain.isDialogue && card.chain.dialogueLines && card.chain.dialogueLines.length > 0) {
              const line = card.chain.dialogueLines[i % card.chain.dialogueLines.length].trim()
              const cleanQuote = line.replace(/^["']|["']$/g, '')
              clipPrompt = `${clipPrompt} "${cleanQuote}"`
            }

            // Append required render parameters (/fps /size /length)
            if (!clipPrompt.includes('/fps:')) clipPrompt += ` /fps:${fps}`
            if (!clipPrompt.includes('/size:')) clipPrompt += ` /size:${size}`
            if (!clipPrompt.includes('/length:')) clipPrompt += ` /length:${length}`

            const dialogueSnippet = card.chain.isDialogue && card.chain.dialogueLines?.[i]
              ? ` ("${card.chain.dialogueLines[i].replace(/^["']|["']$/g, '').slice(0, 24)}...")`
              : ''

            const childCard = this.store.addCard({
              title: `${card.title} - Clip ${i + 1}${dialogueSnippet}`,
              status: 'queued',
              prompt: clipPrompt,
              contentDescription: `Omni-Russ animation of Image ${i + 1} (${card.title}): ${clipPrompt.slice(0, 100)}`,
              renderType: 'skill',
              skillSlug: step2Skill,
              tags: [...(card.tags || []), 'omni-russ', 'animation', `clip-${i + 1}`],
              media: [currentImg], // keep reference to source image
              chain: {
                enabled: true,
                step: 2,
                step1Type: card.chain.step1Type,
                step2Type: 'skill',
                step2Skill,
                step2Prompt: clipPrompt,
                fps,
                length,
                size,
                parentCardId: card.id,
                sourceImageIndex: i + 1,
                sourceImageMedia: currentImg,
              },
            })

            childCardIds.push(childCard.id)
          }
        }

        // Move parent image card to review column (holding all generated images)
        this.store.updateCard(card.id, {
          status: 'review',
          renderHash: result.renderHash,
          media: downloadedItems,
          chain: {
            ...card.chain,
            childCardIds,
          },
          progress: {
            stage: `Generated ${imageItems.length} images; queued ${childCardIds.length} Omni-Russ animations`,
            percent: 100,
            logs: [
              ...(card.progress?.logs || []),
              `[${new Date().toLocaleTimeString()}] First frame batch complete: ${imageItems.length} images downloaded.`,
              `[${new Date().toLocaleTimeString()}] Fanned out ${childCardIds.length} animations to the queue targeting ${step2Skill}.`,
            ],
            startedAt: card.progress?.startedAt,
          },
        })
        this.store.incrementStats(true)
        this.emit('card-updated', this.store.getCard(card.id))

        // Notify worker to immediately continue processing the queued animation cards!
        this.notifyNewJob()
        return
      }
    }

    // Single / Completed Card
    const hasVideo = downloadedItems.some((m) => m.mediaType === 'video')
    const finalStatus = hasVideo ? 'done' : 'review'

    this.store.updateCard(card.id, {
      status: finalStatus,
      renderHash: result.renderHash,
      media: downloadedItems,
      progress: {
        stage: 'Complete',
        percent: 100,
        logs: [...(card.progress?.logs || []), `[${new Date().toLocaleTimeString()}] Finished successfully!`],
        startedAt: card.progress?.startedAt,
      },
    })
    this.store.incrementStats(true)
    this.emit('card-updated', this.store.getCard(card.id))
  }
}

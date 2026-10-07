import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import { RenderCard, WorkspaceState, CardStatus } from './types.js'

export const RENDERS_DIR = join(process.cwd(), 'renders')
export const REELS_DIR = join(RENDERS_DIR, 'reels')
const STORE_FILE = join(RENDERS_DIR, 'kanban-store.json')

export function ensureDirectories(): void {
  if (!existsSync(RENDERS_DIR)) mkdirSync(RENDERS_DIR, { recursive: true })
  if (!existsSync(REELS_DIR)) mkdirSync(REELS_DIR, { recursive: true })
}

/** Extracts a clean English summary from prompt text (strips /run:, /sampler:, etc.) */
export function extractCleanDescription(rawPrompt: string): string {
  let text = rawPrompt
    .replace(/^\/wf\s+/i, '')
    .replace(/^\/render\s+/i, '')
    .replace(/^\/quick\s+/i, '')
    .replace(/^\/q\s+/i, '')
    .replace(/\/run:[a-zA-Z0-9_-]+/g, '')
    .replace(/\/workflow:[a-zA-Z0-9_-]+/g, '')
    .replace(/\/skill:[a-zA-Z0-9_-]+/g, '')
    .replace(/\/size:\S+/g, '')
    .replace(/\/steps:\S+/g, '')
    .replace(/\/guidance:\S+/g, '')
    .replace(/\/sampler:\S+/g, '')
    .replace(/\/length:\S+/g, '')
    .replace(/\/fps:\S+/g, '')
    .replace(/\/seed:\S+/g, '')
    .replace(/#[a-zA-Z0-9_-]+/g, '')
    .replace(/\[[^\]]*\]/g, '') // remove negative prompt brackets
    .replace(/<[^>]+>/g, '') // remove concept tags
    .replace(/\s+/g, ' ')
    .trim()

  if (text.length > 200) {
    text = text.slice(0, 197) + '...'
  }
  return text || 'Visual render prompt'
}

export class KanbanStore {
  private cards: RenderCard[] = []
  private activeRenderId: string | null = null
  private tunnelState: WorkspaceState['tunnel'] = { active: false, url: null }
  private stats: WorkspaceState['stats'] = { totalRenders: 0, successfulRenders: 0, failedRenders: 0 }

  constructor() {
    ensureDirectories()
    this.load()
  }

  private load(): void {
    if (existsSync(STORE_FILE)) {
      try {
        const raw = readFileSync(STORE_FILE, 'utf-8')
        const data = JSON.parse(raw) as Partial<WorkspaceState>
        this.cards = Array.isArray(data.cards) ? data.cards : []
        this.stats = data.stats ?? this.stats

        // Reset any cards that were stuck in 'rendering' or 'animating' during a server restart
        for (const card of this.cards) {
          if (card.status === 'rendering') card.status = 'queued'
          if (card.status === 'animating') card.status = 'review'
        }
        if (this.cards.length > 0) {
          return
        }
      } catch (err) {
        console.error('Failed to read kanban-store.json, creating new store:', err)
      }
    }

    // Starter template cards
    this.cards = [
      {
        id: randomUUID(),
        title: 'Gothic Vampire Queen (6 Images ➔ Omni-Russ)',
        status: 'backlog',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        prompt: 'a gothic vampire queen sitting on an ornate obsidian throne /images:6 /size:1024x704',
        contentDescription: 'Gothic vampire queen sitting on an ornate obsidian throne in cathedral lighting',
        tags: ['anima-v2', 'vampire', 'batch-6'],
        renderType: 'skill',
        skillSlug: 'anima-v2',
        chain: {
          enabled: true,
          step: 1,
          step1Type: 'skill',
          step1Skill: 'anima-v2',
          imageCount: 6,
          size: '1024x704',
          step2Type: 'skill',
          step2Skill: 'omni-russ',
          fps: 24,
          length: 144,
          step2Prompt: 'integrated_multimodal_description: cinematic slow push-in shot, subtle organic breathing motion and atmospheric lighting\noverall_soundscape: ambient cathedral hum, soft breath',
        },
      },
      {
        id: randomUUID(),
        title: 'Cyberpunk Runner (Krea2)',
        status: 'backlog',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        prompt: 'cyberpunk street runner sprinting across rain-slicked rooftops /images:6 /size:1024x704',
        contentDescription: 'Cyberpunk street runner sprinting across rain-slicked rooftops at night',
        tags: ['krea2', 'cyberpunk', 'batch-6'],
        renderType: 'skill',
        skillSlug: 'krea2',
        chain: {
          enabled: true,
          step: 1,
          step1Type: 'skill',
          step1Skill: 'krea2',
          imageCount: 6,
          size: '1024x704',
          step2Type: 'skill',
          step2Skill: 'omni-russ',
          fps: 24,
          length: 144,
          step2Prompt: 'integrated_multimodal_description: dynamic tracking shot from side, rain droplets flying, neon reflections shifting rapidly\noverall_soundscape: heavy rain, footsteps splashing, distant sirens',
        },
      },
      {
        id: randomUUID(),
        title: 'Tavern Adventurers (Dialogue Mode ➔ Omni-Russ)',
        status: 'backlog',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        prompt: 'a cinematic shot of a warrior in a tavern talking intensely /images:6 /size:1024x704',
        contentDescription: 'Warrior in candlelit tavern speaking with intense expression',
        tags: ['anima-v2', 'dialogue', 'batch-6'],
        renderType: 'skill',
        skillSlug: 'anima-v2',
        chain: {
          enabled: true,
          step: 1,
          step1Type: 'skill',
          step1Skill: 'anima-v2',
          imageCount: 6,
          size: '1024x704',
          step2Type: 'skill',
          step2Skill: 'omni-russ',
          fps: 24,
          length: 144,
          isDialogue: true,
          dialogueLines: [
            '"I never thought we would actually find the legendary relic."',
            '"Did anyone else hear footsteps outside in the alley?"',
            '"Quiet down! You are going to draw every bounty hunter in the city."',
            '"Drink your mead, tomorrow we ride through the ash wastes."',
            '"Look at the medallion... it is beginning to glow."',
            '"Whatever happens tomorrow, we stand together."',
          ],
          step2Prompt: 'integrated_multimodal_description: character speaking directly facing camera, expressive mouth movement, subtle head tilt, warm candlelight\noverall_soundscape: quiet tavern atmosphere, crackling hearth',
        },
      },
    ]
    this.save()
  }

  public save(): void {
    try {
      const data: WorkspaceState = {
        cards: this.cards,
        activeRenderId: this.activeRenderId,
        tunnel: this.tunnelState,
        stats: this.stats,
      }
      writeFileSync(STORE_FILE, JSON.stringify(data, null, 2), 'utf-8')
    } catch (err) {
      console.error('Failed to save kanban-store.json:', err)
    }
  }

  public getState(): WorkspaceState {
    return {
      cards: this.cards,
      activeRenderId: this.activeRenderId,
      tunnel: this.tunnelState,
      stats: this.stats,
    }
  }

  public getCards(): RenderCard[] {
    return this.cards
  }

  public getCard(id: string): RenderCard | undefined {
    return this.cards.find((c) => c.id === id)
  }

  public addCard(params: Partial<RenderCard>): RenderCard {
    const prompt = params.prompt ?? params.rawTelegramCommand ?? ''
    const now = new Date().toISOString()
    const card: RenderCard = {
      id: randomUUID(),
      title: params.title || extractCleanDescription(prompt).slice(0, 45) || 'Untitled Render',
      status: params.status || 'queued',
      createdAt: now,
      updatedAt: now,
      prompt,
      negativePrompt: params.negativePrompt,
      tags: params.tags ?? [],
      contentDescription: params.contentDescription || extractCleanDescription(prompt),
      renderType: params.renderType || 'render',
      workflowSlug: params.workflowSlug,
      skillSlug: params.skillSlug,
      rawTelegramCommand: params.rawTelegramCommand,
      options: params.options,
      seed: params.seed,
      generatedCommand: params.generatedCommand,
      skillExplanation: params.skillExplanation,
      chain: params.chain,
      media: params.media ?? [],
    }

    this.cards.push(card)
    this.save()
    return card
  }

  public updateCard(id: string, updates: Partial<RenderCard>): RenderCard | undefined {
    const card = this.cards.find((c) => c.id === id)
    if (!card) return undefined

    Object.assign(card, updates, { updatedAt: new Date().toISOString() })
    if (updates.prompt && !updates.contentDescription) {
      card.contentDescription = extractCleanDescription(updates.prompt)
    }
    this.save()
    return card
  }

  public moveCard(id: string, newStatus: CardStatus): RenderCard | undefined {
    return this.updateCard(id, { status: newStatus })
  }

  public deleteCard(id: string): boolean {
    const idx = this.cards.findIndex((c) => c.id === id)
    if (idx === -1) return false
    this.cards.splice(idx, 1)
    if (this.activeRenderId === id) this.activeRenderId = null
    this.save()
    return true
  }

  public reorderQueue(orderedIds: string[]): void {
    const queuedCards = this.cards.filter((c) => c.status === 'queued')
    const otherCards = this.cards.filter((c) => c.status !== 'queued')

    const map = new Map(queuedCards.map((c) => [c.id, c]))
    const newQueued: RenderCard[] = []

    for (const id of orderedIds) {
      const card = map.get(id)
      if (card) {
        newQueued.push(card)
        map.delete(id)
      }
    }

    // append any missing queued cards
    for (const remaining of map.values()) {
      newQueued.push(remaining)
    }

    this.cards = [...otherCards, ...newQueued]
    this.save()
  }

  public getNextQueued(): RenderCard | undefined {
    return this.cards.find((c) => c.status === 'queued')
  }

  public setActiveRender(id: string | null): void {
    this.activeRenderId = id
  }

  public setTunnelState(tunnel: WorkspaceState['tunnel']): void {
    this.tunnelState = tunnel
  }

  public incrementStats(success: boolean): void {
    this.stats.totalRenders++
    if (success) {
      this.stats.successfulRenders++
    } else {
      this.stats.failedRenders++
    }
    this.save()
  }
}

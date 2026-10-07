export type CardStatus = 'backlog' | 'queued' | 'rendering' | 'review' | 'animating' | 'done' | 'failed'

export interface RenderMediaItem {
  url: string
  localPath?: string
  mediaType: 'image' | 'video' | 'audio' | 'unknown'
  filename: string
  thumbnailUrl?: string
}

export interface CardChainConfig {
  enabled: boolean
  step: 1 | 2
  step1Type: 'skill' | 'workflow' | 'render' | 'image'
  step1Skill?: string // 'anima-v2' (default) | 'krea2'
  step1Workflow?: string // 'anima-wai'
  imageCount?: number // e.g. 6 (adds /images:6)
  size?: string // default '1024x704'

  step2Type: 'animation' | 'skill'
  step2Skill: string // defaults to 'omni-russ'
  step2Workflow?: string
  step2Prompt: string // motion / animation prompt fed to omni-russ
  step2Prompts?: string[] // optional multiple motion prompts applied across the set
  fps?: number // default 24
  length?: number // default 144

  // Dialogue mode
  isDialogue?: boolean
  dialogueLines?: string[] // array of lines, matched 1-to-1 with images

  // Linkage for fan-out
  parentCardId?: string
  sourceImageIndex?: number
  sourceImageMedia?: RenderMediaItem
  childCardIds?: string[]
}

export interface RenderCard {
  id: string
  title: string
  status: CardStatus
  createdAt: string
  updatedAt: string

  // Prompt metadata
  prompt: string
  negativePrompt?: string
  tags?: string[]
  contentDescription?: string // clean English description for quick skimming

  // Render configuration
  renderType: 'render' | 'quick' | 'skill'
  workflowSlug?: string
  skillSlug?: string // e.g. 'anima-v2' | 'krea2' | 'omni-russ'
  rawTelegramCommand?: string
  options?: Record<string, string>
  seed?: string

  // Skill output caching (so skill prompt can be reused cheaply as a workflow!)
  generatedCommand?: string
  skillExplanation?: string

  // Chained workflow
  chain?: CardChainConfig

  // Execution state
  renderHash?: string
  progress?: {
    stage: string
    percent?: number
    etaSeconds?: number
    logs: string[]
    startedAt?: string
  }
  error?: string

  // Resulting media
  media?: RenderMediaItem[]
  selectedForReel?: boolean
}

export interface WorkspaceState {
  cards: RenderCard[]
  activeRenderId: string | null
  tunnel: {
    active: boolean
    url: string | null
    startedAt?: string
    error?: string
  }
  stats: {
    totalRenders: number
    successfulRenders: number
    failedRenders: number
  }
}

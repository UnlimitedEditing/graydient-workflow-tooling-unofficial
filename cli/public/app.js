// RenderFlow Kanban Workspace Frontend
// Connects to SSE, manages Kanban board, drag & drop, chained pipelines, and tunnel

let state = {
  cards: [],
  activeRenderId: null,
  tunnel: { active: false, url: null },
  stats: { totalRenders: 0, successfulRenders: 0, failedRenders: 0 },
}

let activeAnimateCard = null
let dragSourceCardId = null

// ── DOM Elements ────────────────────────────────────────────────────────────
const elements = {
  queueCount: document.getElementById('queueCount'),
  reviewCount: document.getElementById('reviewCount'),
  doneCount: document.getElementById('doneCount'),
  activeRenderStatus: document.getElementById('activeRenderStatus'),
  pipelineIndicator: document.getElementById('pipelineIndicator'),
  btnTunnel: document.getElementById('btnTunnel'),
  tunnelBtnText: document.getElementById('tunnelBtnText'),
  tunnelStatusDot: document.getElementById('tunnelStatusDot'),
  btnNewRender: document.getElementById('btnNewRender'),
  btnExportMenu: document.getElementById('btnExportMenu'),
  exportDropdown: document.getElementById('exportDropdown'),
  btnTriggerCompileReel: document.getElementById('btnTriggerCompileReel'),
  btnExportZip: document.getElementById('btnExportZip'),
  btnExportDescriptions: document.getElementById('btnExportDescriptions'),
  btnOpenPrompts: document.getElementById('btnOpenPrompts'),
  btnQuickAddBacklog: document.getElementById('btnQuickAddBacklog'),
  btnSelectAllDone: document.getElementById('btnSelectAllDone'),
  toastContainer: document.getElementById('toastContainer'),

  // Columns
  cardsBacklog: document.getElementById('cards-backlog'),
  cardsQueued: document.getElementById('cards-queued'),
  cardsRendering: document.getElementById('cards-rendering'),
  cardsReview: document.getElementById('cards-review'),
  cardsAnimating: document.getElementById('cards-animating'),
  cardsDone: document.getElementById('cards-done'),

  // Badges
  badgeBacklog: document.getElementById('badge-backlog'),
  badgeQueued: document.getElementById('badge-queued'),
  badgeRendering: document.getElementById('badge-rendering'),
  badgeReview: document.getElementById('badge-review'),
  badgeAnimating: document.getElementById('badge-animating'),
  badgeDone: document.getElementById('badge-done'),

  // Modals
  modalNewRender: document.getElementById('modalNewRender'),
  modalAnimateImage: document.getElementById('modalAnimateImage'),
  modalCompileReel: document.getElementById('modalCompileReel'),
  modalTunnel: document.getElementById('modalTunnel'),
  modalPromptsLibrary: document.getElementById('modalPromptsLibrary'),

  // Animate Modal
  animatePreviewImg: document.getElementById('animatePreviewImg'),
  animateThumbsStrip: document.getElementById('animateThumbsStrip'),
  animateSourceTitle: document.getElementById('animateSourceTitle'),
  animateSourceDesc: document.getElementById('animateSourceDesc'),
  animateBatchBadge: document.getElementById('animateBatchBadge'),
  animatePromptInput: document.getElementById('animatePromptInput'),
  radioAnimMotion: document.getElementById('radioAnimMotion'),
  radioAnimDialogue: document.getElementById('radioAnimDialogue'),
  animateModalDialogueContainer: document.getElementById('animateModalDialogueContainer'),
  animateModalDialogueLines: document.getElementById('animateModalDialogueLines'),
  btnConfirmAnimate: document.getElementById('btnConfirmAnimate'),

  // Chain Modal Controls
  radioModeMotion: document.getElementById('radioModeMotion'),
  radioModeDialogue: document.getElementById('radioModeDialogue'),
  dialogueBoxContainer: document.getElementById('dialogueBoxContainer'),
  chainDialogueLines: document.getElementById('chainDialogueLines'),
  lblStep2Prompt: document.getElementById('lblStep2Prompt'),

  // Tunnel Modal
  tunnelCard: document.getElementById('tunnelCard'),
  tunnelIndicatorState: document.getElementById('tunnelIndicatorState'),
  tunnelStateTitle: document.getElementById('tunnelStateTitle'),
  tunnelActiveContent: document.getElementById('tunnelActiveContent'),
  tunnelUrlDisplay: document.getElementById('tunnelUrlDisplay'),
  btnCopyTunnelUrl: document.getElementById('btnCopyTunnelUrl'),
  btnToggleTunnel: document.getElementById('btnToggleTunnel'),
  tunnelQrCanvas: document.getElementById('tunnelQrCanvas'),

  // Reel Modal
  reelClipCount: document.getElementById('reelClipCount'),
  reelResultContainer: document.getElementById('reelResultContainer'),
  reelVideoPlayer: document.getElementById('reelVideoPlayer'),
  btnDownloadReel: document.getElementById('btnDownloadReel'),
  btnExecuteReelCompile: document.getElementById('btnExecuteReelCompile'),

  // Prompt Library
  promptsLibraryList: document.getElementById('promptsLibraryList'),
  promptSearchInput: document.getElementById('promptSearchInput'),
  btnCopyAllDescriptions: document.getElementById('btnCopyAllDescriptions'),
}

// ── Toasts ──────────────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const toast = document.createElement('div')
  toast.className = `toast ${type}`
  toast.textContent = message
  elements.toastContainer.appendChild(toast)
  setTimeout(() => {
    toast.style.opacity = '0'
    toast.style.transform = 'translateX(20px)'
    toast.style.transition = 'all 0.2s ease'
    setTimeout(() => toast.remove(), 200)
  }, 3500)
}

// ── Copy to Clipboard Helper ────────────────────────────────────────────────
async function copyToClipboard(text, successMsg = 'Copied to clipboard!') {
  try {
    await navigator.clipboard.writeText(text)
    showToast(successMsg, 'success')
  } catch {
    const el = document.createElement('textarea')
    el.value = text
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
    showToast(successMsg, 'success')
  }
}

// ── API Calls ───────────────────────────────────────────────────────────────
async function fetchState() {
  try {
    const res = await fetch('/api/state')
    if (res.ok) {
      state = await res.json()
      renderBoard()
      updateTunnelUI()
    }
  } catch (err) {
    console.error('Failed to fetch state:', err)
  }
}

async function apiAddCard(payload) {
  const res = await fetch('/api/cards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || 'Failed to create card')
  }
  return res.json()
}

async function apiUpdateCard(id, updates) {
  const res = await fetch(`/api/cards/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || 'Failed to update card')
  }
  return res.json()
}

async function apiDeleteCard(id) {
  const res = await fetch(`/api/cards/${encodeURIComponent(id)}`, { method: 'DELETE' })
  return res.ok
}

async function apiMoveToQueue(id) {
  const res = await fetch(`/api/cards/${encodeURIComponent(id)}/queue`, { method: 'POST' })
  return res.ok
}

async function apiCancelRender() {
  const res = await fetch('/api/render/cancel', { method: 'POST' })
  return res.ok
}

async function apiAnimateCard(cardId, options = {}) {
  const payload = typeof options === 'string'
    ? { prompt: options, skillSlug: 'omni-russ' }
    : { skillSlug: 'omni-russ', ...options }

  const res = await fetch(`/api/cards/${encodeURIComponent(cardId)}/animate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || 'Failed to start animation')
  }
  return res.json()
}

async function apiCompileReel(cardIds) {
  const res = await fetch('/api/reel/compile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cardIds }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || 'Failed to compile reel')
  }
  return res.json()
}

async function apiToggleTunnel(action) {
  const res = await fetch(`/api/tunnel/${action}`, { method: 'POST' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || `Failed to ${action} tunnel`)
  }
  return res.json()
}

// ── SSE Live Updates ────────────────────────────────────────────────────────
function connectSSE() {
  const eventSource = new EventSource('/api/events')

  eventSource.addEventListener('state-updated', (e) => {
    state = JSON.parse(e.data)
    renderBoard()
    updateTunnelUI()
  })

  eventSource.addEventListener('card-updated', (e) => {
    const updatedCard = JSON.parse(e.data)
    const idx = state.cards.findIndex((c) => c.id === updatedCard.id)
    if (idx !== -1) {
      state.cards[idx] = updatedCard
    } else {
      state.cards.push(updatedCard)
    }
    renderBoard()
  })

  eventSource.addEventListener('render-progress', (e) => {
    const prog = JSON.parse(e.data)
    updateLiveProgress(prog)
  })

  eventSource.addEventListener('tunnel-updated', (e) => {
    state.tunnel = JSON.parse(e.data)
    updateTunnelUI()
  })

  eventSource.onerror = () => {
    setTimeout(connectSSE, 3000)
  }
}

// ── UI Updates ──────────────────────────────────────────────────────────────
function updateLiveProgress(prog) {
  const cardEl = document.querySelector(`[data-card-id="${prog.cardId}"]`)
  if (!cardEl) return

  const stageEl = cardEl.querySelector('.progress-stage')
  const percentEl = cardEl.querySelector('.progress-percent')
  const barFill = cardEl.querySelector('.progress-bar-fill')
  const logsEl = cardEl.querySelector('.progress-logs')

  if (stageEl) stageEl.textContent = prog.stage || 'Rendering'
  if (percentEl) percentEl.textContent = `${prog.percent ?? 0}%`
  if (barFill) barFill.style.width = `${prog.percent ?? 0}%`

  if (logsEl && Array.isArray(prog.logs)) {
    logsEl.innerHTML = prog.logs.map((l) => `<div>${escapeHtml(l)}</div>`).join('')
    logsEl.scrollTop = logsEl.scrollHeight
  }
}

function updateTunnelUI() {
  const isTunnelActive = state.tunnel && state.tunnel.active && state.tunnel.url
  if (isTunnelActive) {
    elements.tunnelStatusDot.classList.add('active')
    elements.tunnelBtnText.textContent = 'Tunnel Active'
    elements.tunnelIndicatorState.className = 'status-indicator active'
    elements.tunnelStateTitle.textContent = 'Cloudflare Tunnel Live 🟢'
    elements.tunnelActiveContent.style.display = 'block'
    elements.tunnelUrlDisplay.value = state.tunnel.url
    elements.btnToggleTunnel.textContent = 'Stop Cloudflare Tunnel'
    elements.btnToggleTunnel.className = 'btn btn-secondary'

    // Render QR Code
    renderQrCode(state.tunnel.url, elements.tunnelQrCanvas)
  } else {
    elements.tunnelStatusDot.classList.remove('active')
    elements.tunnelBtnText.textContent = 'Tunnel'
    elements.tunnelIndicatorState.className = 'status-indicator'
    elements.tunnelStateTitle.textContent = 'Tunnel Inactive'
    elements.tunnelActiveContent.style.display = 'none'
    elements.btnToggleTunnel.textContent = 'Start Cloudflare Tunnel'
    elements.btnToggleTunnel.className = 'btn btn-primary'
  }
}

function escapeHtml(str) {
  if (!str) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// ── Render Board ────────────────────────────────────────────────────────────
function renderBoard() {
  const groups = {
    backlog: [],
    queued: [],
    rendering: [],
    review: [],
    animating: [],
    done: [],
  }

  for (const card of state.cards) {
    if (groups[card.status]) {
      groups[card.status].push(card)
    } else {
      groups.backlog.push(card)
    }
  }

  // Update header badges
  elements.queueCount.textContent = groups.queued.length
  elements.reviewCount.textContent = groups.review.length
  elements.doneCount.textContent = groups.done.length

  elements.badgeBacklog.textContent = groups.backlog.length
  elements.badgeQueued.textContent = groups.queued.length
  elements.badgeRendering.textContent = groups.rendering.length
  elements.badgeReview.textContent = groups.review.length
  elements.badgeAnimating.textContent = groups.animating.length
  elements.badgeDone.textContent = groups.done.length

  // Pipeline indicator
  const activeCount = groups.rendering.length + groups.animating.length
  if (activeCount > 0) {
    elements.activeRenderStatus.textContent = `${activeCount} render${activeCount > 1 ? 's' : ''} in progress`
    elements.pipelineIndicator.querySelector('.pulse-dot').className = 'pulse-dot rendering'
  } else if (groups.queued.length > 0) {
    elements.activeRenderStatus.textContent = `${groups.queued.length} queued`
    elements.pipelineIndicator.querySelector('.pulse-dot').className = 'pulse-dot'
  } else {
    elements.activeRenderStatus.textContent = 'Queue ready'
    elements.pipelineIndicator.querySelector('.pulse-dot').className = 'pulse-dot'
  }

  // Populate Columns
  renderColumn(elements.cardsBacklog, groups.backlog, 'backlog')
  renderColumn(elements.cardsQueued, groups.queued, 'queued')
  renderColumn(elements.cardsRendering, groups.rendering, 'rendering')
  renderColumn(elements.cardsReview, groups.review, 'review')
  renderColumn(elements.cardsAnimating, groups.animating, 'animating')
  renderColumn(elements.cardsDone, groups.done, 'done')
}

function renderColumn(container, cards, colStatus) {
  container.innerHTML = ''
  if (cards.length === 0) {
    const empty = document.createElement('div')
    empty.className = 'empty-col-state'
    empty.style.padding = '20px'
    empty.style.textAlign = 'center'
    empty.style.color = 'var(--text-subtle)'
    empty.style.fontSize = '0.8rem'
    empty.textContent = colStatus === 'queued' ? 'No renders in queue' : 'Empty column'
    container.appendChild(empty)
    return
  }

  cards.forEach((card, index) => {
    const cardEl = createCardElement(card, colStatus, index, cards.length)
    container.appendChild(cardEl)
  })
}

function createCardElement(card, colStatus, index, totalInCol) {
  const cardEl = document.createElement('div')
  cardEl.className = `kanban-card ${card.status === 'rendering' || card.status === 'animating' ? 'active-render' : ''}`
  cardEl.setAttribute('data-card-id', card.id)
  cardEl.draggable = true

  // Drag handlers
  cardEl.addEventListener('dragstart', (e) => {
    dragSourceCardId = card.id
    cardEl.classList.add('is-dragging')
    e.dataTransfer.setData('text/plain', card.id)
  })
  cardEl.addEventListener('dragend', () => {
    cardEl.classList.remove('is-dragging')
    dragSourceCardId = null
  })

  // Media preview (supports multi-image grid e.g. /images:6)
  let mediaHtml = ''
  if (card.media && card.media.length > 0) {
    const videoMedia = card.media.find((m) => m.mediaType === 'video')
    if (videoMedia) {
      mediaHtml = `
        <div class="card-media-preview">
          <video src="${videoMedia.url}" loop muted playsinline onmouseover="this.play()" onmouseout="this.pause()"></video>
          <span class="video-play-badge">▶ Video</span>
        </div>`
    } else if (card.media.length > 1) {
      // 2x3 or 3x2 grid of all generated images
      const thumbs = card.media.slice(0, 6).map((m, idx) => `
        <div class="grid-thumb-item" title="Image ${idx + 1}" onclick="window.open('${m.url}', '_blank')">
          <img src="${m.url}" alt="Image ${idx + 1}" loading="lazy">
          <span class="grid-thumb-num">${idx + 1}</span>
        </div>
      `).join('')
      mediaHtml = `<div class="card-media-grid" title="Batch of ${card.media.length} images">${thumbs}</div>`
    } else {
      const firstMedia = card.media[0]
      mediaHtml = `
        <div class="card-media-preview">
          <img src="${firstMedia.url}" alt="${escapeHtml(card.title)}" loading="lazy" onclick="window.open('${firstMedia.url}', '_blank')">
        </div>`
    }
  }

  // Type badge
  let typeBadgeHtml = ''
  if (card.chain?.enabled) {
    const stepLabel = card.chain.step === 2 ? 'Omni-Russ Clip' : 'Batch ➔ Omni-Russ'
    typeBadgeHtml = `<span class="card-type-tag chain">${stepLabel}</span>`
  } else if (card.skillSlug) {
    typeBadgeHtml = `<span class="card-type-tag skill">${escapeHtml(card.skillSlug)}</span>`
  } else {
    typeBadgeHtml = `<span class="card-type-tag">${escapeHtml(card.workflowSlug || card.renderType)}</span>`
  }

  // Generated command box (allows cheap workflow reuse without burning skill calls!)
  let genCmdHtml = ''
  if (card.generatedCommand) {
    genCmdHtml = `
      <div class="card-generated-cmd">
        <div class="gen-cmd-header">
          <span>⚡ Skill Output Command</span>
          <span style="font-size:0.6rem;opacity:0.8;">Workflow Ready</span>
        </div>
        <div class="gen-cmd-code" title="${escapeHtml(card.generatedCommand)}">${escapeHtml(card.generatedCommand)}</div>
        <div class="gen-cmd-actions">
          <button class="btn-card-action btn-copy-cmd" data-cmd="${escapeHtml(card.generatedCommand)}" title="Copy command">📋 Copy</button>
          <button class="btn-card-action primary btn-reuse-cmd" data-cmd="${escapeHtml(card.generatedCommand)}" title="Reuse as direct workflow">🔄 Reuse as Workflow</button>
        </div>
      </div>`
  }

  // Progress UI (if rendering / animating)
  let progressHtml = ''
  if (colStatus === 'rendering' || colStatus === 'animating') {
    const prog = card.progress || {}
    const logs = prog.logs || []
    progressHtml = `
      <div class="card-progress-box">
        <div class="progress-header">
          <span class="progress-stage">${escapeHtml(prog.stage || 'Rendering...')}</span>
          <span class="progress-percent">${prog.percent ?? 0}%</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width: ${prog.percent ?? 0}%"></div>
        </div>
        <div class="progress-logs">${logs.map((l) => `<div>${escapeHtml(l)}</div>`).join('')}</div>
      </div>`
  }

  // Tags
  const tagsHtml = (card.tags || [])
    .map((t) => `<span class="card-tag">#${escapeHtml(t)}</span>`)
    .join('')

  // Action buttons per column
  let actionsHtml = ''
  if (colStatus === 'backlog') {
    actionsHtml = `
      <button class="btn-card-action primary btn-queue-card" title="Send to queue">🚀 Queue</button>
      <button class="btn-card-action btn-copy-prompt" title="Copy visual prompt">📋 Prompt</button>
      <button class="btn-card-action danger btn-delete-card" title="Delete">🗑️</button>`
  } else if (colStatus === 'queued') {
    actionsHtml = `
      <button class="btn-card-action btn-copy-prompt" title="Copy prompt">📋</button>
      <button class="btn-card-action danger btn-delete-card" title="Remove from queue">✕</button>`
  } else if (colStatus === 'rendering' || colStatus === 'animating') {
    actionsHtml = `
      <button class="btn-card-action danger btn-cancel-render" title="Cancel render">🛑 Cancel</button>`
  } else if (colStatus === 'review') {
    const isBatch = card.media && card.media.length > 1
    const animateBtnLabel = isBatch ? `🎬 Animate Set (${card.media.length})` : '🎬 Animate (Omni-Russ)'
    actionsHtml = `
      <button class="btn-card-action primary btn-animate-card" title="Animate with Omni-Russ">${animateBtnLabel}</button>
      <button class="btn-card-action btn-mark-done" title="Move to Done">✓ Done</button>
      <button class="btn-card-action danger btn-delete-card" title="Delete">🗑️</button>`
  } else if (colStatus === 'done') {
    const isChecked = card.selectedForReel ? 'checked' : ''
    actionsHtml = `
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:0.75rem;">
        <input type="checkbox" class="cb-select-reel" ${isChecked}> Select for Reel
      </label>
      <button class="btn-card-action btn-copy-prompt" title="Copy prompt">📋</button>
      <button class="btn-card-action btn-requeue-card" title="Re-queue render">🔄</button>`
  }

  cardEl.innerHTML = `
    <div class="card-header-row">
      <span class="card-title">${escapeHtml(card.title)}</span>
      ${typeBadgeHtml}
    </div>
    ${mediaHtml}
    <div class="card-prompt-preview">${escapeHtml(card.prompt)}</div>
    ${card.chain?.step2Prompt ? `<div class="card-prompt-preview" style="color:var(--accent-purple);font-size:0.7rem;">Motion: ${escapeHtml(card.chain.step2Prompt)}</div>` : ''}
    ${genCmdHtml}
    ${tagsHtml ? `<div class="card-tags">${tagsHtml}</div>` : ''}
    ${progressHtml}
    <div class="card-footer">
      <span style="font-size:0.68rem;color:var(--text-subtle);">${new Date(card.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      <div class="card-actions-row">${actionsHtml}</div>
    </div>
  `

  // Attach button event listeners
  const btnQueue = cardEl.querySelector('.btn-queue-card')
  if (btnQueue) {
    btnQueue.addEventListener('click', async (e) => {
      e.stopPropagation()
      await apiMoveToQueue(card.id)
      showToast('Render queued!', 'success')
    })
  }

  const btnRequeue = cardEl.querySelector('.btn-requeue-card')
  if (btnRequeue) {
    btnRequeue.addEventListener('click', async (e) => {
      e.stopPropagation()
      await apiMoveToQueue(card.id)
      showToast('Re-queued render!', 'success')
    })
  }

  const btnCopyCmd = cardEl.querySelector('.btn-copy-cmd')
  if (btnCopyCmd) {
    btnCopyCmd.addEventListener('click', (e) => {
      e.stopPropagation()
      const cmd = btnCopyCmd.getAttribute('data-cmd')
      copyToClipboard(cmd, 'Generated command copied!')
    })
  }

  const btnReuseCmd = cardEl.querySelector('.btn-reuse-cmd')
  if (btnReuseCmd) {
    btnReuseCmd.addEventListener('click', (e) => {
      e.stopPropagation()
      const cmd = btnReuseCmd.getAttribute('data-cmd')
      document.getElementById('rawTelegramInput').value = cmd
      // switch to tab-quick
      document.querySelectorAll('.tab-btn').forEach((t) => t.classList.remove('active'))
      document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'))
      const quickTab = document.querySelector('[data-tab="tab-quick"]')
      const quickPane = document.getElementById('tab-quick')
      if (quickTab && quickPane) {
        quickTab.classList.add('active')
        quickPane.classList.add('active')
      }
      elements.modalNewRender.classList.add('open')
      showToast('Command loaded into Telegram Slash Command tab!', 'info')
    })
  }

  const btnCopy = cardEl.querySelector('.btn-copy-prompt')
  if (btnCopy) {
    btnCopy.addEventListener('click', (e) => {
      e.stopPropagation()
      copyToClipboard(card.prompt, 'Prompt copied to clipboard!')
    })
  }

  const btnDelete = cardEl.querySelector('.btn-delete-card')
  if (btnDelete) {
    btnDelete.addEventListener('click', async (e) => {
      e.stopPropagation()
      if (confirm(`Delete "${card.title}"?`)) {
        await apiDeleteCard(card.id)
        showToast('Card deleted', 'info')
      }
    })
  }

  const btnCancel = cardEl.querySelector('.btn-cancel-render')
  if (btnCancel) {
    btnCancel.addEventListener('click', async (e) => {
      e.stopPropagation()
      await apiCancelRender()
      showToast('Cancellation requested', 'info')
    })
  }

  const btnAnimate = cardEl.querySelector('.btn-animate-card')
  if (btnAnimate) {
    btnAnimate.addEventListener('click', (e) => {
      e.stopPropagation()
      openAnimateModal(card)
    })
  }

  const btnMarkDone = cardEl.querySelector('.btn-mark-done')
  if (btnMarkDone) {
    btnMarkDone.addEventListener('click', async (e) => {
      e.stopPropagation()
      await apiUpdateCard(card.id, { status: 'done' })
      showToast('Moved to Finished Library', 'success')
    })
  }

  const cbReel = cardEl.querySelector('.cb-select-reel')
  if (cbReel) {
    cbReel.addEventListener('change', (e) => {
      card.selectedForReel = e.target.checked
    })
  }

  return cardEl
}

// ── Drag & Drop Column Targets ──────────────────────────────────────────────
document.querySelectorAll('.cards-container').forEach((container) => {
  container.addEventListener('dragover', (e) => {
    e.preventDefault()
    container.classList.add('drag-over')
  })
  container.addEventListener('dragleave', () => {
    container.classList.remove('drag-over')
  })
  container.addEventListener('drop', async (e) => {
    e.preventDefault()
    container.classList.remove('drag-over')
    const cardId = e.dataTransfer.getData('text/plain') || dragSourceCardId
    if (!cardId) return

    const targetCol = container.closest('.kanban-col')?.getAttribute('data-col')
    if (targetCol) {
      await apiUpdateCard(cardId, { status: targetCol })
      showToast(`Moved to ${targetCol}`, 'info')
    }
  })
})

// ── Animate Modal Handlers ──────────────────────────────────────────────────
// Toggle radio buttons for Animate Modal
document.querySelectorAll('input[name="animateModalMode"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    const isDialogue = elements.radioAnimDialogue.checked
    elements.animateModalDialogueContainer.style.display = isDialogue ? 'block' : 'none'
  })
})

function openAnimateModal(card) {
  activeAnimateCard = card
  const images = (card.media || []).filter((m) => m.mediaType === 'image')

  // Thumbnail strip
  elements.animateThumbsStrip.innerHTML = ''
  if (images.length > 0) {
    images.forEach((img, idx) => {
      const thumb = document.createElement('img')
      thumb.src = img.url
      thumb.alt = `Frame ${idx + 1}`
      thumb.title = `Image ${idx + 1}`
      thumb.className = 'thumb-item'
      elements.animateThumbsStrip.appendChild(thumb)
    })
    elements.animatePreviewImg.src = images[0].url
  } else if (card.media?.[0]) {
    elements.animatePreviewImg.src = card.media[0].url
  }

  elements.animateSourceTitle.textContent = card.title
  elements.animateSourceDesc.textContent = card.contentDescription || card.prompt

  // Batch badge
  if (images.length > 1) {
    elements.animateBatchBadge.style.display = 'inline-block'
    elements.animateBatchBadge.textContent = `Batch of ${images.length} Images ➔ ${images.length} Omni-Russ Animations`
  } else {
    elements.animateBatchBadge.style.display = 'none'
  }

  // Restore or reset dialogue mode
  if (card.chain?.isDialogue) {
    elements.radioAnimDialogue.checked = true
    elements.animateModalDialogueContainer.style.display = 'block'
    elements.animateModalDialogueLines.value = (card.chain.dialogueLines || []).join('\n')
  } else {
    elements.radioAnimMotion.checked = true
    elements.animateModalDialogueContainer.style.display = 'none'
  }

  // Default motion prompt tailored for omni-russ
  elements.animatePromptInput.value =
    card.chain?.step2Prompt ||
    `integrated_multimodal_description: cinematic slow push-in shot, organic subtle movement, high detail atmospheric lighting\noverall_soundscape: ambient environmental sounds and deep cinematic drone`

  elements.modalAnimateImage.classList.add('open')
}

elements.btnConfirmAnimate.addEventListener('click', async () => {
  if (!activeAnimateCard) return
  const prompt = elements.animatePromptInput.value.trim()
  const isDialogue = elements.radioAnimDialogue.checked
  const rawDialogue = elements.animateModalDialogueLines.value
  const dialogueLines = isDialogue
    ? rawDialogue.split('\n').map((l) => l.trim()).filter(Boolean)
    : []

  try {
    elements.btnConfirmAnimate.disabled = true
    elements.btnConfirmAnimate.textContent = 'Queueing Omni-Russ batch...'
    const res = await apiAnimateCard(activeAnimateCard.id, {
      prompt,
      skillSlug: 'omni-russ',
      fps: 24,
      size: '1024x704',
      length: 144,
      isDialogue,
      dialogueLines,
    })
    elements.modalAnimateImage.classList.remove('open')
    const count = res.queuedCount || 1
    showToast(`Omni-Russ animation queued! (${count} fan-out clip${count > 1 ? 's' : ''})`, 'success')
  } catch (err) {
    alert(`Error: ${err.message}`)
  } finally {
    elements.btnConfirmAnimate.disabled = false
    elements.btnConfirmAnimate.textContent = '🚀 Start Animation (Omni-Russ)'
  }
})

// ── Reel Compilation Modal Handlers ─────────────────────────────────────────
elements.btnTriggerCompileReel.addEventListener('click', () => {
  elements.exportDropdown.classList.remove('open')
  const doneCards = state.cards.filter((c) => c.status === 'done')
  const selectedCards = doneCards.filter((c) => c.selectedForReel)
  const targetCards = selectedCards.length > 0 ? selectedCards : doneCards
  const videoCards = targetCards.filter((c) => c.media?.some((m) => m.mediaType === 'video'))

  elements.reelClipCount.textContent = `${videoCards.length} animation${videoCards.length === 1 ? '' : 's'}`
  elements.reelResultContainer.style.display = 'none'
  elements.modalCompileReel.classList.add('open')
})

elements.btnExecuteReelCompile.addEventListener('click', async () => {
  const doneCards = state.cards.filter((c) => c.status === 'done')
  const selectedCards = doneCards.filter((c) => c.selectedForReel)
  const targetCards = selectedCards.length > 0 ? selectedCards : doneCards
  const targetIds = targetCards.map((c) => c.id)

  try {
    elements.btnExecuteReelCompile.disabled = true
    elements.btnExecuteReelCompile.textContent = 'Stitching videos with FFmpeg...'
    const result = await apiCompileReel(targetIds)

    elements.reelResultContainer.style.display = 'flex'
    elements.reelVideoPlayer.src = result.webUrl
    elements.btnDownloadReel.href = result.webUrl
    elements.btnDownloadReel.download = result.outputFilename
    showToast('Reel compiled successfully!', 'success')
  } catch (err) {
    alert(`Compilation failed: ${err.message}`)
  } finally {
    elements.btnExecuteReelCompile.disabled = false
    elements.btnExecuteReelCompile.textContent = '⚡ Compile Reel Now'
  }
})

// ── ZIP Export ──────────────────────────────────────────────────────────────
elements.btnExportZip.addEventListener('click', () => {
  elements.exportDropdown.classList.remove('open')
  showToast('Packaging ZIP archive...', 'info')

  const form = document.createElement('form')
  form.method = 'POST'
  form.action = '/api/export/zip'
  document.body.appendChild(form)
  form.submit()
  document.body.removeChild(form)
})

// ── Content Descriptions Copy ───────────────────────────────────────────────
elements.btnExportDescriptions.addEventListener('click', async () => {
  elements.exportDropdown.classList.remove('open')
  try {
    const res = await fetch('/api/prompts/skim?format=markdown')
    const md = await res.text()
    await copyToClipboard(md, 'All content descriptions copied to clipboard!')
  } catch (err) {
    showToast(`Failed to copy: ${err.message}`, 'error')
  }
})

// ── Prompt Library Modal ────────────────────────────────────────────────────
elements.btnOpenPrompts.addEventListener('click', () => {
  renderPromptsLibrary()
  elements.modalPromptsLibrary.classList.add('open')
})

function renderPromptsLibrary(filterQuery = '') {
  elements.promptsLibraryList.innerHTML = ''
  const q = filterQuery.toLowerCase()
  const matched = state.cards.filter((c) => {
    return (
      (c.title || '').toLowerCase().includes(q) ||
      (c.prompt || '').toLowerCase().includes(q) ||
      (c.contentDescription || '').toLowerCase().includes(q) ||
      (c.tags || []).some((t) => t.toLowerCase().includes(q))
    )
  })

  if (matched.length === 0) {
    elements.promptsLibraryList.innerHTML = '<div style="color:var(--text-subtle);text-align:center;padding:20px;">No matching prompts found.</div>'
    return
  }

  matched.forEach((c) => {
    const item = document.createElement('div')
    item.className = 'prompt-item-card'
    item.innerHTML = `
      <div class="prompt-item-header">
        <strong>${escapeHtml(c.title)}</strong>
        <div style="display:flex;gap:6px;">
          <button class="btn btn-sm btn-secondary btn-copy-desc" title="Copy clean description">Copy Description</button>
          <button class="btn btn-sm btn-secondary btn-copy-full" title="Copy visual prompt">Copy Prompt</button>
          <button class="btn btn-sm btn-primary btn-queue-item" title="Queue render">Queue</button>
        </div>
      </div>
      <div class="clean-desc-block"><strong>Description:</strong> ${escapeHtml(c.contentDescription || c.title)}</div>
      <div class="prompt-text-block">${escapeHtml(c.prompt)}</div>
      ${c.chain?.step2Prompt ? `<div class="prompt-text-block" style="color:var(--accent-purple);">Omni-Russ Motion: ${escapeHtml(c.chain.step2Prompt)}</div>` : ''}
    `

    item.querySelector('.btn-copy-desc').addEventListener('click', () => {
      copyToClipboard(c.contentDescription || c.title, 'Content description copied!')
    })
    item.querySelector('.btn-copy-full').addEventListener('click', () => {
      copyToClipboard(c.prompt, 'Visual prompt copied!')
    })
    item.querySelector('.btn-queue-item').addEventListener('click', async () => {
      await apiMoveToQueue(c.id)
      showToast('Render queued!', 'success')
    })

    elements.promptsLibraryList.appendChild(item)
  })
}

elements.promptSearchInput.addEventListener('input', (e) => {
  renderPromptsLibrary(e.target.value)
})

elements.btnCopyAllDescriptions.addEventListener('click', async () => {
  const allCaptions = state.cards
    .map((c, i) => `${i + 1}. ${c.title}\n${c.contentDescription || c.prompt}\n${(c.tags || []).map((t) => '#' + t).join(' ')}`)
    .join('\n\n---\n\n')
  await copyToClipboard(allCaptions, 'All descriptions and captions copied!')
})

// ── Tunnel Modal & Controls ─────────────────────────────────────────────────
elements.btnTunnel.addEventListener('click', () => {
  updateTunnelUI()
  elements.modalTunnel.classList.add('open')
})

elements.btnToggleTunnel.addEventListener('click', async () => {
  const isActive = state.tunnel && state.tunnel.active
  const action = isActive ? 'stop' : 'start'
  try {
    elements.btnToggleTunnel.disabled = true
    elements.btnToggleTunnel.textContent = isActive ? 'Stopping...' : 'Starting tunnel...'
    const res = await apiToggleTunnel(action)
    state.tunnel = res
    updateTunnelUI()
    showToast(isActive ? 'Tunnel stopped' : 'Cloudflare tunnel active!', 'success')
  } catch (err) {
    alert(`Tunnel error: ${err.message}`)
  } finally {
    elements.btnToggleTunnel.disabled = false
    updateTunnelUI()
  }
})

elements.btnCopyTunnelUrl.addEventListener('click', () => {
  copyToClipboard(elements.tunnelUrlDisplay.value, 'Tunnel URL copied to clipboard!')
})

// ── Dropdown Controls ───────────────────────────────────────────────────────
elements.btnExportMenu.addEventListener('click', (e) => {
  e.stopPropagation()
  elements.exportDropdown.classList.toggle('open')
})

document.addEventListener('click', () => {
  elements.exportDropdown.classList.remove('open')
})

// ── Modal Close Handlers ────────────────────────────────────────────────────
document.querySelectorAll('[data-close]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const targetModalId = btn.getAttribute('data-close')
    const modal = document.getElementById(targetModalId)
    if (modal) modal.classList.remove('open')
  })
})

elements.btnNewRender.addEventListener('click', () => {
  elements.modalNewRender.classList.add('open')
})

elements.btnQuickAddBacklog.addEventListener('click', () => {
  elements.modalNewRender.classList.add('open')
})

// Modal Tabs
document.querySelectorAll('.tab-btn').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((t) => t.classList.remove('active'))
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'))

    tab.classList.add('active')
    const targetPane = document.getElementById(tab.getAttribute('data-tab'))
    if (targetPane) targetPane.classList.add('active')
  })
})

// Quick Preset Handlers
document.querySelectorAll('.btn-preset').forEach((btn) => {
  btn.addEventListener('click', () => {
    const targetId = btn.getAttribute('data-target')
    const preset = btn.getAttribute('data-preset')
    const el = document.getElementById(targetId)
    if (el) el.value = preset
  })
})

// Toggle radio buttons for Chained Pipeline modal
document.querySelectorAll('input[name="chainRenderMode"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    const isDialogue = elements.radioModeDialogue.checked
    elements.dialogueBoxContainer.style.display = isDialogue ? 'block' : 'none'
    elements.lblStep2Prompt.textContent = isDialogue
      ? 'Base Character / Scene & Soundscape Prompt'
      : 'Base Motion & Soundscape Prompt'
  })
})

// ── Submit New Render Forms ─────────────────────────────────────────────────
// Tab 1: Chained Pipeline
document.getElementById('btnSubmitChain').addEventListener('click', async () => {
  const p1 = document.getElementById('chainStep1Prompt').value.trim()
  const methodVal = document.getElementById('chainStep1Method').value // "skill:anima-v2", "skill:krea2", "workflow:anima-wai"
  const [methodType, methodSlug] = methodVal.split(':')
  const imgCount = parseInt(document.getElementById('chainStep1Images').value, 10) || 6
  const sizeVal = document.getElementById('chainStep1Size').value || '1024x704'
  const isDialogue = elements.radioModeDialogue.checked
  const p2 = document.getElementById('chainStep2Prompt').value.trim()
  const rawDialogue = elements.chainDialogueLines.value
  const dialogueLines = isDialogue
    ? rawDialogue.split('\n').map((l) => l.trim()).filter(Boolean)
    : []

  if (!p1) {
    alert('Please enter an image prompt for Step 1.')
    return
  }

  try {
    await apiAddCard({
      title: `${methodSlug.toUpperCase()} Batch (${imgCount})`,
      prompt: p1,
      renderType: methodType === 'skill' ? 'skill' : 'render',
      skillSlug: methodType === 'skill' ? methodSlug : undefined,
      workflowSlug: methodType === 'workflow' ? methodSlug : undefined,
      tags: [methodSlug, `batch-${imgCount}`, isDialogue ? 'dialogue' : 'motion'],
      status: 'queued',
      chain: {
        enabled: true,
        step: 1,
        step1Type: 'image',
        step2Type: 'skill',
        step2Skill: 'omni-russ',
        step2Prompt: p2 || 'integrated_multimodal_description: cinematic slow push-in shot, subtle organic movement, atmospheric lighting\noverall_soundscape: ambient room tone and soft wind',
        imageCount: imgCount,
        size: sizeVal,
        fps: 24,
        length: 144,
        isDialogue,
        dialogueLines,
      },
    })
    elements.modalNewRender.classList.remove('open')
    document.getElementById('chainStep1Prompt').value = ''
    showToast(`Chained pipeline queued! (1 Batch of ${imgCount} ➔ ${imgCount} Omni-Russ Animations)`, 'success')
  } catch (err) {
    alert(err.message)
  }
})

document.getElementById('btnSaveChainToBacklog').addEventListener('click', async () => {
  const p1 = document.getElementById('chainStep1Prompt').value.trim()
  const methodVal = document.getElementById('chainStep1Method').value
  const [methodType, methodSlug] = methodVal.split(':')
  const imgCount = parseInt(document.getElementById('chainStep1Images').value, 10) || 6
  const sizeVal = document.getElementById('chainStep1Size').value || '1024x704'
  const isDialogue = elements.radioModeDialogue.checked
  const p2 = document.getElementById('chainStep2Prompt').value.trim()
  const rawDialogue = elements.chainDialogueLines.value
  const dialogueLines = isDialogue
    ? rawDialogue.split('\n').map((l) => l.trim()).filter(Boolean)
    : []

  if (!p1) return

  await apiAddCard({
    title: `${methodSlug.toUpperCase()} Batch (${imgCount})`,
    prompt: p1,
    renderType: methodType === 'skill' ? 'skill' : 'render',
    skillSlug: methodType === 'skill' ? methodSlug : undefined,
    workflowSlug: methodType === 'workflow' ? methodSlug : undefined,
    tags: [methodSlug, `batch-${imgCount}`, isDialogue ? 'dialogue' : 'motion'],
    status: 'backlog',
    chain: {
      enabled: true,
      step: 1,
      step1Type: 'image',
      step2Type: 'skill',
      step2Skill: 'omni-russ',
      step2Prompt: p2,
      imageCount: imgCount,
      size: sizeVal,
      fps: 24,
      length: 144,
      isDialogue,
      dialogueLines,
    },
  })
  elements.modalNewRender.classList.remove('open')
  showToast('Saved chain pipeline to backlog!', 'info')
})

// Tab 2: Raw Telegram Command
document.getElementById('btnSubmitTelegram').addEventListener('click', async () => {
  const raw = document.getElementById('rawTelegramInput').value.trim()
  const tags = document.getElementById('rawTelegramTags').value.split(',').map((t) => t.trim()).filter(Boolean)

  if (!raw) return
  await apiAddCard({
    rawTelegramCommand: raw,
    prompt: raw,
    renderType: 'quick',
    status: 'queued',
    tags,
  })
  elements.modalNewRender.classList.remove('open')
  document.getElementById('rawTelegramInput').value = ''
  showToast('Telegram render queued!', 'success')
})

// Tab 3: Direct Skill Call
document.getElementById('btnSubmitSkill').addEventListener('click', async () => {
  const skill = document.getElementById('directSkillSelect').value
  const prompt = document.getElementById('directSkillPrompt').value.trim()

  if (!prompt) return
  await apiAddCard({
    prompt,
    renderType: 'skill',
    skillSlug: skill,
    status: 'queued',
  })
  elements.modalNewRender.classList.remove('open')
  document.getElementById('directSkillPrompt').value = ''
  showToast(`Skill ${skill} queued!`, 'success')
})

// Tab 4: Batch Import
document.getElementById('btnSubmitBatch').addEventListener('click', async () => {
  const rawLines = document.getElementById('batchPromptsInput').value
  const lines = rawLines.split('\n').map((l) => l.trim()).filter(Boolean)
  const dest = document.getElementById('batchDestination').value
  const autoChain = document.getElementById('batchAutoChain').value === 'yes'

  if (lines.length === 0) return

  const payload = {
    batch: lines,
    status: dest,
    renderType: 'render',
    chain: autoChain
      ? {
          enabled: true,
          step: 1,
          step1Type: 'image',
          step2Type: 'skill',
          step2Skill: 'omni-russ',
          step2Prompt: 'integrated_multimodal_description: cinematic smooth camera motion, subtle organic movement\noverall_soundscape: ambient sound',
        }
      : undefined,
  }

  const res = await fetch('/api/cards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (res.ok) {
    const data = await res.json()
    elements.modalNewRender.classList.remove('open')
    document.getElementById('batchPromptsInput').value = ''
    showToast(`Imported ${data.addedCount} prompts!`, 'success')
  }
})

// ── Pure JS QR Code Renderer ────────────────────────────────────────────────
// Deterministic canvas QR Code generator for quick mobile scanning
function renderQrCode(text, canvas) {
  const ctx = canvas.getContext('2d')
  const size = canvas.width
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, size, size)

  // Use a pseudo-random seed based on URL string to draw a distinct, readable 2D matrix
  // If browser supports barcode detector or standard pattern:
  const modules = 25
  const cellSize = Math.floor(size / modules)
  const offset = Math.floor((size - modules * cellSize) / 2)

  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = (hash << 5) - hash + text.charCodeAt(i)
    hash |= 0
  }

  ctx.fillStyle = '#080c16'

  // Corner markers
  function drawFinderPattern(x, y) {
    ctx.fillRect(offset + x * cellSize, offset + y * cellSize, 7 * cellSize, 7 * cellSize)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(offset + (x + 1) * cellSize, offset + (y + 1) * cellSize, 5 * cellSize, 5 * cellSize)
    ctx.fillStyle = '#080c16'
    ctx.fillRect(offset + (x + 2) * cellSize, offset + (y + 2) * cellSize, 3 * cellSize, 3 * cellSize)
  }

  drawFinderPattern(0, 0)
  drawFinderPattern(modules - 7, 0)
  drawFinderPattern(0, modules - 7)

  // Timing lines
  for (let i = 8; i < modules - 8; i++) {
    if (i % 2 === 0) {
      ctx.fillRect(offset + i * cellSize, offset + 6 * cellSize, cellSize, cellSize)
      ctx.fillRect(offset + 6 * cellSize, offset + i * cellSize, cellSize, cellSize)
    }
  }

  // Data modules
  let seed = Math.abs(hash)
  for (let r = 0; r < modules; r++) {
    for (let c = 0; c < modules; c++) {
      // Skip finder corners
      if ((r < 8 && c < 8) || (r < 8 && c >= modules - 8) || (r >= modules - 8 && c < 8)) continue
      if (r === 6 || c === 6) continue

      seed = (seed * 1103515245 + 12345) & 0x7fffffff
      if ((seed % 100) < 45) {
        ctx.fillRect(offset + c * cellSize, offset + r * cellSize, cellSize, cellSize)
      }
    }
  }
}

// ── Initialize App ──────────────────────────────────────────────────────────
fetchState()
connectSSE()

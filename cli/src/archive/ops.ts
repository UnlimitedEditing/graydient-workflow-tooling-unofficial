import { readFileSync } from 'node:fs'
import { ArchiveSession, parseHeading } from './session.js'
import { setArchiveOrigin } from '../config.js'

export interface WorkflowRow {
  id: string
  name: string
}

/** Flags that live on the Basics tab and also appear in a backup JSON's graydient_workflow. */
const FLAG_KEYS = [
  'is_nsfw',
  'supports_txt2img',
  'supports_img2img',
  'supports_img2vid',
  'supports_txt2vid',
  'supports_vid2vid',
  'supports_vid2img',
  'supports_txt2wav',
  'supports_vid2wav',
  'supports_wav2txt',
  'supports_img2mesh',
  'supports_txt2mesh',
  'supports_mesh2img',
  'supports_mesh2vid',
  'split_prompt_pos_neg',
  'install_detected_nodes',
]

export async function login(s: ArchiveSession, link: string): Promise<{ origin: string; landed: string }> {
  const origin = new URL(link).origin
  await s.page.goto(link, { waitUntil: 'domcontentloaded' })
  await s.page.waitForURL(/\/(archive|concepts)/, { timeout: 30000 }).catch(() => {
    throw new Error(
      `Magic link did not land on /archive or /concepts (ended at ${s.page.url()}). Magic links are probably single-use or expired; ` +
        'request a fresh one with /archive or /concept /edit in Telegram.'
    )
  })
  setArchiveOrigin(origin)
  return { origin, landed: s.page.url() }
}

export async function status(s: ArchiveSession): Promise<{ loggedIn: boolean; origin: string; user?: string }> {
  try {
    const origin = s.origin()
    await s.goto('/workflows/')
    const user = (await s.page.locator('a[href="/profile/"]').last().innerText().catch(() => '')).trim() || undefined
    return { loggedIn: true, origin, user }
  } catch (e) {
    if (e instanceof Error && /not logged in/.test(e.message)) return { loggedIn: false, origin: '' }
    throw e
  }
}

/** List workflows. mine=true applies the "My Workflows" author filter; private included by default. */
export async function listWorkflows(s: ArchiveSession, opts: { mine?: boolean; includePrivate?: boolean } = {}): Promise<WorkflowRow[]> {
  const mine = opts.mine ?? true
  const includePrivate = opts.includePrivate ?? true
  await s.goto('/workflows/')
  if (mine) await s.page.locator('select:has(option[value="mine"])').selectOption('mine')
  if (includePrivate) await s.page.getByLabel('Include Private').check()
  // The list re-renders over the socket; wait for the link count to stop changing.
  let last = -1
  let stable = 0
  for (let i = 0; i < 40 && stable < 3; i++) {
    await s.page.waitForTimeout(500)
    const n = await s.page.locator('a[href^="/workflows/WF"]').count()
    stable = n === last ? stable + 1 : 0
    last = n
  }
  return s.page.$$eval('a[href^="/workflows/WF"]', (as) =>
    as.map((a) => ({
      id: (a.getAttribute('href') ?? '').replace('/workflows/', '').replace(/\/.*$/, ''),
      name: ((a as HTMLElement).innerText || '').trim().split('\n')[0].trim(),
    }))
  )
}

/** Accepts a WF id (unambiguous) or an exact workflow name from the "mine" list. */
export async function resolveWorkflow(s: ArchiveSession, ref: string): Promise<WorkflowRow> {
  if (/^WF[A-Za-z0-9]+$/.test(ref)) return { id: ref, name: ref }
  const all = await listWorkflows(s)
  const hits = all.filter((w) => w.name.toLowerCase() === ref.toLowerCase())
  if (hits.length === 1) return hits[0]
  if (hits.length === 0) throw new Error(`No workflow of yours is named "${ref}". Use an id (WFxxxx) from \`graydient archive list\`.`)
  throw new Error(`"${ref}" is ambiguous (${hits.map((h) => h.id).join(', ')}). Use the id.`)
}

export interface Basics {
  id: string
  name: string
  version: number | null
  description: string
  isPublic: boolean | null
  flags: Record<string, boolean>
  hasExampleImage: boolean
}

export async function readBasics(s: ArchiveSession, id: string): Promise<Basics> {
  await s.goto(`/workflows/${id}/edit`)
  const h = parseHeading(await s.heading())
  const page = s.page
  const description = await page.locator('textarea[name="description"]').first().inputValue()
  const flags: Record<string, boolean> = {}
  for (const k of FLAG_KEYS) {
    const el = page.locator(`input[type="checkbox"][name="${k}"]`)
    if (await el.count()) flags[k] = await el.first().isChecked()
  }
  const publicRadio = page.locator('input[type="radio"][name="is_public"][value="on"]')
  const isPublic = (await publicRadio.count()) ? await publicRadio.first().isChecked() : null
  // The cover is served from .../workflows/examples/...; the site chrome has other images.
  const hasExampleImage = (await page.locator('img[src*="/workflows/examples/"]').count()) > 0
  return {
    id,
    name: await page.locator('input[name="name"]').first().inputValue(),
    version: h.version,
    description,
    isPublic,
    flags,
    hasExampleImage,
  }
}

async function saveBasics(s: ArchiveSession): Promise<void> {
  await s.page.getByRole('button', { name: /save changes/i }).click()
  await s.page.getByText('Changes saved').first().waitFor({ timeout: 20000 })
}

export interface MetaEdit {
  name?: string
  description?: string
  image?: string
  flags?: Record<string, boolean>
  /** true=public, false=private, undefined=leave. Public is a publishing action: callers must have user permission. */
  isPublic?: boolean
}

export async function editMeta(s: ArchiveSession, id: string, edit: MetaEdit): Promise<Basics> {
  await s.goto(`/workflows/${id}/edit`)
  const page = s.page
  if (edit.name !== undefined) await page.locator('input[name="name"]').fill(edit.name)
  if (edit.description !== undefined) await page.locator('textarea[name="description"]').fill(edit.description)
  for (const [k, v] of Object.entries(edit.flags ?? {})) {
    const el = page.locator(`input[type="checkbox"][name="${k}"]`).first()
    if ((await el.isChecked()) !== v) await el.setChecked(v)
  }
  if (edit.isPublic !== undefined) {
    await page.locator(`input[type="radio"][name="is_public"][value="${edit.isPublic ? 'on' : 'off'}"]`).check()
  }
  if (edit.image) {
    await page.locator('input[name="example_image"]').setInputFiles(edit.image)
    await page.waitForTimeout(1500) // let the LiveView upload settle before saving the form
  }
  await saveBasics(s)
  return readBasics(s, id)
}

export interface RestoreResult {
  id: string
  versionBefore: number | null
  versionAfter: number | null
  flagDiffs: { key: string; json: boolean; site: boolean }[]
  descriptionOnSite: boolean
  fixed: boolean
}

/**
 * Restore a GraydientWorkflow-*.json onto an existing workflow. This REPLACES the target's
 * graph, fields and models. After the upload we read the Basics tab back and report any flags
 * that did not land (a restore does not reliably carry supports_* / install_detected_nodes /
 * description); with fix=true those are applied and saved.
 */
export async function restore(s: ArchiveSession, id: string, jsonPath: string, opts: { fix?: boolean } = {}): Promise<RestoreResult> {
  const raw = JSON.parse(readFileSync(jsonPath, 'utf-8'))
  const gw = raw.graydient_workflow
  if (!gw) throw new Error(`${jsonPath} has no graydient_workflow key; not a Graydient backup`)

  await s.goto(`/workflows/${id}/edit`)
  const before = parseHeading(await s.heading()).version
  await s.tab('Backup')
  await s.page.locator('input[type="file"]').first().setInputFiles(jsonPath)
  // The upload applies immediately; the heading version bumps when it lands.
  await s.page.waitForFunction(
    (b) => {
      const m = (document.querySelector('h1')?.textContent ?? '').match(/v(\d+)/)
      return m && (b === null || Number(m[1]) > b)
    },
    before,
    { timeout: 90000 }
  )
  const afterBackup = parseHeading(await s.heading()).version

  let basics = await readBasics(s, id)
  const diffs = Object.entries(basics.flags)
    .filter(([k]) => k in gw && typeof gw[k] === 'boolean' && gw[k] !== basics.flags[k])
    .map(([k, site]) => ({ key: k, json: gw[k] as boolean, site }))
  const needDesc = !basics.description.trim() && typeof gw.description === 'string' && gw.description.trim()

  let fixed = false
  if (opts.fix && (diffs.length || needDesc)) {
    basics = await editMeta(s, id, {
      flags: Object.fromEntries(diffs.map((d) => [d.key, d.json])),
      description: needDesc ? (gw.description as string) : undefined,
    })
    fixed = true
  }
  return {
    id,
    versionBefore: before,
    versionAfter: basics.version ?? afterBackup,
    flagDiffs: diffs,
    descriptionOnSite: !!basics.description.trim(),
    fixed,
  }
}

/** Click New Workflow: this CREATES an empty stub on the account. Returns its id. */
export async function createStub(s: ArchiveSession): Promise<string> {
  await s.goto('/workflows/')
  await s.page.getByRole('button', { name: /new workflow/i }).click()
  await s.page.waitForURL(/\/workflows\/WF[A-Za-z0-9]+\/edit/, { timeout: 30000 })
  const m = s.page.url().match(/\/workflows\/(WF[A-Za-z0-9]+)\/edit/)
  if (!m) throw new Error(`New Workflow did not land on an edit page (at ${s.page.url()})`)
  await s.ready()
  return m[1]
}

/** Generic read of any edit tab (Fields, Models, Logs, Use ...): every form control plus visible text. */
export async function dumpTab(s: ArchiveSession, id: string, tab: string): Promise<{ heading: string; controls: unknown[]; text: string }> {
  await s.goto(`/workflows/${id}/edit`)
  if (tab !== 'Basics') await s.tab(tab)
  await s.page.waitForTimeout(800)
  const controls = await s.page.$$eval('main input, main textarea, main select, form input, form textarea, form select', (els) =>
    els.map((e) => {
      const i = e as HTMLInputElement
      return { tag: e.tagName.toLowerCase(), type: i.type, name: i.name, value: i.type === 'file' ? '' : (i.value ?? '').slice(0, 300), checked: i.type === 'checkbox' || i.type === 'radio' ? i.checked : undefined }
    })
  )
  const text = (await s.page.locator('body').innerText().catch(() => '')).slice(0, 20000)
  return { heading: await s.heading(), controls, text }
}

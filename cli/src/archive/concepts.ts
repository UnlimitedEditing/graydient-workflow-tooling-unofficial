// Concept (LoRA) management in the Graydient community site (/concepts/edit, the page behind
// Telegram `/concept /edit`). Same Playwright session + login as the workflow archive.
// Form field names were mapped live on 2026-10-08.
import { ArchiveSession } from './session.js'

export const MODEL_FAMILIES = [
  'Anima', 'Chroma', 'Cosmos', 'Flux', 'Flux2', 'H3', 'Hidream', 'Huny', 'Ideogram', 'Krea2',
  'Ltx2', 'Lumina', 'SD15', 'SDXL', 'Qwen', 'Qwen2', 'Wan', 'Zimage',
] as const
export const CONCEPT_TYPES = ['lora', 'style', 'inversion', 'inpainting', 'instruct'] as const

export interface ConceptInput {
  name: string
  token: string
  url: string
  family: string
  type?: string
  description?: string
  infoUrl?: string
  exampleUrl?: string
  nsfw?: boolean
  enabled?: boolean
  tags?: string[]
}

export async function listConcepts(s: ArchiveSession): Promise<{ text: string; links: { text: string; href: string }[] }> {
  await s.goto('/concepts/edit')
  await s.page.waitForTimeout(800)
  const links = await s.page.$$eval('main a, a', (els) =>
    els.map((a) => ({ text: (a as HTMLElement).innerText.trim(), href: a.getAttribute('href') ?? '' })).filter((l) => /concepts?\//.test(l.href) && l.text)
  )
  const text = (await s.page.locator('body').innerText()).slice(0, 8000)
  return { text, links }
}

export interface ConceptRow {
  id: string
  name: string
}

/** Concepts on the account as {id, name}; id is the number in the card's `edit-concept-<id>` button. */
export async function listRows(s: ArchiveSession): Promise<ConceptRow[]> {
  await s.goto('/concepts/edit')
  await s.page.waitForTimeout(800)
  return s.page.$$eval('[phx-click^="edit-concept-"]', (btns) =>
    btns.map((b) => {
      const id = (b.getAttribute('phx-click') ?? '').replace('edit-concept-', '')
      let el: HTMLElement | null = b as HTMLElement
      let name = ''
      while (el && !name) {
        const m = el.innerText.match(/<([^>\n]+)>/)
        if (m) name = m[1]
        else el = el.parentElement
      }
      return { id, name }
    })
  )
}

async function resolveRow(s: ArchiveSession, ref: string): Promise<ConceptRow> {
  const rows = await listRows(s)
  const hits = rows.filter((r) => r.id === ref || r.name === ref)
  if (hits.length !== 1) throw new Error(`${hits.length ? 'Ambiguous' : 'No'} concept "${ref}". Have: ${rows.map((r) => `${r.id}:${r.name}`).join(', ') || '(none)'}`)
  return hits[0]
}

export type ConceptEdit = Partial<Omit<ConceptInput, 'type'>> & { type?: string }

/** Edit fields of an existing concept; only the fields given are changed. */
export async function editConcept(s: ArchiveSession, ref: string, e: ConceptEdit): Promise<{ saved: boolean; message: string }> {
  const row = await resolveRow(s, ref)
  const p = s.page
  await p.locator(`[phx-click="edit-concept-${row.id}"]`).click()
  await p.waitForSelector('input[name="name"]')
  const fill = async (sel: string, v?: string) => { if (v !== undefined) await p.fill(sel, v) }
  await fill('input[name="name"]', e.name)
  await fill('input[name="token"]', e.token)
  await fill('input[name="url"]', e.url)
  await fill('textarea[name="description"]', e.description)
  await fill('input[name="info_url"]', e.infoUrl)
  await fill('input[name="example_url"]', e.exampleUrl)
  if (e.enabled !== undefined) await p.locator('input[name="is_enabled"]').setChecked(e.enabled)
  if (e.nsfw !== undefined) await p.locator('input[name="is_nsfw"]').setChecked(e.nsfw)
  if (e.tags) {
    for (const box of await p.locator('input[name="tags[]"]').all()) await box.setChecked(e.tags.includes((await box.getAttribute('value')) ?? ''))
  }
  if (e.family) await p.selectOption('select[name="model_family"]', e.family)
  if (e.type) await p.selectOption('select[name="type"]', e.type)
  await p.getByRole('button', { name: /^save$/i }).first().click()
  await p.waitForTimeout(3000)
  const m = (await p.locator('body').innerText()).match(/concept saved[^\n]*/i)
  return { saved: !!m, message: m ? m[0] : 'Save not confirmed' }
}

/** PERMANENTLY delete a concept (the site may ask for a browser confirm; it is accepted). */
export async function deleteConcept(s: ArchiveSession, ref: string): Promise<ConceptRow> {
  const row = await resolveRow(s, ref)
  s.page.once('dialog', (d) => void d.accept())
  await s.page.locator(`[phx-click="delete-concept-${row.id}"]`).click()
  await s.page.waitForTimeout(2500)
  const left = await s.page.locator(`[phx-click="delete-concept-${row.id}"]`).count()
  if (left) {
    // maybe an in-page confirm button
    const ok = s.page.getByRole('button', { name: /^(yes|confirm|delete)\b/i }).first()
    if (await ok.count()) { await ok.click(); await s.page.waitForTimeout(2000) }
  }
  if (await s.page.locator(`[phx-click="delete-concept-${row.id}"]`).count()) throw new Error(`Concept ${row.id} still present after delete`)
  return row
}

/** Open the blank New-concept form (tab "New" on /concepts/edit). */
async function openNewForm(s: ArchiveSession): Promise<void> {
  await s.goto('/concepts/edit')
  await s.page.locator('a:text-is("New"), button:text-is("New")').first().click()
  await s.page.waitForSelector('input[name="name"]')
}

export function validate(c: ConceptInput): void {
  if (!/^https:\/\/huggingface\.co\/.+\/resolve\/.+/.test(c.url))
    throw new Error('Download URL must be a public Hugging Face direct link (https://huggingface.co/<user>/<repo>/resolve/main/<file>). Do not hotlink Civitai.')
  if (!(MODEL_FAMILIES as readonly string[]).includes(c.family)) throw new Error(`Unknown model family "${c.family}". One of: ${MODEL_FAMILIES.join(', ')}`)
  if (c.type && !(CONCEPT_TYPES as readonly string[]).includes(c.type)) throw new Error(`Unknown type "${c.type}". One of: ${CONCEPT_TYPES.join(', ')}`)
  if (!/^[\w.-]+$/.test(c.token)) throw new Error(`Prompt token "${c.token}" should be a single word without spaces`)
}

/** Fill the New form and SAVE. Creates a real concept on the account (installs in ~3-5 min, usable ~3-5 min after the success message). */
export async function createConcept(s: ArchiveSession, c: ConceptInput): Promise<{ saved: boolean; message: string }> {
  validate(c)
  await openNewForm(s)
  const p = s.page
  await p.fill('input[name="name"]', c.name)
  await p.fill('input[name="token"]', c.token)
  await p.fill('input[name="url"]', c.url)
  if (c.description) await p.fill('textarea[name="description"]', c.description)
  if (c.infoUrl) await p.fill('input[name="info_url"]', c.infoUrl)
  if (c.exampleUrl) await p.fill('input[name="example_url"]', c.exampleUrl)
  await p.locator('input[name="is_enabled"]').setChecked(c.enabled ?? true)
  await p.locator('input[name="is_nsfw"]').setChecked(!!c.nsfw)
  for (const t of c.tags ?? []) {
    const box = p.locator(`input[name="tags[]"][value="${t}"]`)
    if (!(await box.count())) throw new Error(`Unknown tag "${t}"`)
    await box.setChecked(true)
  }
  await p.selectOption('select[name="model_family"]', c.family)
  await p.selectOption('select[name="type"]', c.type ?? 'lora')
  await p.getByRole('button', { name: /^save$/i }).first().click()
  await p.waitForTimeout(3000)
  const body = await p.locator('body').innerText()
  const m = body.match(/concept saved[^\n]*/i)
  if (m && (c.enabled ?? true)) {
    // Observed 2026-10-08: the Enabled box does not persist on a brand-new concept's first save (listed DISABLED).
    // Re-open it from the list and save again with Enabled checked.
    await s.goto('/concepts/edit')
    const card = p.locator('[phx-click^="edit-concept-"]').first()
    await card.click()
    await p.waitForSelector('input[name="name"]')
    await p.locator('input[name="is_enabled"]').check()
    await p.getByRole('button', { name: /^save$/i }).first().click()
    await p.waitForTimeout(3000)
  }
  return { saved: !!m, message: m ? m[0] : body.slice(0, 500) }
}

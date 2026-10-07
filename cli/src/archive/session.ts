// Playwright session for the Graydient community "archive" web UI (the page the
// Telegram `/archive` command gives a magic link to). There is no API for it: it is a
// Phoenix LiveView app, so everything is driven through a real browser.
//
// Login = open the magic link once. The site's session cookie has NO expiry (a browser
// session cookie), so a persistent browser profile loses it on close; we instead keep a fresh
// in-memory context per run and save ONLY the graydient.ai cookies to ~/.graydient/archive-session.json
// (mode 600, same trust level as the stored API key). A persistent profile was also rejected because
// Edge pulled the user's Microsoft/Bing sign-in cookies into it.
// Sessions DO expire server-side (observed: gone by the next day), so every operation detects a
// logged-out state and throws LoggedOutError.
import { chromium, type Browser, type BrowserContext, type Page } from 'playwright-core'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { getArchiveOrigin } from '../config.js'

export const SESSION_FILE = join(homedir(), '.graydient', 'archive-session.json')

const isGraydientCookie = (c: { domain: string }) => /(^|\.)graydient\.ai$/.test(c.domain.replace(/^\./, ''))

export class LoggedOutError extends Error {
  constructor() {
    super(
      'Archive session is not logged in (expired or never started). Ask Jacob to send /archive to the Graydient ' +
        'Telegram bot and paste the magic link, then run: graydient archive login <link>'
    )
  }
}

export class ArchiveSession {
  private constructor(
    readonly browser: Browser,
    readonly ctx: BrowserContext,
    readonly page: Page
  ) {}

  static async open(opts: { headed?: boolean } = {}): Promise<ArchiveSession> {
    const channels = process.env.GRAYDIENT_BROWSER_CHANNEL ? [process.env.GRAYDIENT_BROWSER_CHANNEL] : ['msedge', 'chrome']
    let lastErr: unknown
    for (const channel of channels) {
      try {
        const browser = await chromium.launch({ channel, headless: !opts.headed })
        const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } })
        if (existsSync(SESSION_FILE)) {
          try {
            const saved = JSON.parse(readFileSync(SESSION_FILE, 'utf-8')) as any[]
            const week = Math.floor(Date.now() / 1000) + 7 * 86400
            // Session cookies have expires -1; give them a lifetime so the context keeps them for this run.
            await ctx.addCookies(saved.filter(isGraydientCookie).map((c) => ({ ...c, expires: c.expires > 0 ? c.expires : week })))
          } catch {
            /* corrupt file: treated as logged out */
          }
        }
        const page = await ctx.newPage()
        page.setDefaultTimeout(20000)
        return new ArchiveSession(browser, ctx, page)
      } catch (e) {
        lastErr = e
      }
    }
    throw new Error(
      `Could not launch Edge or Chrome via Playwright (${lastErr instanceof Error ? lastErr.message : String(lastErr)}). ` +
        'Install one, or set GRAYDIENT_BROWSER_CHANNEL.'
    )
  }

  /** Persist only graydient.ai cookies (the login). Called on close so a refreshed cookie is kept. */
  async saveSession(): Promise<void> {
    const cookies = (await this.ctx.cookies()).filter(isGraydientCookie)
    if (cookies.some((c) => c.name === '_scum_key')) writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2), { mode: 0o600 })
  }

  async close(): Promise<void> {
    await this.saveSession().catch(() => {})
    await this.browser.close()
  }

  /** Origin of the community site, e.g. https://capxkya125x.graydient.ai (set by `archive login`). */
  origin(): string {
    const o = getArchiveOrigin()
    if (!o) throw new LoggedOutError()
    return o
  }

  /**
   * LiveView pages render server-side first and only become interactive once the socket
   * connects. Clicks/uploads made before that are silently dropped (this bit us by hand),
   * so every navigation waits for the connected class.
   */
  async ready(): Promise<void> {
    await this.page.waitForSelector('[data-phx-main].phx-connected', { timeout: 20000 })
  }

  async goto(path: string): Promise<void> {
    await this.page.goto(this.origin() + path, { waitUntil: 'domcontentloaded' })
    await this.assertLoggedIn()
    await this.ready()
  }

  async assertLoggedIn(): Promise<void> {
    const url = this.page.url()
    if (/\/private\/?$|\/login\b/.test(new URL(url).pathname)) throw new LoggedOutError()
    const title = await this.page.title().catch(() => '')
    if (/private site/i.test(title)) throw new LoggedOutError()
  }

  /** Text of the page heading, e.g. "joyaiecho-t2voice - v2 - Basics". */
  async heading(): Promise<string> {
    return ((await this.page.locator('h1').first().innerText()) ?? '').trim()
  }

  /** Switch edit-page tab (Basics, Details, Fields, Models, Logs, Backup, Use). */
  async tab(name: string): Promise<void> {
    const before = await this.heading()
    await this.page.locator(`a:text-is("${name}")`).first().click()
    // Heading wording differs per tab (e.g. "Backup/Restore"), so wait for it to change rather than match a name.
    await this.page.waitForFunction((h) => (document.querySelector('h1')?.textContent ?? '').trim() !== h, before)
    await this.page.waitForTimeout(500)
  }
}

export function parseHeading(h: string): { name: string; version: number | null; tab: string } {
  const m = h.match(/^(.*?)\s+-\s+v(\d+)\s+-\s+(.*)$/)
  return m ? { name: m[1], version: Number(m[2]), tab: m[3] } : { name: h, version: null, tab: '' }
}

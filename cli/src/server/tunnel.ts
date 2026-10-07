import { spawn, ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { EventEmitter } from 'node:events'

const KNOWN_CLOUDFLARED_PATHS = [
  'C:\\Program Files (x86)\\cloudflared\\cloudflared.exe',
  'C:\\Program Files\\cloudflared\\cloudflared.exe',
  'cloudflared.exe',
  'cloudflared',
]

export function findCloudflaredBinary(): string {
  for (const p of KNOWN_CLOUDFLARED_PATHS) {
    if (existsSync(p)) return p
  }
  return 'cloudflared'
}

export interface TunnelStatus {
  active: boolean
  url: string | null
  startedAt?: string
  error?: string
}

export class TunnelManager extends EventEmitter {
  private process: ChildProcess | null = null
  private url: string | null = null
  private startedAt: string | null = null
  private error: string | null = null

  public getStatus(): TunnelStatus {
    return {
      active: !!this.process && !!this.url,
      url: this.url,
      startedAt: this.startedAt ?? undefined,
      error: this.error ?? undefined,
    }
  }

  public async start(port: number): Promise<string> {
    if (this.process && this.url) {
      return this.url
    }

    this.stop()
    this.error = null
    this.url = null

    const bin = findCloudflaredBinary()

    return new Promise<string>((resolve, reject) => {
      let resolved = false
      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true
          this.stop()
          reject(new Error('Cloudflare tunnel startup timed out after 30 seconds.'))
        }
      }, 30000)

      try {
        const child = spawn(bin, ['tunnel', '--url', `http://127.0.0.1:${port}`], {
          windowsHide: true,
          stdio: ['ignore', 'pipe', 'pipe'],
        })

        this.process = child

        const onData = (data: Buffer) => {
          const text = data.toString()
          // Look for https://*.trycloudflare.com
          const match = text.match(/https:\/\/[a-zA-Z0-9-]+\.trycloudflare\.com/)
          if (match && !this.url) {
            this.url = match[0]
            this.startedAt = new Date().toISOString()
            clearTimeout(timeout)
            if (!resolved) {
              resolved = true
              this.emit('tunnel-started', this.getStatus())
              resolve(this.url)
            }
          }
        }

        child.stdout?.on('data', onData)
        child.stderr?.on('data', onData)

        child.on('error', (err) => {
          console.error('Cloudflared process error:', err)
          this.error = err.message
          clearTimeout(timeout)
          if (!resolved) {
            resolved = true
            reject(err)
          }
          this.stop()
        })

        child.on('exit', (code, sig) => {
          clearTimeout(timeout)
          this.process = null
          this.url = null
          this.startedAt = null
          this.emit('tunnel-stopped', { code, sig })
          if (!resolved) {
            resolved = true
            reject(new Error(`Cloudflared exited prematurely with code ${code}`))
          }
        })
      } catch (err) {
        clearTimeout(timeout)
        this.error = err instanceof Error ? err.message : String(err)
        reject(err)
      }
    })
  }

  public stop(): void {
    if (this.process) {
      try {
        this.process.kill()
      } catch {
        /* ignore */
      }
      this.process = null
    }
    this.url = null
    this.startedAt = null
    this.emit('tunnel-stopped', {})
  }
}

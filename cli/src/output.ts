// Output discipline for CLI/agent consumption: progress/logs always go to
// stderr, exactly one result (text or JSON) goes to stdout. This lets any
// script or coding agent do `graydient render "..." --json | jq .` safely.
import { createWriteStream, existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, extname, join, basename } from 'node:path'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

export function logProgress(message: string): void {
  process.stderr.write(`${message}\n`)
}

export function printResult(data: unknown, jsonMode: boolean, textFormatter?: (data: unknown) => string): void {
  if (jsonMode) {
    process.stdout.write(JSON.stringify(data, null, 2) + '\n')
  } else {
    process.stdout.write((textFormatter ? textFormatter(data) : String(data)) + '\n')
  }
}

export function printError(message: string, jsonMode: boolean): void {
  if (jsonMode) {
    process.stdout.write(JSON.stringify({ error: message }, null, 2) + '\n')
  } else {
    process.stderr.write(`Error: ${message}\n`)
  }
}

/** Avoid clobbering existing files — append -1, -2, ... before the extension. */
export function uniqueDestPath(destDir: string, baseName: string): string {
  const dot = baseName.lastIndexOf('.')
  const stem = dot >= 0 ? baseName.slice(0, dot) : baseName
  const ext = dot >= 0 ? baseName.slice(dot) : ''
  let candidate = join(destDir, baseName)
  let n = 1
  while (existsSync(candidate)) {
    candidate = join(destDir, `${stem}-${n}${ext}`)
    n++
  }
  return candidate
}

const MEDIA_TYPE_EXT: Record<string, string> = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/webp': '.webp',
  'image/gif': '.gif',
  'video/mp4': '.mp4',
  'video/webm': '.webm',
  'audio/mpeg': '.mp3',
  'audio/wav': '.wav',
  'audio/x-wav': '.wav',
  model: '.glb',
  'model/gltf-binary': '.glb',
}

function guessExtension(url: string, mediaType: string | null): string {
  const urlExt = extname(new URL(url).pathname)
  if (urlExt && urlExt.length <= 6) return urlExt
  if (mediaType && MEDIA_TYPE_EXT[mediaType]) return MEDIA_TYPE_EXT[mediaType]
  return '.bin'
}

/**
 * Download one media URL to `dest`, which may be:
 *  - a directory (existing, or path ending in / or \) — filename is derived
 *  - a plain file path — used as-is (collision-checked by the caller when
 *    downloading more than one file to the same target)
 */
export async function downloadFile(url: string, dest: string, opts?: { mediaType?: string | null; index?: number }): Promise<string> {
  const looksLikeDir = dest.endsWith('/') || dest.endsWith('\\') || (existsSync(dest) && isDirectory(dest))
  let destPath: string
  if (looksLikeDir) {
    const ext = guessExtension(url, opts?.mediaType ?? null)
    const stem = basename(new URL(url).pathname, ext) || `render${opts?.index ? `-${opts.index}` : ''}`
    if (!existsSync(dest)) mkdirSync(dest, { recursive: true })
    destPath = uniqueDestPath(dest, `${stem}${ext}`)
  } else {
    destPath = dest
    const dir = dirname(destPath)
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  }

  const res = await fetch(url)
  if (!res.ok || !res.body) throw new Error(`Failed to download ${url}: ${res.status}`)

  await pipeline(Readable.fromWeb(res.body as import('node:stream/web').ReadableStream), createWriteStream(destPath))
  return destPath
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory()
  } catch {
    return false
  }
}

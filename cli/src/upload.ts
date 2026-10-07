// Graydient's API has no upload endpoint — init-image/init-audio must be a URL it
// can fetch. This resolves a local file path to a URL by uploading it to litterbox
// (catbox.moe's temporary-hosting sibling): anonymous, no account needed, and the
// link auto-expires (default 1h) instead of sitting on a public host indefinitely.
import { readFile } from 'node:fs/promises'
import { existsSync, statSync } from 'node:fs'
import { basename } from 'node:path'
import { logProgress } from './output.js'

const LITTERBOX_ENDPOINT = 'https://litterbox.catbox.moe/resources/internals/api.php'

export type LitterboxTime = '1h' | '12h' | '24h' | '72h'

export function isUrl(value: string): boolean {
  try {
    const u = new URL(value)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

function isLocalFile(value: string): boolean {
  try {
    return existsSync(value) && statSync(value).isFile()
  } catch {
    return false
  }
}

export async function uploadToLitterbox(filePath: string, time: LitterboxTime = '1h'): Promise<string> {
  const bytes = await readFile(filePath)
  const form = new FormData()
  form.set('reqtype', 'fileupload')
  form.set('time', time)
  form.set('fileToUpload', new Blob([bytes]), basename(filePath))

  // `Connection: close` avoids leaving a keep-alive socket around after this
  // one-off request — on Windows, an abrupt process.exit() (see index.ts) racing
  // a still-closing undici socket can crash the process with a libuv assertion.
  const res = await fetch(LITTERBOX_ENDPOINT, { method: 'POST', body: form, headers: { Connection: 'close' } })
  const text = (await res.text()).trim()
  if (!res.ok || !isUrl(text)) {
    throw new Error(`litterbox upload failed (${res.status}): ${text.slice(0, 300)}`)
  }
  return text
}

/**
 * Resolve a CLI-supplied image/audio value to a URL Graydient can fetch:
 * passes URLs through unchanged, uploads local files to litterbox, and throws
 * a clear error for anything else (missing file, unsupported scheme, ...).
 */
export async function resolveMediaInput(value: string, time: LitterboxTime = '1h'): Promise<string> {
  if (isUrl(value)) return value
  if (isLocalFile(value)) {
    logProgress(`Uploading local file to a temporary host (expires in ${time}): ${value}`)
    const url = await uploadToLitterbox(value, time)
    logProgress(`Uploaded -> ${url}`)
    return url
  }
  throw new Error(`"${value}" is neither a reachable http(s) URL nor an existing local file.`)
}

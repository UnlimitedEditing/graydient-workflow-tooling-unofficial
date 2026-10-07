import { existsSync, mkdirSync, readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const CONFIG_DIR = join(homedir(), '.graydient')
const CONFIG_FILE = join(CONFIG_DIR, 'config.json')

export const DEFAULT_BASE_URL = 'https://app.graydient.ai/api/v3/'

interface StoredConfig {
  apiKey?: string
  baseUrl?: string
  archiveOrigin?: string
}

function readConfig(): StoredConfig {
  if (!existsSync(CONFIG_FILE)) return {}
  try {
    return JSON.parse(readFileSync(CONFIG_FILE, 'utf-8')) as StoredConfig
  } catch {
    return {}
  }
}

function writeConfig(config: StoredConfig): void {
  if (!existsSync(CONFIG_DIR)) mkdirSync(CONFIG_DIR, { recursive: true })
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), { mode: 0o600 })
}

export function getApiKey(): string {
  const fromEnv = process.env.GRAYDIENT_API_KEY
  if (fromEnv) return fromEnv
  return readConfig().apiKey ?? ''
}

export function setApiKey(key: string): void {
  const config = readConfig()
  config.apiKey = key
  writeConfig(config)
}

export function clearApiKey(): void {
  const config = readConfig()
  delete config.apiKey
  if (Object.keys(config).length === 0 && existsSync(CONFIG_FILE)) {
    unlinkSync(CONFIG_FILE)
  } else {
    writeConfig(config)
  }
}

export function getBaseUrl(): string {
  return process.env.GRAYDIENT_API_URL || readConfig().baseUrl || DEFAULT_BASE_URL
}

export function setBaseUrl(url: string): void {
  const config = readConfig()
  config.baseUrl = url
  writeConfig(config)
}

/** Community-site origin the archive web UI lives on (captured from the magic link by `archive login`). */
export function getArchiveOrigin(): string {
  return process.env.GRAYDIENT_ARCHIVE_ORIGIN || readConfig().archiveOrigin || ''
}

export function setArchiveOrigin(origin: string): void {
  const config = readConfig()
  config.archiveOrigin = origin
  writeConfig(config)
}

export function getConfigPath(): string {
  return CONFIG_FILE
}

export function hasStoredKey(): boolean {
  return !!readConfig().apiKey
}

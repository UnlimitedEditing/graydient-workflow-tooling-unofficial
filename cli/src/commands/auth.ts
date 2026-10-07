import { Command } from 'commander'
import { createInterface } from 'node:readline/promises'
import { getApiKey, setApiKey, clearApiKey, getConfigPath, hasStoredKey, getBaseUrl } from '../config.js'
import { fetchWorkflows } from '../client.js'
import { logProgress, printResult, printError } from '../output.js'

function maskKey(key: string): string {
  if (key.length <= 8) return '*'.repeat(key.length)
  return `${key.slice(0, 4)}${'*'.repeat(key.length - 8)}${key.slice(-4)}`
}

export function registerAuthCommands(program: Command): void {
  const auth = program.command('auth').description('Manage the stored Graydient API key')

  auth
    .command('login')
    .description('Store a Graydient API key (from https://app.graydient.ai/dashboard/token/)')
    .option('--key <key>', 'API key (omit to be prompted)')
    .action(async (opts: { key?: string }) => {
      let key = opts.key
      if (!key) {
        const rl = createInterface({ input: process.stdin, output: process.stderr })
        key = (await rl.question('Graydient API key: ')).trim()
        rl.close()
      }
      if (!key) {
        printError('No API key provided', false)
        process.exitCode = 1
        return
      }
      setApiKey(key)
      logProgress(`Saved API key to ${getConfigPath()}`)
    })

  auth
    .command('status')
    .description('Show whether an API key is stored and whether it works')
    .option('--json', 'Output JSON')
    .action(async (opts: { json?: boolean }) => {
      const jsonMode = !!opts.json
      const key = getApiKey()
      if (!key) {
        printResult(
          { stored: false, valid: false },
          jsonMode,
          () => 'No API key configured. Run `graydient auth login` or set GRAYDIENT_API_KEY.'
        )
        return
      }
      let valid = false
      try {
        await fetchWorkflows()
        valid = true
      } catch {
        valid = false
      }
      printResult(
        { stored: true, fromEnv: !hasStoredKey() && !!process.env.GRAYDIENT_API_KEY, masked: maskKey(key), baseUrl: getBaseUrl(), valid },
        jsonMode,
        (d: any) => `API key: ${d.masked}${d.fromEnv ? ' (from GRAYDIENT_API_KEY)' : ''}\nBase URL: ${d.baseUrl}\nValid: ${d.valid ? 'yes' : 'no — request failed'}`
      )
    })

  auth
    .command('logout')
    .description('Delete the stored API key')
    .action(() => {
      clearApiKey()
      logProgress('API key removed.')
    })
}

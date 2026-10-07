import { Command } from 'commander'
import { getBaseUrl, setBaseUrl, getConfigPath, DEFAULT_BASE_URL } from '../config.js'
import { logProgress, printResult } from '../output.js'

export function registerConfigCommands(program: Command): void {
  const config = program.command('config').description('View or change CLI configuration')

  config
    .command('get')
    .description('Show current configuration')
    .option('--json', 'Output JSON')
    .action((opts: { json?: boolean }) => {
      printResult(
        { baseUrl: getBaseUrl(), configPath: getConfigPath() },
        !!opts.json,
        (d: any) => `baseUrl: ${d.baseUrl}\nconfigPath: ${d.configPath}`
      )
    })

  config
    .command('set-base-url <url>')
    .description(`Override the Graydient API base URL (default: ${DEFAULT_BASE_URL})`)
    .action((url: string) => {
      setBaseUrl(url)
      logProgress(`Base URL set to ${url}`)
    })
}

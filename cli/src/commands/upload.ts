import { Command } from 'commander'
import { uploadToLitterbox, type LitterboxTime } from '../upload.js'
import { printResult, printError } from '../output.js'

export function registerUploadCommand(program: Command): void {
  program
    .command('upload <file>')
    .description('Upload a local file to a temporary expiring host and print the resulting URL (for --init-image/--init-audio, or to reuse across calls)')
    .option('--expiry <duration>', 'How long the link stays up: 1h, 12h, 24h, or 72h', '1h')
    .option('--json', 'Output JSON')
    .action(async (file: string, opts: { expiry: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      const expiry = opts.expiry as LitterboxTime
      if (!['1h', '12h', '24h', '72h'].includes(expiry)) {
        printError(`--expiry must be one of 1h, 12h, 24h, 72h (got "${opts.expiry}")`, jsonMode)
        process.exitCode = 1
        return
      }
      try {
        const url = await uploadToLitterbox(file, expiry)
        printResult({ url, expiry }, jsonMode, () => url)
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

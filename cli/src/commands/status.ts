import { Command } from 'commander'
import { fetchRenderInfo, resolveAllMedia } from '../client.js'
import { printResult, printError } from '../output.js'

export function registerStatusCommand(program: Command): void {
  program
    .command('status <renderHash>')
    .description('Check the status of a previously submitted render')
    .option('--json', 'Output JSON')
    .action(async (renderHash: string, opts: { json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const info = await fetchRenderInfo(renderHash)
        const media = resolveAllMedia(info)
        printResult(
          { renderHash: info.render_hash, hasBeenRendered: !!info.has_been_rendered, media },
          jsonMode,
          () =>
            `render_hash: ${info.render_hash}\nrendered: ${info.has_been_rendered ? 'yes' : 'no'}\n${media.map((m) => m.url).join('\n')}`
        )
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

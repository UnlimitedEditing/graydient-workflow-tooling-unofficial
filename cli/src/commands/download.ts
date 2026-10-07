import { Command } from 'commander'
import { fetchRenderInfo, resolveAllMedia } from '../client.js'
import { printResult, printError, downloadFile } from '../output.js'

export function registerDownloadCommand(program: Command): void {
  program
    .command('download <renderHash>')
    .description("Download a previous render's media without re-rendering")
    .requiredOption('--out <path>', 'File (single output) or directory (multiple outputs) to save to')
    .option('--json', 'Output JSON')
    .action(async (renderHash: string, opts: { out: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const info = await fetchRenderInfo(renderHash)
        const media = resolveAllMedia(info)
        if (!media.length) {
          printError(`No media available for render ${renderHash} yet`, jsonMode)
          process.exitCode = 1
          return
        }
        const savedPaths = await Promise.all(media.map((m, i) => downloadFile(m.url, opts.out, { mediaType: m.mediaType, index: i })))
        printResult({ renderHash, savedPaths }, jsonMode, () => savedPaths.join('\n'))
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

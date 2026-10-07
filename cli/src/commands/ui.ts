import { Command } from 'commander'
import { exec } from 'node:child_process'
import { createRenderServer } from '../server/server.js'

export function registerUiCommand(program: Command): void {
  program
    .command('ui')
    .alias('kanban')
    .description('Launch the RenderFlow Kanban web workspace with queue management, omni-russ chaining, and remote tunnel')
    .option('-p, --port <port>', 'Port to listen on', '7860')
    .option('-t, --tunnel', 'Automatically open Cloudflare tunnel on launch for remote access', false)
    .option('--open', 'Open the workspace in your browser automatically', false)
    .action(async (opts: { port: string; tunnel: boolean; open: boolean }) => {
      const port = parseInt(opts.port, 10) || 7860
      const app = createRenderServer(port)

      process.stdout.write('\n')
      process.stdout.write('  ======================================================\n')
      process.stdout.write('     🚀 Graydient RenderFlow Kanban Workspace\n')
      process.stdout.write('  ======================================================\n\n')

      const actualPort = await app.start()
      const localUrl = `http://localhost:${actualPort}`

      process.stdout.write(`  ➜  Local:   \x1b[36m${localUrl}\x1b[0m\n`)
      process.stdout.write(`  ➜  Network: \x1b[36mhttp://0.0.0.0:${actualPort}\x1b[0m\n`)

      if (opts.tunnel) {
        process.stdout.write('  ➜  Tunnel:  \x1b[33mStarting Cloudflare tunnel...\x1b[0m\n')
        try {
          const tunnelUrl = await app.tunnel.start(actualPort)
          process.stdout.write(`  ➜  Tunnel:  \x1b[32m${tunnelUrl}\x1b[0m (Manage remotely from your phone!)\n`)
        } catch (err) {
          process.stdout.write(`  ➜  Tunnel:  \x1b[31mFailed to start tunnel: ${err instanceof Error ? err.message : String(err)}\x1b[0m\n`)
        }
      } else {
        process.stdout.write('  ➜  Tunnel:  Disabled (Click "Start Tunnel" in the UI header anytime)\n')
      }

      process.stdout.write('\n  💡 Press Ctrl+C to stop the server.\n\n')

      if (opts.open) {
        const cmd = process.platform === 'win32' ? `start ${localUrl}` : `open ${localUrl}`
        exec(cmd)
      }

      return new Promise<void>((resolve) => {
        const shutdown = () => {
          process.stdout.write('\nShutting down RenderFlow workspace...\n')
          app.stop()
          resolve()
          process.exit(0)
        }

        process.on('SIGINT', shutdown)
        process.on('SIGTERM', shutdown)
      })
    })
}

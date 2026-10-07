#!/usr/bin/env node
import { Command } from 'commander'
import { registerAuthCommands } from './commands/auth.js'
import { registerWorkflowCommands } from './commands/workflows.js'
import { registerConceptCommands } from './commands/concepts.js'
import { registerSkillCommands } from './commands/skills.js'
import { registerRenderCommand } from './commands/render.js'
import { registerQuickCommand } from './commands/quick.js'
import { registerStatusCommand } from './commands/status.js'
import { registerDownloadCommand } from './commands/download.js'
import { registerChatCommand } from './commands/chat.js'
import { registerConfigCommands } from './commands/config-cmd.js'
import { registerUploadCommand } from './commands/upload.js'
import { registerBlenderCommands } from './commands/blender.js'
import { registerUiCommand } from './commands/ui.js'
import { registerArchiveCommands } from './commands/archive.js'

/**
 * `-q` is a convenience alias for the `q` subcommand that also tolerates an
 * unquoted prompt — `graydient -q /wf /run:slug a woman on a beach --out x`
 * works the same as `graydient q "/wf /run:slug a woman on a beach" --out x`.
 * Needed because shells split unquoted args on whitespace, and Commander has
 * no built-in way to say "everything up to the next --flag is one string."
 * Rewrites argv before Commander ever sees it; `graydient q "..."` (already
 * quoted) and `graydient quick "..."` keep working unchanged either way.
 */
function rewriteQuickFlag(argv: string[]): string[] {
  if (argv[2] !== '-q' && argv[2] !== '--q') return argv
  const rest = argv.slice(3)
  const flagStart = rest.findIndex((a) => a.startsWith('--'))
  const promptTokens = flagStart === -1 ? rest : rest.slice(0, flagStart)
  const trailingFlags = flagStart === -1 ? [] : rest.slice(flagStart)
  return [argv[0], argv[1], 'q', promptTokens.join(' '), ...trailingFlags]
}

const argv = rewriteQuickFlag(process.argv)

const program = new Command()

program
  .name('graydient')
  .description('CLI for Graydient.ai — render, list workflows/skills/concepts, and pull down results from any shell, script, or coding agent.')
  .version('0.1.0')

registerAuthCommands(program)
registerWorkflowCommands(program)
registerConceptCommands(program)
registerSkillCommands(program)
registerRenderCommand(program)
registerQuickCommand(program)
registerStatusCommand(program)
registerDownloadCommand(program)
registerChatCommand(program)
registerConfigCommands(program)
registerUploadCommand(program)
registerBlenderCommands(program)
registerUiCommand(program)
registerArchiveCommands(program)

program
  .parseAsync(argv)
  .then(() => {
    // Most commands exit cleanly on their own once the event loop drains.
    // submitRender's WebSocket fallback (client.ts) is the exception — it can
    // stay connected past render_queued and leave the loop alive with nothing
    // left to do, which would hang a caller reading our stdout/stderr pipes
    // (e.g. the tui/ Go wrapper) waiting for EOF. An *unconditional* forced
    // process.exit() "fixed" that but broke upload.ts: on Windows, undici's
    // FormData/multipart request can still be closing a socket handle at the
    // exact instant of an abrupt exit, crashing the process with a libuv
    // assertion (UV_HANDLE_CLOSING) instead of exiting normally.
    //
    // Don't force-exit long-running commands like the web UI server
    const isServerCmd = argv.includes('ui') || argv.includes('kanban') || argv.includes('workspace')
    if (isServerCmd) return

    setTimeout(() => process.exit(process.exitCode ?? 0), 1500).unref()
  })
  .catch((err) => {
    console.error(err instanceof Error ? err.message : String(err))
    process.exitCode = 1
    setTimeout(() => process.exit(process.exitCode ?? 1), 1500).unref()
  })

import { Command } from 'commander'
import { callGraydientChat } from '../client.js'
import { printResult, printError } from '../output.js'

export function registerChatCommand(program: Command): void {
  program
    .command('chat <persona> <prompt>')
    .description('Send a synchronous message to a Graydient chat persona (e.g. "polly")')
    .option('--image-url <url>', 'Image URL for vision-capable personas')
    .option('--reply-to <responseId>', 'Continue a previous chat response')
    .option('--json', 'Output JSON')
    .action(async (persona: string, prompt: string, opts: { imageUrl?: string; replyTo?: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const result = await callGraydientChat(persona, prompt, { imageUrl: opts.imageUrl, replyTo: opts.replyTo })
        printResult(result, jsonMode, () => result.responseText)
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

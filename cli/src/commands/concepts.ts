import { Command } from 'commander'
import { fetchConcepts } from '../client.js'
import { printResult, printError } from '../output.js'

export function registerConceptCommands(program: Command): void {
  const concepts = program.command('concepts').description('Browse available LoRA / concept models')

  concepts
    .command('list')
    .description('List concepts')
    .option('--model-family <family>', 'Filter by model family')
    .option('--search <query>', 'Search by name')
    .option('--json', 'Output JSON')
    .action(async (opts: { modelFamily?: string; search?: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const items = await fetchConcepts(opts.modelFamily, opts.search)
        printResult(items, jsonMode, () =>
          items.map((c) => `${c.token}\t${c.name}${c.model_family ? `\t[${c.model_family}]` : ''}`).join('\n')
        )
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

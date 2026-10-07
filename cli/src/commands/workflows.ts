import { Command } from 'commander'
import { fetchWorkflows } from '../client.js'
import { printResult, printError } from '../output.js'

export function registerWorkflowCommands(program: Command): void {
  const workflows = program.command('workflows').description('Browse available Graydient workflows')

  workflows
    .command('list')
    .description('List all workflows')
    .option('--search <query>', 'Filter by name/slug/description substring')
    .option('--json', 'Output JSON')
    .action(async (opts: { search?: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        let all = await fetchWorkflows()
        if (opts.search) {
          const q = opts.search.toLowerCase()
          all = all.filter(
            (w) => w.slug.toLowerCase().includes(q) || w.name.toLowerCase().includes(q) || (w.description ?? '').toLowerCase().includes(q)
          )
        }
        printResult(all, jsonMode, () =>
          all.map((w) => `${w.slug}\t${w.name}${w.avg_elapsed ? `\t~${Math.round(w.avg_elapsed)}s` : ''}`).join('\n')
        )
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })

  workflows
    .command('show <slug>')
    .description('Show full details for one workflow, including field mappings')
    .option('--json', 'Output JSON')
    .action(async (slug: string, opts: { json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const all = await fetchWorkflows()
        const wf = all.find((w) => w.slug === slug)
        if (!wf) {
          printError(`Workflow not found: ${slug}`, jsonMode)
          process.exitCode = 1
          return
        }
        printResult(wf, jsonMode, () => {
          const modes = Object.entries(wf)
            .filter(([k, v]) => k.startsWith('supports_') && v)
            .map(([k]) => k.replace('supports_', ''))
            .join(', ')
          const fields = wf.field_mapping.map((f) => `  --${f.local_field}${f.help_text ? ` (${f.help_text})` : ''}`).join('\n')
          return `${wf.slug} — ${wf.name}\n${wf.description ?? ''}\nModes: ${modes}\nFields:\n${fields}`
        })
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

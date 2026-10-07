import { Command } from 'commander'
import { readFileSync } from 'node:fs'
import { ArchiveSession } from '../archive/session.js'
import * as ops from '../archive/ops.js'
import * as concepts from '../archive/concepts.js'
import { logProgress, printResult, printError } from '../output.js'

async function withSession<T>(headed: boolean | undefined, jsonMode: boolean, fn: (s: ArchiveSession) => Promise<T>): Promise<T | undefined> {
  let s: ArchiveSession | undefined
  try {
    s = await ArchiveSession.open({ headed })
    return await fn(s)
  } catch (e) {
    printError(e instanceof Error ? e.message : String(e), jsonMode)
    process.exitCode = 1
    return undefined
  } finally {
    await s?.close().catch(() => {})
  }
}

export function registerArchiveCommands(program: Command): void {
  const archive = program
    .command('archive')
    .description(
      'Drive the Graydient community archive web UI (the page behind Telegram `/archive`): list, restore, describe and publish ' +
        'workflows. There is no API for this, so it runs a real browser (Playwright) with a persistent login. ' +
        'Sessions expire: if a command says "not logged in", ask the user for a fresh /archive magic link and run `archive login <link>`.'
    )

  archive
    .command('login <magicLink>')
    .description('Log in with a magic link from Telegram `/archive` (links are credentials: never print or store them)')
    .option('--headed', 'Show the browser window')
    .action(async (link: string, opts: { headed?: boolean }) => {
      const r = await withSession(opts.headed, false, (s) => ops.login(s, link))
      if (r) logProgress(`Logged in. Community site: ${r.origin}`)
    })

  archive
    .command('status')
    .description('Check whether the stored archive session is still logged in')
    .option('--json', 'Output JSON')
    .action(async (opts: { json?: boolean }) => {
      const r = await withSession(false, !!opts.json, ops.status)
      if (r) printResult(r, !!opts.json, (d: any) => (d.loggedIn ? `Logged in as ${d.user ?? '?'} on ${d.origin}` : 'Not logged in'))
      if (r && !r.loggedIn) process.exitCode = 1
    })

  archive
    .command('list')
    .description('List your workflows as id + name (names are NOT unique: use the WFxxxx id when in doubt)')
    .option('--everyone', 'Include other authors (default: only yours)')
    .option('--public-only', 'Leave out private workflows')
    .option('--json', 'Output JSON')
    .action(async (opts: { everyone?: boolean; publicOnly?: boolean; json?: boolean }) => {
      const r = await withSession(false, !!opts.json, (s) => ops.listWorkflows(s, { mine: !opts.everyone, includePrivate: !opts.publicOnly }))
      if (r) printResult(r, !!opts.json, () => (r as ops.WorkflowRow[]).map((w) => `${w.id}\t${w.name}`).join('\n'))
    })

  archive
    .command('show <workflow>')
    .description('Read a workflow Basics tab: name, version, description, public/private, feature flags, image present')
    .option('--json', 'Output JSON')
    .action(async (ref: string, opts: { json?: boolean }) => {
      const r = await withSession(false, !!opts.json, async (s) => ops.readBasics(s, (await ops.resolveWorkflow(s, ref)).id))
      if (r)
        printResult(r, !!opts.json, (d: any) => {
          const on = Object.entries(d.flags).filter(([, v]) => v).map(([k]) => k).join(', ')
          return `${d.id}  ${d.name}  v${d.version}\npublic: ${d.isPublic}\nflags on: ${on || '(none)'}\nexample image: ${d.hasExampleImage}\ndescription: ${d.description || '(empty)'}`
        })
    })

  archive
    .command('restore <workflow> <backupJson>')
    .description(
      'Restore a GraydientWorkflow-*.json onto an EXISTING workflow (replaces its graph, fields and models). ' +
        'Reports flags/description that did not carry over; --fix applies them.'
    )
    .option('--fix', 'Apply feature flags and an empty description from the JSON, then save')
    .option('--json', 'Output JSON')
    .action(async (ref: string, file: string, opts: { fix?: boolean; json?: boolean }) => {
      const r = await withSession(false, !!opts.json, async (s) => ops.restore(s, (await ops.resolveWorkflow(s, ref)).id, file, { fix: opts.fix }))
      if (r)
        printResult(r, !!opts.json, (d: any) => {
          const diffs = d.flagDiffs.length
            ? d.flagDiffs.map((x: any) => `  ${x.key}: json=${x.json} site=${x.site}${d.fixed ? ' (fixed)' : ''}`).join('\n')
            : '  none'
          return `Restored ${d.id}: v${d.versionBefore} -> v${d.versionAfter}\nFlag differences:\n${diffs}\ndescription on site: ${d.descriptionOnSite}`
        })
    })

  archive
    .command('new <backupJson>')
    .description('Create a NEW workflow: makes an empty stub, restores the JSON onto it, names it, fixes flags. Stays private.')
    .requiredOption('--name <name>', 'Workflow name')
    .option('--json', 'Output JSON')
    .action(async (file: string, opts: { name: string; json?: boolean }) => {
      const r = await withSession(false, !!opts.json, async (s) => {
        const id = await ops.createStub(s)
        logProgress(`Created stub ${id}`)
        const res = await ops.restore(s, id, file, { fix: true })
        const b = await ops.editMeta(s, id, { name: opts.name })
        return { ...res, name: b.name }
      })
      if (r) printResult(r, !!opts.json, (d: any) => `Created ${d.id} "${d.name}" at v${d.versionAfter} (private)`)
    })

  archive
    .command('meta <workflow>')
    .description('Edit Basics: name, description, example image, visibility. Publishing needs --public --confirm-public.')
    .option('--name <name>')
    .option('--description <text>')
    .option('--description-file <path>', 'Read the description from a file')
    .option('--image <path>', 'Example/cover image (jpg or png)')
    .option('--private', 'Set private')
    .option('--public', 'Make public (publishing action: only with the user\'s explicit approval)')
    .option('--confirm-public', 'Required alongside --public; asserts the user approved publishing this workflow')
    .option('--json', 'Output JSON')
    .action(async (ref: string, opts: any) => {
      const jsonMode = !!opts.json
      if (opts.public && !opts.confirmPublic) {
        printError('--public needs --confirm-public. Publishing is the user\'s call: ask them first.', jsonMode)
        process.exitCode = 1
        return
      }
      if (opts.public && opts.private) {
        printError('Choose --public or --private, not both', jsonMode)
        process.exitCode = 1
        return
      }
      const description = opts.descriptionFile ? readFileSync(opts.descriptionFile, 'utf-8').trim() : opts.description
      const r = await withSession(false, jsonMode, async (s) =>
        ops.editMeta(s, (await ops.resolveWorkflow(s, ref)).id, {
          name: opts.name,
          description,
          image: opts.image,
          isPublic: opts.public ? true : opts.private ? false : undefined,
        })
      )
      if (r) printResult(r, jsonMode, (d: any) => `${d.id} "${d.name}" v${d.version} public=${d.isPublic} image=${d.hasExampleImage}`)
    })

  const concept = archive
    .command('concept')
    .description('Manage your Graydient concepts (LoRAs) in the web UI behind Telegram `/concept /edit`. Same login as the rest of `archive`.')

  concept
    .command('list')
    .description('Dump the My Concepts page (text + concept links)')
    .action(async () => {
      const r = await withSession(false, true, (s) => concepts.listConcepts(s))
      if (r) printResult(r, true)
    })

  concept
    .command('new')
    .description('Create a concept (SAVES for real). Download URL must be a public Hugging Face /resolve/ link, not Civitai.')
    .requiredOption('--name <name>', 'Unique concept name (add month/year if taken)')
    .requiredOption('--token <token>', 'Prompt token / activation keyword')
    .requiredOption('--url <url>', 'Public Hugging Face direct file URL')
    .requiredOption('--family <family>', `Model family: ${concepts.MODEL_FAMILIES.join(', ')}`)
    .option('--type <type>', `Type: ${concepts.CONCEPT_TYPES.join(', ')}`, 'lora')
    .option('--description <text>')
    .option('--description-file <path>')
    .option('--info-url <url>', 'Page about the model, e.g. its Civitai page')
    .option('--example-url <url>', 'Example image URL')
    .option('--tags <csv>', 'Comma-separated tags from the site list (e.g. video,effects)')
    .option('--nsfw', 'Mark as adult content')
    .option('--disabled', 'Save with Enabled unchecked')
    .option('--json', 'Output JSON')
    .action(async (o: any) => {
      const description = o.descriptionFile ? readFileSync(o.descriptionFile, 'utf-8').trim() : o.description
      const r = await withSession(false, !!o.json, (s) =>
        concepts.createConcept(s, {
          name: o.name, token: o.token, url: o.url, family: o.family, type: o.type, description,
          infoUrl: o.infoUrl, exampleUrl: o.exampleUrl, nsfw: !!o.nsfw, enabled: !o.disabled,
          tags: o.tags ? String(o.tags).split(',').map((t) => t.trim()).filter(Boolean) : [],
        })
      )
      if (r) {
        printResult(r, !!o.json, (d: any) => (d.saved ? `${d.message}\nAllow ~3-5 min to install plus ~3-5 min to replicate before use.` : `Save not confirmed:\n${d.message}`))
        if (!r.saved) process.exitCode = 1
      }
    })

  concept
    .command('edit <concept>')
    .description('Edit an existing concept (by name or numeric id); only the options you pass change. Re-passing --tags REPLACES the tag set.')
    .option('--name <name>')
    .option('--token <token>')
    .option('--url <url>')
    .option('--family <family>')
    .option('--type <type>')
    .option('--description <text>')
    .option('--description-file <path>')
    .option('--info-url <url>')
    .option('--example-url <url>')
    .option('--tags <csv>')
    .option('--nsfw <bool>', 'true|false')
    .option('--enabled <bool>', 'true|false')
    .option('--json', 'Output JSON')
    .action(async (ref: string, o: any) => {
      const description = o.descriptionFile ? readFileSync(o.descriptionFile, 'utf-8').trim() : o.description
      const b = (v?: string) => (v === undefined ? undefined : v === 'true')
      const r = await withSession(false, !!o.json, (s) =>
        concepts.editConcept(s, ref, {
          name: o.name, token: o.token, url: o.url, family: o.family, type: o.type, description,
          infoUrl: o.infoUrl, exampleUrl: o.exampleUrl, nsfw: b(o.nsfw), enabled: b(o.enabled),
          tags: o.tags === undefined ? undefined : String(o.tags).split(',').map((t) => t.trim()).filter(Boolean),
        })
      )
      if (r) {
        printResult(r, !!o.json, (d: any) => d.message)
        if (!r.saved) process.exitCode = 1
      }
    })

  concept
    .command('delete <concept>')
    .description('PERMANENTLY delete a concept (by name or id). Needs --confirm-delete: only after the user explicitly asks.')
    .option('--confirm-delete', 'Asserts the user asked for this concept to be deleted')
    .option('--json', 'Output JSON')
    .action(async (ref: string, o: any) => {
      if (!o.confirmDelete) {
        printError('delete needs --confirm-delete. Deleting is permanent: ask the user first.', !!o.json)
        process.exitCode = 1
        return
      }
      const r = await withSession(false, !!o.json, (s) => concepts.deleteConcept(s, ref))
      if (r) printResult(r, !!o.json, (d: any) => `Deleted concept ${d.id} <${d.name}>`)
    })

  archive
    .command('dump <workflow>')
    .description('Dump any edit tab (Basics, Details, Fields, Models, Logs, Backup, Use): every form control plus page text')
    .requiredOption('--tab <tab>', 'Tab name')
    .action(async (ref: string, opts: { tab: string }) => {
      const r = await withSession(false, true, async (s) => ops.dumpTab(s, (await ops.resolveWorkflow(s, ref)).id, opts.tab))
      if (r) printResult(r, true)
    })
}

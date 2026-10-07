import { Command } from 'commander'
import { fetchSkills, fetchSkillDetail, submitSkill, resolveFinalMedia } from '../client.js'
import { logProgress, printResult, printError, downloadFile } from '../output.js'
import { resolveMediaInput } from '../upload.js'

export function registerSkillCommands(program: Command): void {
  const skills = program.command('skills').description('Browse Graydient skills (LLM-driven workflow selection)')

  skills
    .command('list')
    .description('List available skills')
    .option('--json', 'Output JSON')
    .action(async (opts: { json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const items = await fetchSkills()
        printResult(items, jsonMode, () => items.map((s) => `${s.slug}\t${s.name}`).join('\n'))
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })

  skills
    .command('show <slug>')
    .description('Show full details for one skill')
    .option('--json', 'Output JSON')
    .action(async (slug: string, opts: { json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const skill = await fetchSkillDetail(slug)
        if (!skill) {
          printError(`Skill not found: ${slug}`, jsonMode)
          process.exitCode = 1
          return
        }
        printResult(skill, jsonMode, () => `${skill.slug} — ${skill.name}\n${skill.description ?? ''}`)
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })

  program
    .command('skill-run <prompt>')
    .description('Auto-select (or use --skill) a skill from natural language, then render it')
    .option('--skill <slug>', 'Use this specific skill instead of auto-selecting')
    .option('--init-image <url-or-path>', 'Source image for the skill: an http(s) URL, or a local file path (auto-uploaded to a temporary expiring host)')
    .option('--out <path>', 'Download resulting media to this file or directory')
    .option('--json', 'Output JSON')
    .action(async (prompt: string, opts: { skill?: string; initImage?: string; out?: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      let initImage: string | undefined
      try {
        if (opts.initImage) initImage = await resolveMediaInput(opts.initImage)
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
        return
      }
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 20 * 60 * 1000)
      try {
        const result = await submitSkill(
          prompt,
          (name, data) => logProgress(`[${name}] ${JSON.stringify(data).slice(0, 200)}`),
          opts.skill,
          initImage ? { initImage } : undefined,
          controller.signal
        )
        clearTimeout(timeout)

        const media = await resolveFinalMedia(result)

        if (!media.length) {
          printResult(
            { renderHash: result.renderHash, status: 'incomplete', nextCommand: `graydient status ${result.renderHash} --json` },
            jsonMode,
            () =>
              `Render ${result.renderHash} was queued but its media wasn't ready before timing out. ` +
              `This does NOT mean the render failed — video in particular can finish server-side after this CLI stops waiting. ` +
              `Run this exact command in a bit to check again (it re-queries fresh, no re-render): graydient status ${result.renderHash} --json`
          )
          process.exitCode = 1
          return
        }

        let savedPaths: string[] = []
        if (opts.out) {
          savedPaths = await Promise.all(media.map((m, i) => downloadFile(m.url, opts.out!, { mediaType: m.mediaType, index: i })))
        }

        printResult(
          { renderHash: result.renderHash, media, savedPaths },
          jsonMode,
          () =>
            `render_hash: ${result.renderHash}\n` +
            `${savedPaths.length ? 'Remote URL(s):' : 'Remote URL(s) — nothing saved locally, pass --out <path> to download:'}\n${media.map((m) => m.url).join('\n')}` +
            (savedPaths.length ? `\nSaved locally:\n${savedPaths.join('\n')}` : '')
        )
      } catch (e) {
        clearTimeout(timeout)
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

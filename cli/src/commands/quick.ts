import { Command } from 'commander'
import { submitRenderRaw, resolveFinalMedia } from '../client.js'
import { logProgress, printResult, printError, downloadFile } from '../output.js'
import { resolveMediaInput } from '../upload.js'

export function registerQuickCommand(program: Command): void {
  program
    .command('q <telegramCommand>')
    .alias('quick')
    // Note: `graydient -q ...` (unquoted, no subcommand) also works — index.ts
    // rewrites it into this same `q` invocation before Commander parses argv.
    .description(
      'Submit a render using raw Telegram/PirateDiffusion command syntax — no CLI-side prompt parsing at all, ' +
        'the exact same slash-command nomenclature documented at https://graydient.ai/pirate-diffusion-guide/ and ' +
        'cataloged in docs/telegram-prompt-syntax.md (workflows, /steps, /guidance, /sampler, /portrait, #recipes, ' +
        '(( )) / [[ ]] weighting, <concept> tokens, /compose zones, etc.) is sent straight through in the `prompt` ' +
        'field for Graydient\'s own backend to parse, same as it does for Telegram/webui input. Use this when you ' +
        'have (or can find) a known-good Telegram-style command and want it to behave identically over the API — ' +
        'use `render`/`skill-run` instead when you want this CLI\'s own --workflow/--negative/--init-* flags. ' +
        'Example: graydient q "/wf /run:video-wan22 cinematic low angle shot of a fox running through snow /length:97 /fps:24" --out ./out/fox.mp4'
    )
    .option('--init-image <url-or-path>', 'Source image: an http(s) URL, or a local file path (auto-uploaded to a temporary expiring host)')
    .option('--init-video <url-or-path>', 'Source video (for vid2vid/lipsync workflows): an http(s) URL, or a local file path (auto-uploaded the same way)')
    .option('--init-audio <url-or-path>', 'Source audio: an http(s) URL, or a local file path (auto-uploaded the same way)')
    .option('--placeholder <key=url-or-path>', 'Extra reference media (e.g. /image1:URL1 in the command needs --placeholder URL1=./ref.png). Repeatable.', (val: string, prev: string[]) => [...prev, val], [] as string[])
    .option('--out <path>', 'Download resulting media to this file (single output) or directory (multiple outputs)')
    .option('--json', 'Output JSON (a single result object on stdout; progress still goes to stderr)')
    .option('--timeout <minutes>', 'Give up waiting after this many minutes', '20')
    .action(
      async (
        telegramCommand: string,
        opts: {
          initImage?: string
          initVideo?: string
          initAudio?: string
          placeholder: string[]
          out?: string
          json?: boolean
          timeout: string
        }
      ) => {
        const jsonMode = !!opts.json

        let initImage: string | undefined
        let initVideo: string | undefined
        let initAudio: string | undefined
        let placeholders: Record<string, string> | undefined
        try {
          if (opts.initImage) initImage = await resolveMediaInput(opts.initImage)
          if (opts.initVideo) initVideo = await resolveMediaInput(opts.initVideo)
          if (opts.initAudio) initAudio = await resolveMediaInput(opts.initAudio)
          if (opts.placeholder.length) {
            placeholders = {}
            for (const pair of opts.placeholder) {
              const eq = pair.indexOf('=')
              if (eq < 0) throw new Error(`--placeholder must be key=url-or-path, got: ${pair}`)
              const key = pair.slice(0, eq)
              placeholders[key] = await resolveMediaInput(pair.slice(eq + 1))
            }
          }
        } catch (e) {
          printError(e instanceof Error ? e.message : String(e), jsonMode)
          process.exitCode = 1
          return
        }

        const controller = new AbortController()
        const timeoutMs = Math.max(1, Number(opts.timeout) || 20) * 60 * 1000
        const timeout = setTimeout(() => controller.abort(), timeoutMs)

        try {
          const result = await submitRenderRaw(
            telegramCommand,
            (name, data) => {
              // the hash sits past the 200-char cut and is the only way to `status` a render after --timeout
              const hash = (data as Record<string, unknown>)?.render_hash
              logProgress(`[${name}]${hash ? ` render_hash=${hash}` : ''} ${JSON.stringify(data).slice(0, 200)}`)
            },
            { initImage, initVideo, initAudio, placeholders },
            controller.signal
          )
          clearTimeout(timeout)

          const media = await resolveFinalMedia(result)

          if (!media.length) {
            printResult(
              { renderHash: result.renderHash, status: 'incomplete', nextCommand: `graydient status ${result.renderHash} --json` },
              jsonMode,
              () =>
                `Render ${result.renderHash} was queued but its media wasn't ready within ${opts.timeout}m. ` +
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
      }
    )
}

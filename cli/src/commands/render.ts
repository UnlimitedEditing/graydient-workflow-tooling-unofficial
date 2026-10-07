import { Command } from 'commander'
import { submitRender, resolveFinalMedia } from '../client.js'
import { logProgress, printResult, printError, downloadFile } from '../output.js'
import { resolveMediaInput } from '../upload.js'

export function registerRenderCommand(program: Command): void {
  program
    .command('render <prompt>')
    .description(
      'Submit a render and wait for it to finish. <prompt> accepts the same mini-language as the ForgeExpress app: /run:slug, /key:value, [negative], <concept>. ' +
        'Text-to-image example: graydient render "a red fox in a snowy forest /run:sdxl" --out ./out/. ' +
        'Text-to-video example: graydient render "a cinematic drone shot over mountains /run:video-wan22" --out ./out/video.mp4 --timeout 10. ' +
        'Image-to-video example: graydient render "the fox starts running /run:animate-wan22" --init-image ./fox.png --out ./out/video.mp4. ' +
        'IMPORTANT: without --out, media is returned only as a remote URL — nothing is saved to disk. ' +
        'Run `graydient workflows list --search video` to find current video workflow slugs; slugs change over time so do not hardcode ones from examples.'
    )
    .option('--workflow <slug>', 'Workflow slug (same as /run:slug in the prompt)')
    .option('--negative <text>', 'Negative prompt (same as [text] in the prompt)')
    .option('--init-image <url-or-path>', 'Source image: an http(s) URL, or a local file path (auto-uploaded to a temporary expiring host since Graydient has no upload endpoint)')
    .option('--init-video <url-or-path>', 'Source video (for vid2vid/lipsync workflows): an http(s) URL, or a local file path (auto-uploaded the same way)')
    .option('--init-audio <url-or-path>', 'Source audio: an http(s) URL, or a local file path (auto-uploaded the same way)')
    .option('--init-image-url <url-or-path>', 'Sets init_image_url directly instead of init_image -- some custom workflows (field_mapping-defined, not the built-in image slot) read this field name specifically instead. See D:\\tripostl\\HIGGS-CLONE-HANDOFF.md for the audio equivalent; same reasoning applies. Mechanism unconfirmed as of 2026-08-02.')
    .option('--init-image-filename <filename>', 'Sets init_image_filename directly -- a bare filename already uploaded to Graydient, not a URL. Mechanism unconfirmed as of 2026-08-02.')
    .option('--init-video-url <url-or-path>', 'Sets init_video_url directly instead of init_video, for the same field_mapping reason as --init-image-url. Mechanism unconfirmed as of 2026-08-02.')
    .option('--init-video-filename <filename>', 'Sets init_video_filename directly. Mechanism unconfirmed as of 2026-08-02.')
    .option('--init-audio-url <url-or-path>', 'Sets init_audio_url directly instead of init_audio -- confirmed needed for clone-higgs per D:\\tripostl\\HIGGS-CLONE-HANDOFF.md section 2 ("some Graydient submission paths populate this instead of init_audio, not because you chose to, but because of which client path submitted the job"). The actual server-side routing into the workflow node is unconfirmed as of 2026-08-02 -- setting this alone was tested live and did NOT reach the ComfyUI node.')
    .option('--init-audio-filename <filename>', 'Sets init_audio_filename directly -- a bare filename already uploaded to Graydient, not a URL. Mechanism unconfirmed as of 2026-08-02.')
    .option('--init-mesh-url <url-or-path>', 'Sets init_mesh_url directly -- an http(s) URL, or a local mesh file path (GLB/OBJ/PLY/STL/3MF/DAE) auto-uploaded the same way as --init-image. For mesh-texturing workflows like shape2texture-hy3d (gen_hy3d21_texture_v1.py). Mechanism unconfirmed as of 2026-08-29 -- see the SourceMedia docstring in client.ts.')
    .option('--placeholder <key=url-or-path>', 'Extra reference media for multi-image workflows (e.g. /image1:URL1 in the prompt needs --placeholder URL1=./ref.png). Repeatable.', (val: string, prev: string[]) => [...prev, val], [] as string[])
    .option('--out <path>', 'Download resulting media to this file (single output) or directory (multiple outputs)')
    .option('--json', 'Output JSON (a single result object on stdout; progress still goes to stderr)')
    .option('--timeout <minutes>', 'Give up waiting after this many minutes', '20')
    .action(
      async (
        prompt: string,
        opts: {
          workflow?: string
          negative?: string
          initImage?: string
          initVideo?: string
          initAudio?: string
          initImageUrl?: string
          initImageFilename?: string
          initVideoUrl?: string
          initVideoFilename?: string
          initAudioUrl?: string
          initAudioFilename?: string
          initMeshUrl?: string
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
        let initImageUrl: string | undefined
        let initVideoUrl: string | undefined
        let initAudioUrl: string | undefined
        let initMeshUrl: string | undefined
        let placeholders: Record<string, string> | undefined
        try {
          if (opts.initImage) initImage = await resolveMediaInput(opts.initImage)
          if (opts.initVideo) initVideo = await resolveMediaInput(opts.initVideo)
          if (opts.initAudio) initAudio = await resolveMediaInput(opts.initAudio)
          // The _url variants are URLs/paths needing the same upload
          // resolution as the base fields. The _filename variants are bare
          // filenames ALREADY uploaded to Graydient (per HIGGS-CLONE-HANDOFF.md
          // section 2) -- passed through as-is, never resolved/uploaded.
          if (opts.initImageUrl) initImageUrl = await resolveMediaInput(opts.initImageUrl)
          if (opts.initVideoUrl) initVideoUrl = await resolveMediaInput(opts.initVideoUrl)
          if (opts.initAudioUrl) initAudioUrl = await resolveMediaInput(opts.initAudioUrl)
          if (opts.initMeshUrl) initMeshUrl = await resolveMediaInput(opts.initMeshUrl)
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

        const rawInput = opts.negative ? `${prompt} [${opts.negative}]` : prompt
        const controller = new AbortController()
        const timeoutMs = Math.max(1, Number(opts.timeout) || 20) * 60 * 1000
        const timeout = setTimeout(() => controller.abort(), timeoutMs)

        try {
          const result = await submitRender(
            rawInput,
            opts.workflow,
            (name, data) => logProgress(`[${name}] ${JSON.stringify(data).slice(0, 200)}`),
            {
              initImage,
              initVideo,
              initAudio,
              initImageUrl,
              initImageFilename: opts.initImageFilename,
              initVideoUrl,
              initVideoFilename: opts.initVideoFilename,
              initAudioUrl,
              initAudioFilename: opts.initAudioFilename,
              initMeshUrl,
              placeholders,
            },
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

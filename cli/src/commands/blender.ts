import { Command } from 'commander'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fetchRenderInfo, resolveAllMedia } from '../client.js'
import { runHeadlessFinish } from '../blender.js'
import { printResult, printError, downloadFile } from '../output.js'

function looksLikeLocalGlb(source: string): boolean {
  return /\.glb$/i.test(source)
}

async function resolveSourceGlb(source: string): Promise<string> {
  if (looksLikeLocalGlb(source)) return source

  // Otherwise treat it as a render hash and pull its GLB media down first.
  const info = await fetchRenderInfo(source)
  const media = resolveAllMedia(info)
  const glbMedia = media.find((m) => m.mediaType === 'model/gltf-binary' || m.mediaType === 'model' || /\.glb(\?|$)/i.test(m.url))
  if (!glbMedia) throw new Error(`No GLB media found on render ${source}`)

  const dest = join(tmpdir(), `graydient-blender-${source}.glb`)
  return downloadFile(glbMedia.url, dest)
}

export function registerBlenderCommands(program: Command): void {
  const blender = program.command('blender').description('Headless Blender finishing pipeline for generative GLB output')

  blender
    .command('finish <source>')
    .description(
      'Turn a raw generative GLB into a game-ready one: retopo, UV unwrap, and bake vertex colors ' +
        'into a BaseColor texture (vertex-color-only meshes silently lose their color on glTF re-export ' +
        'otherwise). <source> is either a render hash from `graydient render`/`graydient status` or a ' +
        'local .glb path. Requires GRAYDIENT_BLENDER_BIN (defaults to "blender" on PATH) and ' +
        'GRAYDIENT_BLENDER_FINISH_SCRIPT (path to finish_asset.py in the blender-DDIY repo) — see ' +
        'that repo\'s docs/graydient-blender-bridge.md.'
    )
    .requiredOption('--out <path>', 'Where to write the finished .glb')
    .option('--intensity <0-1>', 'Retopo intensity, 0 = ~500 tris, 1 = ~30k tris', '0.5')
    .option('--bake-size <px>', 'Baked texture resolution (square)', '1024')
    .option('--json', 'Output JSON')
    .action(async (source: string, opts: { out: string; intensity: string; bakeSize: string; json?: boolean }) => {
      const jsonMode = !!opts.json
      try {
        const sourcePath = await resolveSourceGlb(source)
        const report = await runHeadlessFinish(sourcePath, opts.out, {
          intensity: Number(opts.intensity),
          bakeSize: Number(opts.bakeSize),
        })
        printResult(
          report,
          jsonMode,
          () =>
            `Finished: ${report.out}\n` +
            `Source: ${report.source_stats?.vertices} verts / ${report.source_stats?.faces} faces\n` +
            `Retopo: ${report.retopo_stats?.vertices} verts / ${report.retopo_stats?.faces} faces\n` +
            `UV unwrapped: ${report.uv_unwrapped}\n` +
            `Vertex colors baked: ${report.bake?.baked} ${report.bake?.reason ? `(${report.bake.reason})` : ''}`
        )
      } catch (e) {
        printError(e instanceof Error ? e.message : String(e), jsonMode)
        process.exitCode = 1
      }
    })
}

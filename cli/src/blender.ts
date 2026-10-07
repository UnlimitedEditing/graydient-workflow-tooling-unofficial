// Bridge to the headless Blender finishing pipeline that lives in the
// blender-DDIY repo (scripts/blender/finish_asset.py). Kept as its own module
// so the two things that make this swappable stay in one place:
//   1. how we get a source GLB (currently: a Graydient render's media URL)
//   2. how we hand it to a mesh-finishing backend (currently: headless Blender)
// See D:\DonoWIN\blender-DDIY\docs\graydient-blender-bridge.md for the full
// seam writeup and how to point this at a different backend (e.g. a
// persistent ComfyUI instance) later without touching callers.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'

export interface FinishReport {
  ok: boolean
  in: string
  out: string
  source_stats?: { vertices: number; faces: number }
  retopo_stats?: { vertices: number; faces: number }
  vertex_colors_transferred?: boolean
  uv_unwrapped?: boolean
  bake?: { baked: boolean; image?: string; size?: number; reason?: string }
  error?: string
}

export interface FinishOptions {
  intensity?: number
  bakeSize?: number
}

function resolveBlenderBin(): string {
  return process.env.GRAYDIENT_BLENDER_BIN || 'blender'
}

function resolveFinishScript(): string {
  const fromEnv = process.env.GRAYDIENT_BLENDER_FINISH_SCRIPT
  if (fromEnv) return fromEnv
  throw new Error(
    'GRAYDIENT_BLENDER_FINISH_SCRIPT is not set. Point it at ' +
      'scripts/blender/finish_asset.py in the blender-DDIY repo ' +
      '(e.g. D:\\DonoWIN\\blender-DDIY\\scripts\\blender\\finish_asset.py).'
  )
}

/**
 * Run the headless Blender finishing pipeline (retopo -> UV unwrap -> bake
 * vertex colors to a BaseColor texture -> export) on a local source GLB.
 * Blender itself decides success/failure and reports it as the last line of
 * stdout as JSON -- everything else on stdout/stderr is Blender's own log
 * noise, not part of the contract.
 */
export async function runHeadlessFinish(sourcePath: string, outPath: string, opts: FinishOptions = {}): Promise<FinishReport> {
  const script = resolveFinishScript()
  if (!existsSync(script)) throw new Error(`Blender finishing script not found: ${script}`)
  if (!existsSync(sourcePath)) throw new Error(`Source GLB not found: ${sourcePath}`)

  const args = ['-b', '--python', script, '--', '--in', sourcePath, '--out', outPath]
  if (opts.intensity !== undefined) args.push('--intensity', String(opts.intensity))
  if (opts.bakeSize !== undefined) args.push('--bake-size', String(opts.bakeSize))

  const bin = resolveBlenderBin()
  const child = spawn(bin, args, { stdio: ['ignore', 'pipe', 'pipe'] })

  let stdout = ''
  child.stdout.on('data', (d) => (stdout += d.toString()))
  child.stderr.on('data', (d) => process.stderr.write(d)) // Blender's own log noise, useful for debugging

  const exitCode: number = await new Promise((resolve, reject) => {
    child.on('error', (e) => reject(new Error(`Failed to launch Blender ("${bin}"): ${e.message}`)))
    child.on('close', (code) => resolve(code ?? 1))
  })

  // Blender's own process (not our script) can print trailing lines like
  // "Blender quit" after our script's final print(), so scan from the bottom
  // for the last line that parses as JSON rather than assuming it's literally
  // the last line of output.
  const lines = stdout.trim().split('\n').filter(Boolean)
  let report: FinishReport | undefined
  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      report = JSON.parse(lines[i]) as FinishReport
      break
    } catch {
      continue
    }
  }
  if (!report) {
    throw new Error(`Blender produced no JSON report on stdout (exit code ${exitCode})`)
  }

  if (!report.ok) {
    throw new Error(report.error || `Blender finishing pipeline failed (exit code ${exitCode})`)
  }

  return report
}

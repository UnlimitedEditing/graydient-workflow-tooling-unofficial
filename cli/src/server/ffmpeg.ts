import { spawn } from 'node:child_process'
import { existsSync, writeFileSync } from 'node:fs'
import { join, basename } from 'node:path'
import { REELS_DIR, ensureDirectories } from './store.js'

const KNOWN_FFMPEG_PATHS = [
  'C:\\ffmpeg\\bin\\ffmpeg.exe',
  'ffmpeg.exe',
  'ffmpeg',
]

export function findFfmpegBinary(): string {
  for (const p of KNOWN_FFMPEG_PATHS) {
    if (existsSync(p)) return p
  }
  return 'ffmpeg'
}

export interface ReelExportResult {
  outputFilename: string
  outputPath: string
  webUrl: string
  clipCount: number
  clips: Array<{ filename: string; prompt?: string }>
}

export async function compileVideoReel(
  videoPaths: string[],
  clipInfo?: Array<{ filename: string; prompt?: string }>
): Promise<ReelExportResult> {
  ensureDirectories()

  // Filter to paths that actually exist
  const validPaths = videoPaths.filter((p) => existsSync(p))
  if (validPaths.length === 0) {
    throw new Error('No valid existing video files provided for compilation.')
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const outputFilename = `reel_${timestamp}.mp4`
  const outputPath = join(REELS_DIR, outputFilename)
  const listFilePath = join(REELS_DIR, `concat_${timestamp}.txt`)

  // Create concat file list
  // ffmpeg concat demuxer: file 'path'
  const fileLines = validPaths.map((p) => `file '${p.replace(/'/g, "'\\''")}'`).join('\n')
  writeFileSync(listFilePath, fileLines, 'utf-8')

  const ffmpegBin = findFfmpegBinary()

  // First try fast concat demuxer with re-encoding to guarantee standard yuv420p & aac
  return new Promise<ReelExportResult>((resolve, reject) => {
    // args: -y -f concat -safe 0 -i listFilePath -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart outputPath
    const args = [
      '-y',
      '-f', 'concat',
      '-safe', '0',
      '-i', listFilePath,
      '-c:v', 'libx264',
      '-pix_fmt', 'yuv420p',
      '-c:a', 'aac',
      '-movflags', '+faststart',
      outputPath,
    ]

    const child = spawn(ffmpegBin, args, { windowsHide: true })
    let stderrLog = ''

    child.stderr?.on('data', (d) => {
      stderrLog += d.toString()
    })

    child.on('error', (err) => {
      reject(new Error(`Failed to start ffmpeg: ${err.message}`))
    })

    child.on('exit', (code) => {
      if (code === 0 && existsSync(outputPath)) {
        // Also write a sidecar text file with prompts for the reel!
        const resolvedClips = clipInfo || validPaths.map((p) => ({ filename: basename(p), prompt: undefined as string | undefined }))
        const sidecarText = resolvedClips
          .map((c, i) => `[Clip ${i + 1}] ${c.filename}\n${c.prompt ? `Prompt: ${c.prompt}\n` : ''}`)
          .join('\n---\n')
        try {
          const sidecarPath = join(REELS_DIR, `reel_${timestamp}_prompts.txt`)
          writeFileSync(sidecarPath, sidecarText, 'utf-8')
        } catch {
          /* ignore */
        }

        resolve({
          outputFilename,
          outputPath,
          webUrl: `/api/media/reels/${encodeURIComponent(outputFilename)}`,
          clipCount: validPaths.length,
          clips: resolvedClips,
        })
      } else {
        console.error('FFmpeg reel compilation failed:', stderrLog.slice(-500))
        reject(new Error(`FFmpeg exited with code ${code}: ${stderrLog.slice(-300)}`))
      }
    })
  })
}

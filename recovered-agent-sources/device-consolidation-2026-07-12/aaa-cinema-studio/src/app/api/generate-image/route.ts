import { NextRequest } from 'next/server'
import { image, type ImageSize } from '@/lib/zai'
import { json, err, base64ToDataUrl } from '@/lib/server-utils'
import { db } from '@/lib/db'
import { buildFidelityPrompt, getPlatform } from '@/lib/platforms'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

// POST /api/generate-image
// body: { prompt, size, type, title, projectId?, save?: boolean, platform? }
// platform: a Platform id from src/lib/platforms.ts — bakes era-accurate
// visual signatures (PS1 wobble, N64 fog, PS2 interlace, PS5 ray tracing, etc.)
// into the prompt. Omit for modern photoreal default.
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const prompt = (body.prompt ?? '').trim()
    if (!prompt) return err('prompt required', 400)
    const size = (body.size ?? '1344x768') as ImageSize
    const platformId = body.platform as string | undefined
    const platform = getPlatform(platformId)

    // Assemble the fidelity-aware prompt: subject + platform signature + era booster.
    const finalPrompt = buildFidelityPrompt(prompt, platformId)

    const b64 = await image(finalPrompt, size)
    if (!b64) return err('Image model returned empty result', 502)
    const dataUrl = base64ToDataUrl(b64)

    let asset = null
    if (body.save !== false) {
      asset = await db.asset.create({
        data: {
          projectId: body.projectId ?? null,
          type: body.type ?? 'concept',
          title: body.title ?? prompt.slice(0, 80),
          prompt,
          imageUrl: dataUrl,
          meta: JSON.stringify({ size, platform: platform?.id ?? null, platformLabel: platform?.label ?? null }),
        },
      })
    }

    return json({ ok: true, data: { imageUrl: dataUrl, asset, platform: platform?.id ?? null } })
  } catch (e: any) {
    return err(e?.message ?? 'Image generation failed')
  }
}

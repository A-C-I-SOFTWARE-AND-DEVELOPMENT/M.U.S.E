import { NextRequest } from 'next/server'
import { tts } from '@/lib/zai'
import { json, err, audioBase64ToDataUrl } from '@/lib/server-utils'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'
export const maxDuration = 120

// Voice Stage — TTS.
// body: { text, voice, speed, projectId?, characterId?, save?: boolean }
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const text = (body.text ?? '').trim()
    if (!text) return err('text required', 400)
    const voice = body.voice ?? 'default'
    const speed = body.speed ?? 1

    const b64 = await tts(text, voice, speed)
    if (!b64) return err('Voice model returned empty result', 502)
    const dataUrl = audioBase64ToDataUrl(b64)

    let take = null
    if (body.save !== false) {
      take = await db.voiceTake.create({
        data: {
          projectId: body.projectId ?? null,
          characterId: body.characterId ?? null,
          text,
          voice,
          audioBase64: dataUrl,
        },
      })
    }

    return json({ ok: true, data: { audioUrl: dataUrl, take } })
  } catch (e: any) {
    return err(e?.message ?? 'Voice synthesis failed')
  }
}

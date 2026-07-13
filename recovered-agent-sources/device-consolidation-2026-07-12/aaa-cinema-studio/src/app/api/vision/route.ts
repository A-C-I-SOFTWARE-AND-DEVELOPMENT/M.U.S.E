import { NextRequest } from 'next/server'
import { vision } from '@/lib/zai'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 120

// Vision Lab — VLM analysis of a reference image (data URL or http URL).
// body: { imageUrl, mode }
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const imageUrl = (body.imageUrl ?? '').trim()
    if (!imageUrl) return err('imageUrl required', 400)
    const mode = body.mode ?? 'describe'

    const prompts: Record<string, string> = {
      describe:
        'You are M.U.S.E Vision. Describe this reference image as a production design brief: composition, lighting, color palette (with hex guesses), mood, key visual motifs, and 3 cinematography takeaways for a film/game. Use markdown headers.',
      style:
        'Extract the VISUAL STYLE DNA of this image as a reusable prompt template: a single dense paragraph a generative image model could use to reproduce this look. Include lighting, lens, palette, texture, grain, era. End with: "PROMPT: <the template>".',
      character:
        'Reverse-engineer the character in this image: name suggestion, archetype, 3-line backstory, appearance notes, voice profile, and wardrobe. Markdown headers.',
      storyboard:
        'Analyze this as a STORYBOARD FRAME. Return: shot type, camera height, lens approximation, lighting setup, blocking, intended emotional beat, and a director note. Markdown.',
      moodboard:
        'Treat this as one tile of a moodboard. Output a 4-line mood statement, 5 evocative keywords, a complementary palette (5 hex), and a one-sentence direction for the next tile.',
    }

    const content = await vision(prompts[mode] ?? prompts.describe, imageUrl)
    return json({ ok: true, data: { content, mode } })
  } catch (e: any) {
    return err(e?.message ?? 'Vision analysis failed')
  }
}

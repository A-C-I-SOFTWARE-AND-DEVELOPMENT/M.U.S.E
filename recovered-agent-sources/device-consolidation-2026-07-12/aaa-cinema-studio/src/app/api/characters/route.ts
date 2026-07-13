import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'
import type { MuseCharacter } from '@/lib/types'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const projectId = req.nextUrl.searchParams.get('projectId')
  try {
    const where = projectId ? { projectId } : {}
    const characters = await db.character.findMany({ where, orderBy: { createdAt: 'desc' } })
    return json({ ok: true, data: characters as MuseCharacter[] })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load characters')
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const character = await db.character.create({
      data: {
        projectId: body.projectId,
        name: body.name ?? 'Unnamed',
        role: body.role ?? 'Supporting',
        archetype: body.archetype ?? '',
        backstory: body.backstory ?? '',
        appearance: body.appearance ?? '',
        voiceProfile: body.voiceProfile ?? '',
        voice: body.voice ?? 'default',
        portraitUrl: body.portraitUrl ?? '',
      },
    })
    return json({ ok: true, data: character as MuseCharacter }, 201)
  } catch (e: any) {
    return err(e?.message ?? 'Failed to save character')
  }
}

export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('id')
  if (!id) return err('id required', 400)
  try {
    await db.character.delete({ where: { id } })
    return json({ ok: true })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to delete character')
  }
}

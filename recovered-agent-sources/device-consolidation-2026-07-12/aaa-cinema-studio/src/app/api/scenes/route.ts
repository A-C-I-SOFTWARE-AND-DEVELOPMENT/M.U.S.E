import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'
import type { MuseScene } from '@/lib/types'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const projectId = req.nextUrl.searchParams.get('projectId')
  try {
    const where = projectId ? { projectId } : {}
    const scenes = await db.scene.findMany({ where, orderBy: { sequence: 'asc' } })
    return json({ ok: true, data: scenes as MuseScene[] })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load scenes')
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const scene = await db.scene.create({
      data: {
        projectId: body.projectId,
        title: body.title ?? 'Scene',
        slug: body.slug ?? '',
        sequence: body.sequence ?? 0,
        location: body.location ?? '',
        timeOfDay: body.timeOfDay ?? '',
        mood: body.mood ?? '',
        shotType: body.shotType ?? '',
        description: body.description ?? '',
        imageUrl: body.imageUrl ?? '',
        duration: body.duration ?? 0,
      },
    })
    return json({ ok: true, data: scene as MuseScene }, 201)
  } catch (e: any) {
    return err(e?.message ?? 'Failed to save scene')
  }
}

export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('id')
  if (!id) return err('id required', 400)
  try {
    await db.scene.delete({ where: { id } })
    return json({ ok: true })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to delete scene')
  }
}

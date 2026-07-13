import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'
import type { MuseProject } from '@/lib/types'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const projects = await db.project.findMany({
      orderBy: { updatedAt: 'desc' },
      include: { _count: { select: { characters: true, scenes: true, scripts: true, assets: true, voiceTakes: true } } },
    })
    return json({ ok: true, data: projects as MuseProject[] })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load projects')
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const title = (body.title ?? '').trim() || 'Untitled Production'
    const project = await db.project.create({
      data: {
        title,
        logline: body.logline ?? '',
        genre: body.genre ?? '',
        medium: body.medium ?? 'film',
        palette: body.palette ?? '',
      },
      include: { _count: { select: { characters: true, scenes: true, scripts: true, assets: true, voiceTakes: true } } },
    })
    return json({ ok: true, data: project as MuseProject }, 201)
  } catch (e: any) {
    return err(e?.message ?? 'Failed to create project')
  }
}

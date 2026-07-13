import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'

export async function GET(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params
  try {
    const project = await db.project.findUnique({
      where: { id },
      include: {
        characters: { orderBy: { createdAt: 'asc' } },
        scenes: { orderBy: { sequence: 'asc' } },
        scripts: { orderBy: { createdAt: 'desc' } },
        assets: { orderBy: { createdAt: 'desc' } },
        voiceTakes: { orderBy: { createdAt: 'desc' } },
      },
    })
    if (!project) return err('Project not found', 404)
    return json({ ok: true, data: project })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load project')
  }
}

export async function PATCH(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params
  try {
    const body = await req.json()
    const project = await db.project.update({
      where: { id },
      data: {
        title: body.title,
        logline: body.logline,
        genre: body.genre,
        medium: body.medium,
        palette: body.palette,
      },
    })
    return json({ ok: true, data: project })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to update project')
  }
}

export async function DELETE(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params
  try {
    await db.project.delete({ where: { id } })
    return json({ ok: true })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to delete project')
  }
}

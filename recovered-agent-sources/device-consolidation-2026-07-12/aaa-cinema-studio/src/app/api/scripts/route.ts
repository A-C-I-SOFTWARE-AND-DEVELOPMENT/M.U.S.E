import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'
import type { MuseScript } from '@/lib/types'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const projectId = req.nextUrl.searchParams.get('projectId')
  try {
    const where = projectId ? { projectId } : {}
    const scripts = await db.script.findMany({ where, orderBy: { createdAt: 'desc' } })
    return json({ ok: true, data: scripts as MuseScript[] })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load scripts')
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const script = await db.script.create({
      data: {
        projectId: body.projectId,
        title: body.title ?? 'Untitled',
        act: body.act ?? 'Act I',
        kind: body.kind ?? 'scene',
        content: body.content ?? '',
      },
    })
    return json({ ok: true, data: script as MuseScript }, 201)
  } catch (e: any) {
    return err(e?.message ?? 'Failed to save script')
  }
}

export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('id')
  if (!id) return err('id required', 400)
  try {
    await db.script.delete({ where: { id } })
    return json({ ok: true })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to delete script')
  }
}

import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'
import type { MuseAsset } from '@/lib/types'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const projectId = req.nextUrl.searchParams.get('projectId')
  const type = req.nextUrl.searchParams.get('type')
  try {
    const where: any = {}
    if (projectId) where.projectId = projectId
    if (type) where.type = type
    const assets = await db.asset.findMany({ where, orderBy: { createdAt: 'desc' }, take: 200 })
    return json({ ok: true, data: assets as MuseAsset[] })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load assets')
  }
}

export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('id')
  if (!id) return err('id required', 400)
  try {
    await db.asset.delete({ where: { id } })
    return json({ ok: true })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to delete asset')
  }
}

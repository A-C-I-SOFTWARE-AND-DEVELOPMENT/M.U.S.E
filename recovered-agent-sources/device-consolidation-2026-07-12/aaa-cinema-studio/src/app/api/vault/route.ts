import { NextRequest } from 'next/server'
import { db } from '@/lib/db'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'

// Vault stats — aggregate counts across the ledger.
export async function GET() {
  try {
    const [projects, characters, scenes, scripts, assets, voiceTakes] = await Promise.all([
      db.project.count(),
      db.character.count(),
      db.scene.count(),
      db.script.count(),
      db.asset.count(),
      db.voiceTake.count(),
    ])
    return json({
      ok: true,
      data: { projects, characters, scenes, scripts, assets, voiceTakes },
    })
  } catch (e: any) {
    return err(e?.message ?? 'Failed to load vault stats')
  }
}

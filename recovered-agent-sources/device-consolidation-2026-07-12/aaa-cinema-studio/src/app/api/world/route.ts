import { NextRequest } from 'next/server'
import { llm } from '@/lib/zai'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 120

// World Architect — worldbuilding LLM.
// body: { mode, ...payload }
const SYSTEM = `You are muse's World Architect — a once-in-a-generation worldbuilder operating at the
level of the most decorated setting designers in the medium (Tolkien, Le Guin, Miéville,
Herbert, Ursula K. Le Guin; the Housers, Yoko Taro, FromSoftware's lore team, Bethesda's
world leads). You design worlds that are lived-in, mythically resonant, internally
consistent, and dramatically generative — every detail seeds a story. You return ONLY the
requested artifact, richly specific, no preamble, no hedging.`

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const mode = body.mode ?? 'world'
    let prompt = ''

    switch (mode) {
      case 'world':
        prompt = `Build a world for a ${body.genre || 'mythic fantasy'} ${body.medium || 'hybrid'} production titled "${body.title || 'Untitled'}". Seed: ${body.seed || 'a fading empire built on borrowed time'}. Return markdown with these sections: ### PREMISE (2 sentences), ### COSMOLOGY (how the world works — its rules/physics/magic), ### GEOGRAPHY (3 signature locations, each a vivid paragraph), ### FACTIONS (3 factions — name, agenda, signature aesthetic, tension with another faction), ### AESTHETIC (color palette, materials, sound design in 3 lines), ### CONFLICT ENGINE (the structural tension that keeps generating story). Be concrete and evocative.`
        break
      case 'location':
        prompt = `Design a SIGNATURE LOCATION for a ${body.genre || 'neo-noir'} story: ${body.seed || 'a place that remembers'}. Return markdown: ### NAME, ### SENSORY (3 lines: sight / sound / smell), ### ARCHITECTURE, ### WHO LIVES HERE, ### WHAT IT HIDES, ### ONE SCENE SEED. Vivid, specific, ~220 words.`
        break
      case 'faction':
        prompt = `Design a FACTION for a ${body.genre || 'space opera'}: ${body.seed || "those who inherit the dead god's debt"}. Return markdown: ### NAME + SIGIL, ### CREED (one-line rallying cry), ### HIERARCHY, ### RESOURCES & WEAKNESS, ### RELATIONS (1 ally, 1 rival), ### AESTHETIC. ~200 words.`
        break
      case 'lore':
        prompt = `Write a piece of IN-WORLD LORE for a ${body.genre || 'cosmic horror'} setting — an excerpt from a sacred text, field report, or folk song about "${body.seed || 'the thing beneath the ice'}". Return it as a styled document fragment (header + body). Atmospheric, ~180 words.`
        break
      case 'palette':
        prompt = `Define the visual palette for "${body.title || 'Untitled'}" (${body.genre || 'open'}). Return markdown: ### KEY COLORS (5 hex codes with evocative names), ### MATERIALS, ### LIGHTING (2 sentences), ### TEXTURE & GRAIN, ### COMPOSITION RULES (3 bullets). Cinematographer-ready.`
        break
      default:
        return err('Unknown world mode: ' + mode, 400)
    }

    const content = await llm(prompt, { system: SYSTEM, temperature: 0.9, maxTokens: 1600 })
    return json({ ok: true, data: { content, mode } })
  } catch (e: any) {
    return err(e?.message ?? 'World generation failed')
  }
}

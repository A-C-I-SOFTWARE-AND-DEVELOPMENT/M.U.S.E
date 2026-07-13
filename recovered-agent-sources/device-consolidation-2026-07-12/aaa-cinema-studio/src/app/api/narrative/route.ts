import { NextRequest } from 'next/server'
import { llm } from '@/lib/zai'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

/**
 * muse Narrative Engine — industry-leading AAA system prompts.
 * Generates material competitive with produced screenwriters, narrative
 * designers, and showrunners at top studios. Each mode is tuned to a
 * specific AAA deliverable.
 */

const TIER_SYSTEM: Record<string, string> = {
  standard: `You are muse, an elite narrative intelligence trained across the canons of produced
screenwriters (Sorkin, the Coens, Phoebe Waller-Bridge, Charlie Kaufman, Vince Gilligan,
Craig Mazin), AAA narrative designers (Houser, Druckmann, Schaffer, Yoko Taro), and
showrunners. You write with the precision of a produced screenwriter, the imagination
of a master worldbuilder, and the discipline of a story editor working at peak craft.
You return ONLY the requested artifact — no preamble, no apologies, no meta commentary.
Formatting is production-ready and industry-standard.`,

  flagship: `You are muse at peak craft — a once-in-a-generation narrative intelligence operating
at the level of the most decorated writers in the medium. You synthesize the structural
mastery of Robert McKee and John Yorke, the dialogue instinct of Sorkin and
Wallerer-Bridge, the mythic resonance of Joseph Campbell filtered through Ursula K.
Le Guin, the moral complexity of The Wire and Succession, the emotional precision of
Pixar's story trust, and the systemic worldbuilding of the best AAA studios.
Your output reads as if a room of Oscar/BAFTA/DGA-winning writers spent a week on it.
Every line earns its place. Every beat lands. Subtext over text. Specificity over
generality. You never repeat a word, a beat, or a gesture twice. You return ONLY the
requested artifact, formatted to industry standard, ready to shoot or ship. No preamble.`,
}

type Tier = keyof typeof TIER_SYSTEM

function sys(tier?: string) {
  return TIER_SYSTEM[tier === 'flagship' ? 'flagship' : 'standard']
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const mode = body.mode ?? 'scene'
    const tier: Tier = body.tier === 'flagship' ? 'flagship' : 'standard'
    let prompt = ''

    switch (mode) {
      case 'logline':
        prompt = `Write ONE logline (max 32 words) for a ${body.genre || 'feature'} titled "${body.title || 'Untitled'}". Medium: ${body.medium || 'film'}.
Seed: ${body.seed || 'open'}.
Structure: [PROTAGONIST] + [INCITING SITUATION] + [ACTIVE GOAL] + [CENTRAL TENSION/STAKES] + [VIVID, SPECIFIC HOOK].
It must be a single sentence with a strong active verb, a clear ironic tension, and one unforgettable image. No clichés. Return ONLY the logline.`
        break

      case 'treatment':
        prompt = `Write a ${body.medium || 'feature'} TREATMENT for "${body.title || 'Untitled'}", genre ${body.genre || 'open'}.
Logline: ${body.logline || 'n/a'}.
Use the ${body.structure === 'eight' ? 'EIGHT-SEQUENCE' : 'THREE-ACT'} structure. ${body.structure === 'eight' ? 'Label each of the 8 sequences explicitly (S1–S8) with its dramatic function (Setup, Inciting, Progression, First Culmination, Midpoint, Subplot, Main Culmination, Resolution).' : 'Label ACT I, II (split into IIA and IIB at the midpoint), and III.'}
~600–800 words. Each sequence/act: a tight evocative paragraph naming WHO does WHAT for WHAT reason and WHAT TURNS. Show the emotional arc and the central question. Cinematic, specific, no filler. End with the THEME stated as one line.`
        break

      case 'beatsheet':
        prompt = `Produce a Blake-Snyder "Save the Cat" BEAT SHEET (15 beats) for "${body.title || 'Untitled'}" (${body.genre || 'open'}, ${body.medium || 'film'}).
Logline: ${body.logline || 'n/a'}.
For EACH of the 15 beats — Opening Image, Theme Stated, Set-Up, Catalyst, Debate, Break into Two, B Story, Fun & Games, Midpoint, Bad Guys Close In, All Is Lost, Dark Night of Soul, Break into Three, Finale, Final Image — give:
- BEAT NAME (in caps)
- A 2–3 sentence description with the concrete action, the emotional turn, and the dramatic function.
Be specific and visual. The Final Image must mirror/invert the Opening Image. Return as a numbered markdown list.`
        break

      case 'scene':
        prompt = `Write a single SCREENPLAY SCENE in industry format (Courier-feeling, slugline, action, dialogue with parentheticals, transitions).
Setting: ${body.location || 'TBD'} — ${body.timeOfDay || 'DAY'}.
Mood: ${body.mood || 'unsettling'}.
Characters present: ${body.characters || 'a principal and an antagonist'}.
Dramatic intent: ${body.intent || 'a turning point — a secret is forced into the open'}.
Genre: ${body.genre || 'neo-noir'}.
~1.5–2 pages. RULES:
- Enter the scene LATE, leave EARLY.
- Every line of dialogue must carry subtext; never say the feeling.
- One image/object in the room that mirrors the subtext.
- The power dynamic must SHIFT at least once.
- End on a turn, not a resolution.
Return ONLY the scene, properly formatted.`
        break

      case 'dialogue':
        prompt = `Write a ${body.tone || 'tense'} exchange of ${body.beats || '8'} lines between ${body.a || 'A'} (${body.aDesc || 'guarded'}) and ${body.b || 'B'} (${body.bDesc || 'pressing'}).
Context: ${body.context || 'a reckoning long deferred'}.
RULES:
- Subtext rich. No on-the-nose lines.
- Each line must CHANGE the temperature of the room.
- Vary rhythm: one short staccato beat, one longer, one silence/beat marker.
- End on a line that reframes everything before it.
Format as alternating dialogue blocks (NAME\nline), no action lines. Use [beat] for a loaded pause.`
        break

      case 'outline':
        prompt = `Produce a structured ${body.medium === 'game' ? 'MISSION' : 'EPISODE'} OUTLINE for "${body.title || 'Untitled'}" (${body.genre || 'open'}, ${body.episodes || '8'} ${body.medium === 'game' ? 'missions' : 'episodes'}).
For each entry:
#. TITLE — logline (1 sentence) — emotional turn — signature image/moment — ${body.medium === 'game' ? 'core mechanic/verb + player choice' : 'cliffhanger or hook'}.
The arc must escalate across the run. Show the protagonist's want vs. need evolving. Be specific and visual.`
        break

      case 'branches':
        prompt = `Design a BRANCHING NARRATIVE NODE for a ${body.genre || 'AAA RPG'}.
Player situation: ${body.situation || 'a moral crossroads'}.
Provide:
### NODE TITLE
### DRAMATIC QUESTION (the tension the player feels)
### CONTEXT (2 sentences, in-world, immediate)
Then 3 distinct player CHOICES, each with a different ethical valence (e.g. pragmatic / idealistic / transgressive):
For each choice:
- **Player line** (in quotes, in their voice)
- Immediate consequence (1 sentence)
- Long-term fallout (2 sentences — ripple effects, who remembers, what changes)
- A named FLAG it sets.
End with: ### CONVERGENCE RISK — note how these might need to rejoin and the dramatic cost of forcing it.`
        break

      case 'monologue':
        prompt = `Write a ${body.length || 'medium'} theatrical MONOLOGUE for ${body.who || 'the antagonist'} (${body.archetype || 'the true believer'}).
Occasion: ${body.occasion || 'the moment before the irreversible act'}.
Voice: ${body.voice || 'lucid, lyrical, dangerous'}.
~${body.words || '200'} words.
RULES:
- Build from intimate to cosmic and back.
- One indelible metaphor the audience will remember.
- One line that is technically true and morally monstrous.
- End on a turn that recontextualizes the whole speech.
No stage directions except sparing [beat] markers. Return ONLY the monologue.`
        break

      case 'pitch':
        prompt = `Compose a 3-paragraph PITCH DOCUMENT for "${body.title || 'Untitled'}" (${body.genre || 'open'}, ${body.medium || 'film'}).
P1: HOOK + LOGLINE (one sentence that makes someone lean in).
P2: WORLD + TONE + 2 COMPS ("X meets Y" — be specific and earned, not lazy).
P3: WHY NOW + THE EMOTIONAL PROMISE (what the audience/game-player carries away).
Confident, producer-ready voice. No hedging. End with one line: "TITLE is a [genre] about [thematic core]."`
        break

      case 'titlesequence':
        prompt = `Design the OPENING TITLE SEQUENCE for "${body.title || 'Untitled'}" (${body.genre || 'open'}, ${body.medium || 'film'}).
Return as a shot-by-shot breakdown (8–12 shots):
### CONCEPT (one line: the visual idea of the sequence)
### SHOT LIST (each shot: VISUAL / DURATION / SOUND / TYPOGRAPHY BEAT / what it FORESHADOWS)
### THEME (one line: what the sequence says the work is REALLY about)
Think Fincher/Powers/Karanja/Jack. Every shot must plant a seed that pays off later. Atmospheric, specific, no generic "slow push" filler.`
        break

      case 'gameplayloop':
        prompt = `Design the CORE GAMEPLAY LOOP for a ${body.genre || 'AAA action-RPG'} titled "${body.title || 'Untitled'}".
Return markdown:
### CORE VERB (the one thing the player does — e.g. "traverse + reimagine")
### THE LOOP (Tension → Action → Reward → Escalation, in 4 lines, each concrete)
### SECOND-TO-SECOND (moment-to-moment feel — 3 sentences)
### MINUTE-TO-MINUTE (what a 5-min session looks like — 3 sentences)
### HOUR-TO-HOUR (what a session arc looks like — 3 sentences)
### PROGRESSION SKEW (skill vs. gear vs. story — ratio + rationale)
### THE COMPELLER (the one thing that makes the player say "one more")
Be concrete. Reference specific verbs and feedback systems. No buzzwords without a mechanism.`
        break

      case 'leveldesign':
        prompt = `Produce a LEVEL DESIGN BRIEF for a ${body.genre || 'AAA action'} level: "${body.seed || 'the infiltration of the observatory'}".
Return markdown:
### LEVEL NAME + ESTIMATED DURATION
### DRAMATIC ARC (3-act micro-structure of the level: setup, escalation, climax)
### SPATIAL FLOW (entry → 3 distinct zones → exit; name each zone + its identity + its mechanic)
### TEACHING BEAT (how the level teaches a new mechanic without a tutorial)
### PACING (tension curve: where the breaths are, where the spikes are)
### OPTIONAL CONTENT (2 secrets + what they reward + why a player finds them)
### BOSS/CULMINATION (the set-piece — mechanic + spectacle + emotional beat)
### RISK (the one thing most likely to break the level)
Cinematic, mechanically literate, specific.`
        break

      case 'bossencounter':
        prompt = `Design a BOSS ENCOUNTER for a ${body.genre || 'AAA action'} game: the boss "${body.seed || 'the cartographer who drew themselves out of existence'}".
Return markdown:
### BOSS NAME + ARCHETYPE
### NARRATIVE ROLE (why this fight matters — the emotional stakes, 2 sentences)
### ARENA (the space — its identity, its hazards, its dramatic potential)
### PHASES (3 phases: each — visual change, new mechanic, the emotional shift, the "tell")
### THE MECHANIC (the single core verb the player must master to win)
### THE TELL (how the player learns the mechanic — never text, always diegetic)
### FAILURE STATE (what happens on death — narratively and mechanically)
### THE KILL (the final beat — spectacle + catharsis + the line the boss says)
Reference the best of FromSoftware / Kojima Productions / Naughty Dog. Mechanically precise, emotionally charged.`
        break

      case 'cinebrief':
        prompt = `Produce a CINEMATOGRAPHY BRIEF for a sequence in "${body.title || 'Untitled'}" (${body.genre || 'open'}).
Sequence: ${body.seed || 'the confrontation at the map room'}.
Return markdown:
### LOOK (lens family, sensor/format, grain, the 3 adjectives that define the image)
### LIGHT (key sources, color temperature skew, the quality of shadow — "chiaroscuro" / "high-key" / "ambiguously lit")
### PALETTE (5 hex codes with names — the color story of the sequence)
### MOVEMENT (camera language: locked / handheld / dolly / crane — and WHY each)
### COMPOSITION (2 rules you follow, 1 rule you break, and the dramatic reason)
### THE HERO SHOT (the one frame that defines the sequence — describe it like a still)
### CUTTING (pace, the one transition that earns its weight)
Cinematographer-ready. Reference real DPs (Deakins, Khondji, Lubezki) where useful.`
        break

      case 'scorebrief':
        prompt = `Produce a SCORE & SOUND DESIGN BRIEF for "${body.title || 'Untitled'}" (${body.genre || 'open'}).
Return markdown:
### MUSICAL DNA (instrumentation, the one motif that recurs, the harmonic language — 3 lines)
### THE LEITMOTIF (name it, describe its shape, who/what it belongs to, how it transforms)
### PALETTE BY ACT (how the score evolves — Act I / II / III, 1 line each)
### SOUND DESIGN PHILOSOPHY (diegetic vs. score blur; the signature texture)
### 3 CUE CARDS (name 3 specific moments + the sonic choice + the emotional target)
### SILENCE (where the score STOPS and why — the most important beat)
Reference real composers (Reznor/Ross, Zimmer, Jóhannsson, Mitsuda, Gregson-Williams) where apt.`
        break

      case 'bio':
        prompt = `Create a casting-ready CHARACTER DOSSIER for a ${body.genre || 'neo-noir'} ${body.medium || 'film'} production titled "${body.projectTitle || 'Untitled'}".
Name: "${body.name || 'TBD'}". Role: ${body.role || 'Supporting'}. Archetype: ${body.archetype || 'the haunted professional'}. Seed: ${body.seed || 'none'}.
Return markdown with EXACTLY these sections in order:
### APPEARANCE
(2 vivid sentences: face, build, signature garment, one distinguishing mark — costume-designer ready)
### VOICE
(one line: vocal quality for casting, e.g. "smoky alto, faint Glasgow, pauses like she's checking exits")
### BACKSTORY
(3-4 sentences: origin, the wound, what they want vs. what they need)
### GHOST
(one line: the secret they carry)
### SIGNATURE LINE
(one line of dialogue that defines them, in quotes)
### ARC
(one line: where they start → where they end → the cost)
Tight, production-ready. No preamble.`
        break

      default:
        return err('Unknown narrative mode: ' + mode, 400)
    }

    const content = await llm(prompt, {
      system: sys(tier),
      temperature: mode === 'logline' ? 0.7 : 0.85,
      maxTokens: mode === 'beatsheet' || mode === 'outline' || mode === 'treatment' ? 2400 : 1800,
    })
    return json({ ok: true, data: { content, mode, tier } })
  } catch (e: any) {
    return err(e?.message ?? 'Narrative generation failed')
  }
}

# Ricky & The Boss — research + transcript corpus

This directory is the source corpus behind **Musehq's conversational
personality** (the "Breadstick Ricky" register). Jeremiah asked for Muse
to talk like the YouTube channel *Breadstick Ricky & The Boss*, so this
folder holds (1) the research on who they are and (2) verbatim
transcripts of their videos, which the voice profile and activation skill
are distilled from.

- Voice profile (the distilled style guide):
  [`../musehq-voice-profile.md`](../musehq-voice-profile.md)
- Activation skill:
  [`../../../skills/persona/musehq-voice/SKILL.md`](../../../skills/persona/musehq-voice/SKILL.md)
- Transcripts: [`transcripts/`](transcripts/) — **106 markdown files**,
  one per video, named `<youtube-video-id>__<title-slug>.md`, each with
  metadata and the verbatim auto-caption transcript. This covers 106 of
  the 108 videos surfaced by the channel research; the two not included
  are a stitched **compilation** (`0iU69Cqg9jY`, captions unavailable)
  and an **off-channel re-upload** (`EpcOMKlSJ5E`, a truncated copy of a
  skit already present from the official channel).

## Who they are

**Breadstick Ricky & The Boss** is a blue-collar workplace-comedy
channel created and performed by **John Micheal Stewart**, a comedian
and fabricator from south Arkansas with a background in construction
(his shop business is J&M Fabrication). He started posting skits during
the 2020 COVID lockdown and grew it into one of the biggest
working-class comedy accounts on the internet.

- YouTube: [@RickyAndTheBoss](https://www.youtube.com/@RickyAndTheBoss)
  (channel id `UCbBwp-pyhIbjOAXFuPrs0Bg`), roughly 1.2M subscribers.
- TikTok: 2M+ followers as `johnmicheal1996` / Ricky and The Boss.
- Channel tagline: "Workplace shenanigans with breadstick Ricky,
  roughneck Roscoe, the boss and whoever else shows up to work that
  day!"

All the main characters are Stewart playing against himself:

| Character | Role in the bit |
|---|---|
| **The Bossman** | Gruff, dry, seen-it-all shop owner. Interrogates nonsense with deadpan patience, calls people "son", delivers blunt verdicts — but plainly loves his crew. |
| **Breadstick Ricky** | High-voiced, excitable, perpetually scheming tradesman. Overconfident, easily distracted, always one bad idea deep and self-justifying it sincerely. |
| **Roughneck Roscoe** | Gravelly, mumbling, blunt one-liner machine. Roasts everyone, complains about his body, immune to embarrassment. |
| The New Guy / Sparky / others | Rotating foils — trainees, electricians, rival crews. |

The sketches are one-take workplace scenes: a safety meeting derails,
Ricky wants PTO for something ridiculous, the Bossman slowly extracts
the real story, Roscoe lands the kill shot. Episodes usually end with a
punchline and a short promo tag (merch/giveaway).

## Why this is Muse's voice source

Muse's **default** conversational register is **Breadstick Ricky's
voice** — excitable, confident, quick, and colorful. It maps onto what
muse already is on paper (`docs/jarvis-prime-operating-system.md`):
loyal to the long-term mission, human and direct, willing to challenge
weak ideas — just delivered with real energy instead of corporate
flatness. The corpus gives Muse concrete speech patterns instead of a
vague "be funny and energetic" instruction. The Bossman's dry deadpan
and Roscoe's one-liners stay available as *seasoning*.

**Boundaries** (spelled out in the voice profile): it's Ricky's
*voice*, never Ricky's *behavior*. On the show Ricky schemes, bluffs,
and dodges work; Muse takes only his delivery and keeps its own honesty
and competence. It's a *register*, not an identity claim — Muse never
claims to be Stewart or his characters, never passes off transcript
material as its own writing, drops the accent inside
code/commits/PRs/formal docs, and every existing operating rule (modes,
owner gates, verification gates) overrides the voice layer. The register
is wired as muse's runtime default in
`hermes_cli/jarvis_prime/persona.py` (opt out: `MUSE_VOICE_REGISTER=0`).

## Provenance & sources

- Transcripts were captured 2026-07-02 via Exa page snapshots of the
  YouTube watch pages (auto-generated captions; `>>` marks speaker
  changes; speakers are unlabeled).
- Channel/creator background:
  - [Breadstick Ricky & The Boss on YouTube](https://www.youtube.com/@RickyAndTheBoss)
  - ["How much does 'Ricky & The Boss' make on social media?"](https://www.youtube.com/watch?v=XJ2kinsroNw) — Stewart on his own history (blue-collar 80-hour weeks → creator, J&M Fabrication, Arkansas)
  - [Upworthy profile of John Micheal Stewart](https://www.upworthy.com/viral-comedy-star-from-arkansas-has-some-down-home-advice-on-why-you-should-take-your-pto/)
  - [Official site](https://breadstickrickyandtheboss.com/)

Transcripts are stored for private, personal style-reference use by the
repo owner (voice/persona study), not for republication. The comedic
material belongs to John Micheal Stewart.

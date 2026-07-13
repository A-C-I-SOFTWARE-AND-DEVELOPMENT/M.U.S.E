// Shared M.U.S.E domain types

export type Medium = 'film' | 'game' | 'hybrid'

export interface MuseProject {
  id: string
  title: string
  logline: string
  genre: string
  medium: Medium
  palette: string
  createdAt: string
  updatedAt: string
  _count?: { characters: number; scenes: number; scripts: number; assets: number; voiceTakes: number }
}

export interface MuseCharacter {
  id: string
  projectId: string
  name: string
  role: string
  archetype: string
  backstory: string
  appearance: string
  voiceProfile: string
  voice: string
  portraitUrl: string
  createdAt: string
}

export interface MuseScene {
  id: string
  projectId: string
  title: string
  slug: string
  sequence: number
  location: string
  timeOfDay: string
  mood: string
  shotType: string
  description: string
  imageUrl: string
  duration: number
  createdAt: string
}

export interface MuseScript {
  id: string
  projectId: string
  title: string
  act: string
  kind: string
  content: string
  createdAt: string
}

export interface MuseAsset {
  id: string
  projectId: string | null
  type: string
  title: string
  prompt: string
  imageUrl: string
  meta: string
  createdAt: string
}

export interface MuseVoiceTake {
  id: string
  projectId: string | null
  characterId: string | null
  text: string
  voice: string
  audioBase64: string
  createdAt: string
}

export interface ApiResponse<T = unknown> {
  ok: boolean
  data?: T
  error?: string
}

// TTS voice catalog — descriptive names for the harness.
export const VOICES: { id: string; label: string; desc: string }[] = [
  { id: 'default', label: 'Muse (Neutral Narrator)', desc: 'Balanced cinematic narrator' },
  { id: 'male-1', label: 'Atlas (Gravelly Baritone)', desc: 'Aged warrior / mentor' },
  { id: 'male-2', label: 'Orion (Calm Tenor)', desc: 'Young protagonist' },
  { id: 'female-1', label: 'Vesper (Smoky Alto)', desc: 'Noir detective / antagonist' },
  { id: 'female-2', label: 'Lyra (Bright Soprano)', desc: 'Idealist / ingénue' },
  { id: 'child-1', label: 'Pip (Youthful)', desc: 'Child / creature companion' },
]

export const GENRES = [
  'Neo-Noir',
  'Space Opera',
  'Mythic Fantasy',
  'Cyberpunk',
  'Post-Apocalyptic',
  'Cosmic Horror',
  'Western',
  'Period Drama',
  'Psychological Thriller',
  'Mythic Realism',
]

export const SHOT_TYPES = [
  'Wide Establishing',
  'Extreme Wide',
  'Medium Shot',
  'Close-Up',
  'Extreme Close-Up',
  'Over-the-Shoulder',
  'Dutch Tilt',
  'Low Angle',
  'High Angle',
  'Birds-Eye',
  'Dolly Push',
  'Tracking',
  'Crane / Boom',
  'POV',
  'Two-Shot',
]

export const ASPECT_BY_SHOT: Record<string, '1344x768' | '768x1344' | '1024x1024' | '1440x720' | '720x1440'> = {
  'Wide Establishing': '1440x720',
  'Extreme Wide': '1440x720',
  'Medium Shot': '1024x1024',
  'Close-Up': '768x1344',
  'Extreme Close-Up': '768x1344',
  'Over-the-Shoulder': '1024x1024',
  'Dutch Tilt': '1024x1024',
  'Low Angle': '768x1344',
  'High Angle': '1344x768',
  "Birds-Eye": '1440x720',
  'Dolly Push': '1344x768',
  'Tracking': '1344x768',
  'Crane / Boom': '1440x720',
  'POV': '1024x1024',
  'Two-Shot': '1344x768',
}

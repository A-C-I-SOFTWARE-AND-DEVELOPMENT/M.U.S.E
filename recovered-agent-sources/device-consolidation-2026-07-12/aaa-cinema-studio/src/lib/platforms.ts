/**
 * muse Platform Fidelity System
 *
 * Canonical visual signatures for every major console generation — from the
 * Game Boy DMG to the PS5. Each profile bakes era-accurate rendering
 * characteristics (polygon budget, texture filtering, color depth, resolution,
 * lighting model, dithering, CRT characteristics) into the image prompt so
 * generations authentically evoke that platform's look.
 */

export type Era = 'pixel' | '32bit' | '128bit' | 'hd' | 'modern' | 'current' | 'engine'

export interface Platform {
  id: string
  label: string
  code: string
  maker: 'Nintendo' | 'Sony' | 'Microsoft' | 'Sega' | 'PC' | 'Epic'
  era: Era
  year: number
  accent: string // brand-ish color for UI
  prompt: string // the visual signature fragment appended to image prompts
}

export const PLATFORMS: Platform[] = [
  // ---- Pixel Era -----------------------------------------------------------
  {
    id: 'gb-dmg',
    label: 'Game Boy',
    code: 'GB',
    maker: 'Nintendo',
    era: 'pixel',
    year: 1989,
    accent: '#9bbc0f',
    prompt:
      'original Nintendo Game Boy DMG (1989) aesthetic, strict 4-shade pea-green monochrome palette (#0f380f #306230 #8bac0f #9bbc0f), 160x144 resolution, heavy ordered Bayer dithering, tile-based sprites, crunchy visible pixels, no anti-aliasing, retro handheld LCD screen with ghosting, pixel art',
  },
  {
    id: 'gbc',
    label: 'Game Boy Color',
    code: 'GBC',
    maker: 'Nintendo',
    era: 'pixel',
    year: 1998,
    accent: '#7a3df0',
    prompt:
      'Nintendo Game Boy Color aesthetic, limited 56-color palette, 160x144 resolution, dithered pixel art, crunchy tiles, sprite-based, retro handheld, no anti-aliasing, visible pixels',
  },
  {
    id: 'nes',
    label: 'NES',
    code: 'NES',
    maker: 'Nintendo',
    era: 'pixel',
    year: 1985,
    accent: '#e60012',
    prompt:
      'Nintendo Entertainment System NES 8-bit aesthetic, 8-bit pixel art, strict 54-color palette, 256x240, sprite tiles, limited per-sprite palettes, hard edges, no gradients, 1985 cartridge graphics, CRT scanlines',
  },
  {
    id: 'snes',
    label: 'SNES',
    code: 'SNES',
    maker: 'Nintendo',
    era: 'pixel',
    year: 1990,
    accent: '#7b0a2f',
    prompt:
      'Super Nintendo SNES 16-bit aesthetic, 16-bit pixel art, 32768-color palette, Mode 7 perspective effects, rich sprite work, 256x224, 1990s JRPG look, detailed pixel shading, CRT scanlines, no 3D',
  },

  // ---- 32-bit Era ----------------------------------------------------------
  {
    id: 'ps1',
    label: 'PlayStation',
    code: 'PS1',
    maker: 'Sony',
    era: '32bit',
    year: 1994,
    accent: '#0070d1',
    prompt:
      'Sony PlayStation 1 PS1 PSX aesthetic, 32-bit 3D, affine texture warping, jittery unstable vertices, very low-polygon models, 320x240, no z-buffer causing texture wobble and polygon pop, vertex/Gouraud lighting, pre-rendered backgrounds, 1995 era, CRT scanlines, heavy dithering, crunchy',
  },
  {
    id: 'n64',
    label: 'Nintendo 64',
    code: 'N64',
    maker: 'Nintendo',
    era: '32bit',
    year: 1996,
    accent: '#5a1ea5',
    prompt:
      'Nintendo 64 N64 aesthetic, 64-bit 3D, bilinear texture filtering (blurry smeared textures), low-polygon, anti-aliased edges, distance fog hiding draw distance, vertex lighting, 320x240, 1996 era, cartridge graphics, trilinear mipmaps',
  },

  // ---- 128-bit Era (6th gen) -----------------------------------------------
  {
    id: 'ps2',
    label: 'PlayStation 2',
    code: 'PS2',
    maker: 'Sony',
    era: '128bit',
    year: 2000,
    accent: '#1f4fa3',
    prompt:
      'Sony PlayStation 2 PS2 aesthetic, 128-bit era, 512x448 interlaced field rendering, slight texture shimmer and aliasing, vertex lighting, limited texture memory, low-poly but clean, that distinct PS2 look, 2000 era, CRT, subtle depth of field, film grain',
  },
  {
    id: 'gc',
    label: 'GameCube',
    code: 'GC',
    maker: 'Nintendo',
    era: '128bit',
    year: 2001,
    accent: '#6a5acd',
    prompt:
      'Nintendo GameCube aesthetic, 6th generation, 480p, clean low-poly models, glossy specular shaders, baked lighting, environment mapping reflections, polished Nintendo look, 2001 era, soft shadows, vibrant saturated color',
  },
  {
    id: 'xbox',
    label: 'Xbox',
    code: 'XB',
    maker: 'Microsoft',
    era: '128bit',
    year: 2001,
    accent: '#107c10',
    prompt:
      'original Microsoft Xbox (2001) aesthetic, 720p capable, bump mapping, sharp specular highlights, higher polygon count than PS2, dynamic per-pixel lighting, early normal maps, glossy reflective surfaces, hard-edged 6th-gen 3D',
  },

  // ---- HD Era (7th gen) ----------------------------------------------------
  {
    id: 'ps3',
    label: 'PlayStation 3',
    code: 'PS3',
    maker: 'Sony',
    era: 'hd',
    year: 2006,
    accent: '#003087',
    prompt:
      'Sony PlayStation 3 PS3 aesthetic, 7th generation, 720p/1080p HD, deferred rendering, strong HDR bloom, high dynamic range lighting, glossy SSAO, heavy motion blur, that bloomy slightly-washed PS3 look, 2006 era, contrast sometimes crushed, cinematic color grading',
  },
  {
    id: 'x360',
    label: 'Xbox 360',
    code: 'X360',
    maker: 'Microsoft',
    era: 'hd',
    year: 2005,
    accent: '#0e7a3d',
    prompt:
      'Microsoft Xbox 360 aesthetic, 7th generation, 720p/1080p HD, early PBR, bloom, SSAO, motion blur, 2005 era HD look, glossy specular, cinematic depth of field, color graded',
  },
  {
    id: 'wii',
    label: 'Wii',
    code: 'WII',
    maker: 'Nintendo',
    era: 'hd',
    year: 2006,
    accent: '#3aa6a0',
    prompt:
      'Nintendo Wii aesthetic, 7th generation but 480p SD, slightly above GameCube fidelity, soft shadows, heavy mip-mapping, motion blur, 2006 era, family-friendly polished look, slightly soft image, vibrant',
  },

  // ---- Modern Era (8th gen) ------------------------------------------------
  {
    id: 'ps4',
    label: 'PlayStation 4',
    code: 'PS4',
    maker: 'Sony',
    era: 'modern',
    year: 2013,
    accent: '#00439c',
    prompt:
      'Sony PlayStation 4 PS4 aesthetic, 8th generation, 1080p to 4K, physically based rendering PBR, high quality SSAO, screen-space reflections, subtle film grain, color graded, 2013 era modern AAA, crisp textures, realistic materials',
  },
  {
    id: 'xbone',
    label: 'Xbox One',
    code: 'X1',
    maker: 'Microsoft',
    era: 'modern',
    year: 2013,
    accent: '#1a8a3f',
    prompt:
      'Microsoft Xbox One aesthetic, 8th generation, 1080p, physically based rendering PBR, SSAO, screen-space reflections, 2013 era modern AAA, crisp, realistic materials, color graded',
  },
  {
    id: 'switch',
    label: 'Switch',
    code: 'NSW',
    maker: 'Nintendo',
    era: 'modern',
    year: 2017,
    accent: '#e60012',
    prompt:
      'Nintendo Switch aesthetic, 8th generation hybrid console, fidelity between PS3 and PS4, often stylized art direction, clean PBR, 720p handheld to 1080p docked, 2017 era, vibrant, polished Nintendo modern look',
  },

  // ---- Current Gen (9th) ---------------------------------------------------
  {
    id: 'ps5',
    label: 'PlayStation 5',
    code: 'PS5',
    maker: 'Sony',
    era: 'current',
    year: 2020,
    accent: '#1357be',
    prompt:
      'Sony PlayStation 5 PS5 aesthetic, 9th generation, 4K 60-120fps, ray-traced reflections, ray-traced global illumination, ultra physically based rendering, volumetric lighting and fog, 2020 era cutting-edge AAA, photorealistic, cinematic depth of field',
  },
  {
    id: 'xsx',
    label: 'Xbox Series X',
    code: 'XSX',
    maker: 'Microsoft',
    era: 'current',
    year: 2020,
    accent: '#0b8a2b',
    prompt:
      'Microsoft Xbox Series X aesthetic, 9th generation, 4K 120fps, hardware ray tracing, ultra PBR, volumetric lighting, 2020 era cutting-edge AAA, photorealistic, crisp reflections, cinematic',
  },
  {
    id: 'pc-ultra',
    label: 'PC Ultra',
    code: 'PC',
    maker: 'PC',
    era: 'current',
    year: 2024,
    accent: '#b388ff',
    prompt:
      'PC max settings ultra preset, 4K, full ray tracing and path tracing, highest fidelity, photorealistic, 8K textures, DLSS-quality sharpness, every modern rendering feature maxed, cutting-edge 2024 AAA',
  },

  // ---- Unreal Engine 5 (prompt-driven fidelity) ----------------------------
  // UE5 itself cannot run in this sandbox (no GPU/desktop, ~100GB, not prompt-driven).
  // These profiles bake UE5's rendering signatures into the image prompt so
  // generations evoke Unreal Engine 5's signature look — the realistic path to
  // "mind-blowing quality through prompts."
  {
    id: 'ue5-lumen',
    label: 'Unreal Engine 5 · Lumen',
    code: 'UE5',
    maker: 'Epic',
    era: 'engine',
    year: 2024,
    accent: '#1a8cff',
    prompt:
      'Unreal Engine 5.4 render with Lumen dynamic global illumination, light bouncing off every surface and bleeding colored indirect light into shadows, soft realistic shadow falloff with penumbra, Nanite virtualized geometry with microscopic surface detail, Quixel Megascans 8K photoreal PBR materials with visible roughness variation, weathering, cracks, grime and wetness, ray-traced ambient occlusion, volumetric fog rolling through the scene with god rays, atmospheric haze softening distant elements, cinematic shallow depth of field, film-grade color grading, 4K, photorealistic, the look of a UE5 Lumen tech demo, NOT flat lighting, NOT plastic',
  },
  {
    id: 'ue5-path',
    label: 'Unreal Engine 5 · Path Traced',
    code: 'PT',
    maker: 'Epic',
    era: 'engine',
    year: 2024,
    accent: '#7ae0ff',
    prompt:
      'Unreal Engine 5 path-traced render, offline-quality unbiased path tracing with infinite light bounces, physically perfect global illumination and reflections, colored light bleeding between surfaces and warm subsurface color-bleed into shadowed faces, cool sky-fill bounce on upward surfaces, soft area-light shadows with realistic penumbra, caustics, subsurface scattering on skin and wax, Quixel Megascans photoreal PBR materials at 8K with true roughness and metalness, visible micro-scratches and pitting on all metal, edge-chipped paint, rust and salt streaks on steel, dust accumulation in crevices, fabric thread micro-noise, physically-scattered volumetric fog with anisotropic in-scattering and visible light shafts, aerial perspective falloff, photorealistic, indistinguishable from a real photograph, cinematic film frame, the quality of a UE5 path-traced cinematic, NOT flat, NOT plastic',
  },
  {
    id: 'ue5-cine',
    label: 'Unreal Engine 5 · Cinematic',
    code: 'CINE',
    maker: 'Epic',
    era: 'engine',
    year: 2024,
    accent: '#b388ff',
    prompt:
      'Unreal Engine 5 cinematic trailer frame, Lumen GI with bounced indirect light, Nanite virtualized geometry, MetaHuman-grade character detail, shot on a virtual production LED volume stage, anamorphic 2.39:1 lens with subtle barrel distortion and chromatic aberration, cinematic bloom and anamorphic lens flares, realistic film grain, Hollywood teal-and-orange color grading, dramatic volumetric god rays cutting through atmospheric haze, ultra-detailed 8K Quixel Megascans environments with weathered PBR materials, motion blur, shallow cinematic depth of field, the look of a billion-dollar AAA game reveal trailer, photorealistic, NOT flat lighting',
  },
  {
    id: 'ue5-megascans',
    label: 'UE5 · Megascans World',
    code: 'SCAN',
    maker: 'Epic',
    era: 'engine',
    year: 2024,
    accent: '#5be3a0',
    prompt:
      'Unreal Engine 5 environment built entirely from Quixel Megascans, photoreal scanned real-world assets at 8K resolution, Lumen global illumination bouncing light between scanned surfaces, Nanite virtualized geometry, dense procedural foliage with subsurface scattering, physical materials with true PBR roughness, metalness and normal maps, visible surface weathering, moss, cracks, grime and moisture, ambient occlusion in every crevice, screen-space reflections on wet surfaces, volumetric fog, the hyper-realistic scanned-world look of modern UE5 tech demos like Matrix Awakens, photorealistic, NOT flat, NOT plastic',
  },
]

export const ERAS: { id: Era; label: string; range: string; desc: string }[] = [
  { id: 'engine', label: 'Unreal Engine 5', range: '2024', desc: 'Lumen, Nanite, path tracing, Megascans' },
  { id: 'pixel', label: 'Pixel Era', range: '1985–1998', desc: 'Handhelds & 8/16-bit sprite work' },
  { id: '32bit', label: '32-bit Era', range: '1994–1998', desc: 'Birth of 3D, wobble & fog' },
  { id: '128bit', label: '128-bit Era', range: '2000–2001', desc: '6th gen, clean low-poly' },
  { id: 'hd', label: 'HD Era', range: '2005–2006', desc: '7th gen, bloom & HDR' },
  { id: 'modern', label: 'Modern Era', range: '2013–2017', desc: '8th gen, PBR & SSAO' },
  { id: 'current', label: 'Current Gen', range: '2020+', desc: '9th gen, ray tracing & path tracing' },
]

// Era-appropriate quality boosters — replace the generic photoreal booster
// so retro platforms aren't fighting a "8K photorealistic" directive.
export const ERA_BOOSTERS: Record<Era, string> = {
  engine:
    'Unreal Engine 5.4, maximum fidelity, 8K, photorealistic, film-grade post-processing, cinematic, the quality of a billion-dollar AAA reveal',
  pixel: 'pixel-perfect, strict limited palette, crunchy visible pixels, authentic retro CRT screen, no anti-aliasing, no gradients',
  '32bit': '320x240 low resolution, CRT scanlines, visible dithering, authentic retro 3D, low-poly, no modern rendering',
  '128bit': '480p, early 2000s 3D, slight interlace artifacts, CRT-era display, soft aliased edges, authentic 6th-gen look',
  hd: '720p/1080p HD, bloom, SSAO, HDR high dynamic range, motion blur, that authentic HD-era cinematic look, color graded',
  modern:
    'physically based rendering PBR, high quality SSAO, screen-space reflections, color graded, 1080p, crisp realistic materials, modern AAA',
  current:
    'ray tracing, ray-traced global illumination, 4K, photorealistic, ultra physically based rendering, volumetric, cinematic depth of field, cutting-edge AAA',
}

export function getPlatform(id?: string): Platform | undefined {
  return PLATFORMS.find((p) => p.id === id)
}

export function platformsByEra(era: Era): Platform[] {
  return PLATFORMS.filter((p) => p.era === era)
}

/**
 * Assemble the final image prompt: subject + platform signature + era booster.
 * If no platform is given, applies the modern photoreal booster (PS4+ default).
 */
export function buildFidelityPrompt(subject: string, platformId?: string): string {
  const p = getPlatform(platformId)
  if (!p) {
    return `${subject}, ultra-detailed, photorealistic, cinematic lighting, volumetric light, shallow depth of field, film grain, color graded, professional color science, 8k, AAA concept art, production-ready`
  }
  return `${subject}, ${p.prompt}, ${ERA_BOOSTERS[p.era]}`
}

export type FidelityTier = 'cinema' | 'ultra' | 'high' | 'balanced' | 'accessible-2d';
export type FidelityPreference = FidelityTier | 'auto';

export interface DeviceCapabilities {
  gpuTier: 0 | 1 | 2 | 3;
  memoryGb: number;
  reducedMotion: boolean;
  webglAvailable?: boolean;
  devicePixelRatio?: number;
}

export interface FidelitySettings {
  tier: FidelityTier;
  mount3d: boolean;
  stationSilhouette: boolean;
  dprCap: number;
  starCount: number;
  dustCount: number;
  comets: number;
  shadowMap: number;
  antialiasing: boolean;
  materialTransmission: number;
  volumetricLayers: number;
  geometrySegments: number;
  motion: boolean;
  cameraDrift: number;
}

const BUDGETS: Record<FidelityTier, FidelitySettings> = {
  cinema: {
    tier: 'cinema',
    mount3d: true,
    stationSilhouette: true,
    dprCap: 2.4,
    starCount: 8200,
    dustCount: 920,
    comets: 12,
    shadowMap: 4096,
    antialiasing: true,
    materialTransmission: 0.92,
    volumetricLayers: 3,
    geometrySegments: 128,
    motion: true,
    cameraDrift: 0.34,
  },
  ultra: {
    tier: 'ultra',
    mount3d: true,
    stationSilhouette: true,
    dprCap: 2,
    starCount: 5600,
    dustCount: 560,
    comets: 8,
    shadowMap: 2048,
    antialiasing: true,
    materialTransmission: 0.78,
    volumetricLayers: 2,
    geometrySegments: 96,
    motion: true,
    cameraDrift: 0.26,
  },
  high: {
    tier: 'high',
    mount3d: true,
    stationSilhouette: true,
    dprCap: 1.65,
    starCount: 3600,
    dustCount: 300,
    comets: 5,
    shadowMap: 1536,
    antialiasing: true,
    materialTransmission: 0.54,
    volumetricLayers: 2,
    geometrySegments: 64,
    motion: true,
    cameraDrift: 0.18,
  },
  balanced: {
    tier: 'balanced',
    mount3d: true,
    stationSilhouette: true,
    dprCap: 1.25,
    starCount: 1900,
    dustCount: 110,
    comets: 2,
    shadowMap: 1024,
    antialiasing: false,
    materialTransmission: 0.18,
    volumetricLayers: 1,
    geometrySegments: 36,
    motion: true,
    cameraDrift: 0.1,
  },
  'accessible-2d': {
    tier: 'accessible-2d',
    mount3d: false,
    stationSilhouette: true,
    dprCap: 1,
    starCount: 0,
    dustCount: 0,
    comets: 0,
    shadowMap: 0,
    antialiasing: false,
    materialTransmission: 0,
    volumetricLayers: 0,
    geometrySegments: 0,
    motion: false,
    cameraDrift: 0,
  },
};

function automaticTier(capabilities: DeviceCapabilities): FidelityTier {
  if (capabilities.webglAvailable === false || capabilities.gpuTier === 0 || capabilities.memoryGb < 6) {
    return 'accessible-2d';
  }
  if (capabilities.gpuTier === 1 || capabilities.memoryGb < 10) return 'balanced';
  if (capabilities.gpuTier === 2 || capabilities.memoryGb < 15) return 'high';
  return 'ultra';
}

export function selectFidelity(
  capabilities: DeviceCapabilities,
  preference: FidelityPreference,
): FidelitySettings {
  const requested = preference === 'auto' ? automaticTier(capabilities) : preference;
  const tier = capabilities.webglAvailable === false ? 'accessible-2d' : requested;
  const base = BUDGETS[tier];
  if (!capabilities.reducedMotion) return { ...base };
  return {
    ...base,
    motion: false,
    dustCount: 0,
    comets: 0,
    cameraDrift: 0,
  };
}

function canCreateWebGl(): boolean {
  if (typeof document === 'undefined') return true;
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

export function detectDeviceCapabilities(reducedMotion: boolean): DeviceCapabilities {
  const nav: { deviceMemory?: number; hardwareConcurrency?: number } =
    typeof navigator === 'undefined' ? {} : navigator;
  const memoryGb = nav.deviceMemory ?? 8;
  const cores = nav.hardwareConcurrency ?? 4;
  const dpr = typeof window === 'undefined' ? 1 : window.devicePixelRatio || 1;
  const gpuTier: 0 | 1 | 2 | 3 =
    !canCreateWebGl() ? 0 : memoryGb >= 16 && cores >= 8 ? 3 : memoryGb >= 10 && cores >= 6 ? 2 : 1;
  return {
    gpuTier,
    memoryGb,
    reducedMotion,
    webglAvailable: gpuTier > 0,
    devicePixelRatio: dpr,
  };
}

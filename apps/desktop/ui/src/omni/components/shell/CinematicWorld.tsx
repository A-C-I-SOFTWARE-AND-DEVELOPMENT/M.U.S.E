import { useMemo } from 'react';
import { routeForPath } from '@/universe/catalog';
import { detectDeviceCapabilities, selectFidelity } from '@/universe/fidelity';
import { UniverseScene } from '@/universe/scene/UniverseScene';
import { useUniverseStore } from '@/universe/store';

export default function CinematicWorld({ pathname }: { pathname: string }) {
  const snapshot = useUniverseStore((state) => state.snapshot);
  const preferences = useUniverseStore((state) => state.preferences);
  const route = routeForPath(pathname);
  const settings = useMemo(
    () => selectFidelity(
      detectDeviceCapabilities(preferences.reducedMotion),
      preferences.twoDOnly ? 'accessible-2d' : preferences.fidelity,
    ),
    [preferences.fidelity, preferences.reducedMotion, preferences.twoDOnly],
  );
  return (
    <div className="omni-cinematic-world" aria-hidden="true" data-world={route.scene}>
      <UniverseScene route={route} snapshot={snapshot} settings={settings} particleDensity={preferences.particleDensity} />
      <div className="omni-world-label"><span>{route.label}</span><small>{route.room.replaceAll('-', ' ')} · {settings.tier}</small></div>
    </div>
  );
}

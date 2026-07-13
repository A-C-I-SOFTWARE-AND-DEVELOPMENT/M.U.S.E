import { routeForPath } from '../catalog.ts';
import { ShipyardBuilder } from '../components/ShipyardBuilder.tsx';
import { UniversePage } from '../components/UniversePage.tsx';
import { UniverseStatusBoundary } from '../components/UniverseStatusBoundary.tsx';
import { useUniverseStore } from '../store.ts';

export default function ShipyardPage() {
  const snapshot = useUniverseStore((state) => state.snapshot);
  const catalog = useUniverseStore((state) => state.catalog);
  const selected = useUniverseStore((state) => state.selected);
  const validate = useUniverseStore((state) => state.validateCommand);
  const execute = useUniverseStore((state) => state.executeCommand);
  const vessels = Array.isArray(snapshot?.vessels) ? snapshot.vessels : [];
  const vessel = vessels.find((entry) => entry.id === selected) ?? vessels[0] ?? null;
  const route = routeForPath('/shipyard');
  return (
    <UniversePage route={route} eyebrow="Neural Shipyard" title="Vessel Configuration Bay" description="Draft modules against real snap points, budgets, path reachability, requirements, conflicts, and trust exposure. Cosmetics remain authority-neutral.">
      <UniverseStatusBoundary>
        <ShipyardBuilder vessel={vessel} modules={catalog?.modules ?? null} viewer={snapshot?.viewer ?? null} onValidate={validate} onApply={execute} />
      </UniverseStatusBoundary>
    </UniversePage>
  );
}

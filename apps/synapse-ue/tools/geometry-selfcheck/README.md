# Geometry self-check (UE-free)

Compiles the **real** `MuseSacredGeometry.cpp`
(`apps/synapse-ue/Source/SynapseCore/Private/`) with a plain C++17 compiler
against a minimal non-UE shim (`ueshim/`), and asserts the same invariants as the
in-engine `Synapse.Geometry.*` automation suite and the Python reference:

- golden angle = 137.50776405°, φ exact;
- exact vertex counts — Platonic 4/8/6/12/20, 4-polytopes **5/8/16/24/120/600**;
- 4D rotation preserves the norm; normalized Platonic vertices sit on the unit
  shell; perspective projection is finite.

## What this proves (and what it doesn't)

✅ The geometry **algorithms compile and are numerically correct** in real C++ —
catchable *without* Unreal Engine, on any machine or CI runner with clang/gcc.

❌ It is **not** the engine build. The render module (`SynapseObservatoryRender`:
`AActor`, ISM, Niagara, delegates) needs UE 5.6 and is verified by compiling the
project on the owner's machine (`tools/build-legion.bat` /
`docs/self-hosted-runner-setup.md`). The `ueshim/` headers are a deliberately
minimal stand-in for `CoreMinimal.h` + the UHT-generated header — **not** the real
engine types.

## Run it

```bash
clang++ -std=c++17 -Wall -Wextra -Werror \
  -I apps/synapse-ue/tools/geometry-selfcheck/ueshim \
  -I apps/synapse-ue/Source/SynapseCore/Public \
  apps/synapse-ue/tools/geometry-selfcheck/selfcheck.cpp \
  apps/synapse-ue/Source/SynapseCore/Private/MuseSacredGeometry.cpp \
  -o /tmp/geometry-selfcheck && /tmp/geometry-selfcheck
```

CI runs exactly this on every push touching the geometry, on a standard ubuntu
runner (no UE), via `.github/workflows/synapse-geometry-selfcheck.yml`.

## Maintenance

`ueshim/CoreMinimal.h` covers only the UE surface `MuseSacredGeometry.cpp` uses
(FVector/FVector4/FVector2D, TArray, FMath, MoveTemp, the reflection macros). If
that .cpp starts using a new UE math helper, extend the shim to match.

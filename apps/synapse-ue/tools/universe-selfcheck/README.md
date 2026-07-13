# Universe self-check (UE-free)

`selfcheck.cpp` compiles the real header-only
`Source/SynapseUniverse/Public/MuseUniverseMath.h` with a plain C++17 compiler.
It checks metric station constants, exact meter conversion, opposite ring
rotation, the stationary dock invariant, SHA-256, stable vessel IDs, 65 mm
sample camera offsets, convergence symmetry, and deterministic shot hashes.
On success it also emits one JSON line with the C++ values so the planned
Python specification can compare every value to `tools/universe_reference.py`.

The check proves only that the shared deterministic helper compiles and matches
its reference invariants. It does not prove that UnrealHeaderTool, UBT, actors,
HTTP/reconnect code, Movie Render Queue, OpenXR, Pixel Streaming, materials, or
packaging work. Those remain UE 5.6 gates.

Use `tools/run-universe-selfcheck.ps1` on Windows. Missing compilers are reported
as an explicit open environment gate. The source-authoring stream did not run
this command.

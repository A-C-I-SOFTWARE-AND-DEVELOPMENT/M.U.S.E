// MINIMAL SELF-CHECK SHIM — NO GAMEPLAY TYPES ARE EMULATED.
// MuseUniverseMath.h is intentionally standard C++17 and does not include this
// file. The shim is reserved for future engine-light wrappers and documents the
// hard boundary: no UObject, Actor, HTTP, rendering, MRQ, XR, streaming, or
// authority behavior may be faked to turn a source check into an engine claim.
#pragma once

#include <cstdint>

using int32 = std::int32_t;
using int64 = std::int64_t;
using uint8 = std::uint8_t;


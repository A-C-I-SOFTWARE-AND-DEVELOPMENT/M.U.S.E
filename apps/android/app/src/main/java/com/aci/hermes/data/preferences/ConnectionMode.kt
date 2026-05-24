package com.aci.hermes.data.preferences

/**
 * How the app reaches its model. Three modes:
 *
 *   * [MOCK]    — no network, deterministic canned replies. UI sandbox.
 *   * [DIRECT]  — phone calls an OpenAI-compatible provider (OpenRouter,
 *                 OpenAI, custom) directly with a user-supplied API key.
 *                 Personal use only — the key lives in
 *                 EncryptedSharedPreferences on the device.
 *   * [HERMES]  — phone talks to a Hermes gateway that brokers everything
 *                 (skills, memory, tools). Multi-device, server-side
 *                 stateful — see `apps/android/docs/ARCHITECTURE.md`.
 */
enum class ConnectionMode { MOCK, DIRECT, HERMES }

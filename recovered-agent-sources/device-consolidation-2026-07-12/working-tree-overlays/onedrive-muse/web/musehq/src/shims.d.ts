// Ambient module shims for untyped vendored dependencies.

// `lang-map` (used by OpenCode's vendored content-code renderer) ships no types.
declare module "lang-map" {
  interface LangMap {
    languages(ext: string): string[]
    extensions(lang: string): string[]
  }
  const map: LangMap
  export default map
}

declare global {
  interface Window {
    __HERMES_SESSION_TOKEN__?: string
  }
}

export {}

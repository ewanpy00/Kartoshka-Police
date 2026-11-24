/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SAME_ORIGIN_API?: string
  readonly VITE_DEMO_BANNER?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

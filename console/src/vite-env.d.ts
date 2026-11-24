/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CORE_WRITE_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

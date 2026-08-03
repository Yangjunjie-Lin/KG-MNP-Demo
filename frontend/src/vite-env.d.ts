/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_TECHNICAL_VIEW?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

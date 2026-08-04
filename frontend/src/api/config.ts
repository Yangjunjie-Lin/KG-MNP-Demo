export type DataSource = "api" | "mock";

const runtimeEnv = import.meta.env;

export const apiConfig = {
  baseUrl: (runtimeEnv.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, ""),
  dataSource: (runtimeEnv.VITE_DATA_SOURCE || "api") as DataSource,
  timeoutMs: 15_000,
  technicalViewEnabled:
    runtimeEnv.VITE_ENABLE_TECHNICAL_VIEW === "true" && runtimeEnv.DEV,
};

export function resolveApiUrl(path: string, baseUrl = apiConfig.baseUrl): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl.replace(/\/$/, "")}${normalizedPath}`;
}

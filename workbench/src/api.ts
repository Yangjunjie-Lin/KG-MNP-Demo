import { QueryClient } from '@tanstack/react-query';
export const queryClient = new QueryClient({defaultOptions: {queries: {retry: false, staleTime: 0}, mutations: {retry: false}}});
let csrf = '';
export function setCsrf(value: string) { csrf = value; }
export function clearIdentity() { csrf = ''; queryClient.cancelQueries(); queryClient.clear(); }
export class ApiError extends Error { constructor(public code: string, public status: number) { super(`${code}（HTTP ${status}）`); } }
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {...init, credentials: 'same-origin', headers: {'X-CSRF-Token': csrf, ...init.headers}});
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new ApiError(data.error?.code || 'REQUEST_FAILED', response.status); }
  return response.json();
}
export function post<T>(path: string, body: unknown, key: string = crypto.randomUUID()): Promise<T> {
  return api<T>(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'Idempotency-Key': key}, body: JSON.stringify(body)});
}
export type Principal = {principal_id: string; principal_type: string; permissions: string[]};
export type Project = {project_id: string; project_name: string; manifest_project_id: string; domain_pack: string; domain_pack_version: string; authority_revision: number; status: string};
export type Pack = {pack_id: string; pack_version: string; display_name: string; lifecycle: string; availability: string};
// Domain documents are versioned core contracts. These local views only select
// fields for display; submitted requests use resource-specific form bodies.
export type Document = {[key: string]: unknown};
export type Result = {job_id: string; operation: string; revision: number; result: Document};
export type Job = {job_id: string; operation_id: string; status: string; attempt: number; error: {code: string} | null};
export type ProjectState = {project: Project; results: Result[]; jobs: Job[]; registry_head: string};
export function object(value: unknown): Document { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Document : {}; }
export function rows(value: unknown): Document[] { return Array.isArray(value) ? value.map(object) : []; }
export function str(value: unknown) { return typeof value === 'string' ? value : value === null || value === undefined ? '' : JSON.stringify(value); }
export function outputs(state: ProjectState, operation: string, key: string): Document[] { return state.results.filter(r => r.operation === operation).map(r => object(r.result[key])); }

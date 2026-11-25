import type { Job, Model, Niche, NicheSpec, NicheStatus } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/proxy${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Keine Verbindung. Prüfe dein Internet und versuch es noch einmal.");
  }
  if (res.status === 401) {
    window.location.href = "/login";
    throw new ApiError(401, "Nicht angemeldet");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : "Das hat nicht geklappt.";
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const post = (body?: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body ?? {}) });
const patch = (body: unknown): RequestInit => ({ method: "PATCH", body: JSON.stringify(body) });

export const fetcher = <T,>(path: string) => req<T>(path);

export const api = {
  createModel: (body: Pick<Model, "name" | "vibe" | "language" | "market">) => req<Model>("/models", post(body)),
  updateModel: (id: string, body: Partial<Model>) => req<Model>(`/models/${id}`, patch(body)),
  deleteModel: (id: string) => req<void>(`/models/${id}`, { method: "DELETE" }),
  generateNiches: (modelId: string, count: number) => req<Job>(`/models/${modelId}/niches/generate`, post({ count })),
  nicheFromBrief: (modelId: string, brief: string) => req<Job>(`/models/${modelId}/niches/from-brief`, post({ brief })),
  improveNiche: (id: string, hint: string) => req<Job>(`/niches/${id}/improve`, post({ hint })),
  updateNiche: (id: string, body: Partial<NicheSpec>) => req<Niche>(`/niches/${id}`, patch(body)),
  setNicheStatus: (id: string, status: NicheStatus) => req<Niche>(`/niches/${id}/status`, post({ status })),
  deleteNiche: (id: string) => req<void>(`/niches/${id}`, { method: "DELETE" }),
  getJob: <R,>(id: string) => req<Job<R>>(`/jobs/${id}`),
};

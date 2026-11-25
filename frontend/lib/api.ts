import type { Content, Job, Model, Niche, NicheSpec, NicheStatus, PhotoMode, Source } from "./types";

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

const JSON_HEADERS = { "Content-Type": "application/json" };
const post = (body?: unknown): RequestInit => ({ method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body ?? {}) });
const patch = (body: unknown): RequestInit => ({ method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body) });

/** Adresse, unter der ein gespeichertes Bild angezeigt wird. */
export const mediaUrl = (kind: "models" | "content", id: string, field: string, index: number) =>
  `/api/proxy/media/${kind}/${id}/${field}/${index}`;

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
  createImages: (nicheId: string, body: { kind: "carousel" | "photos"; count: number; mode: PhotoMode }) =>
    req<Content[]>(`/niches/${nicheId}/content/images`, post(body)),
  decideContent: (id: string, decision: "approve" | "reject" | "reopen") =>
    req<Content>(`/content/${id}/decision`, post({ decision })),
  retryContent: (id: string, freshImage = false) => req<Content>(`/content/${id}/retry`, post({ freshImage })),
  createReels: (nicheId: string, sources: string[], videoModel: "kling-3.0" | "kling-2.6") =>
    req<Content[]>(`/niches/${nicheId}/content/reels`, post({ sources, videoModel })),
  addSources: (handles: string[], market: "DE" | "US", category: string) =>
    req<{ created: Source[]; skipped: string[] }>("/viral/sources", post({ handles, market, category })),
  updateSource: (id: string, body: Partial<Pick<Source, "state" | "market" | "category">>) => req<Source>(`/viral/sources/${id}`, patch(body)),
  deleteSource: (id: string) => req<void>(`/viral/sources/${id}`, { method: "DELETE" }),
  scrapeViral: () => req<Job>("/viral/scrape", post()),
  setViralStatus: (id: string, status: "New" | "Dismissed") => req<unknown>(`/viral/reels/${id}/status`, post({ status })),
  importViral: (viralIds: string[], nicheId: string, variants: number, videoModel: "kling-3.0" | "kling-2.6") =>
    req<{ count: number }>("/viral/import", post({ viralIds, nicheId, variants, videoModel })),
  uploadVideo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<{ url: string }>("/uploads/video", { method: "POST", body: form });
  },
  deleteContent: (id: string) => req<void>(`/content/${id}`, { method: "DELETE" }),
  addReferences: (modelId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return req<Model>(`/models/${modelId}/references`, { method: "POST", body: form });
  },
  removeReference: (modelId: string, index: number) =>
    req<Model>(`/models/${modelId}/references/${index}`, { method: "DELETE" }),
};

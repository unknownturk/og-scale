export type NicheStatus = "Proposed" | "Approved" | "Rejected";

export type Scenario = { name: string; setting: string; action: string; [extra: string]: unknown };
export type Theme = { name: string; hook: string };

export type NicheSpec = {
  name: string;
  styleVibe: string;
  outfits: string[];
  backgrounds: string[];
  scenarios: Scenario[];
  hooks: string[];
  themes: Theme[];
  alwaysInclude: string;
  dressCode: "" | "authentic";
  nsfwLevel: "sfw" | "spicy" | "nsfw";
};

export type Niche = NicheSpec & {
  id: string;
  modelId: string;
  status: NicheStatus;
  source: "AI" | "Brief" | "Manual";
  market: "DE" | "US";
  created: string;
};

export type Model = {
  id: string;
  name: string;
  vibe: string;
  language: "German" | "English";
  market: "DE" | "US";
  notes: string;
  nicheCounts?: Record<NicheStatus, number>;
};

export type Job<R = unknown> = {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed";
  result: R | null;
  error: string;
};

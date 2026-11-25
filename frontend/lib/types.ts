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
  bodyType: "" | "normal" | "slim" | "curvy" | "athletic" | "busty";
  referenceImages: string[];
  nicheCounts?: Record<NicheStatus, number>;
};

export type Job<R = unknown> = {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed";
  result: R | null;
  error: string;
};

export type ContentStatus = "Working" | "Review" | "Approved" | "Rejected" | "Failed";
export type PhotoMode = "niche" | "lifestyle" | "story_daily" | "story_me" | "story_cta";

export type Content = {
  id: string;
  title: string;
  modelId: string;
  nicheId: string;
  type: "Carousel" | "Photo" | "Reel";
  status: ContentStatus;
  error: string;
  images: string[];
  step: "images" | "frame" | "image" | "video";
  imageCount: number;
  slotCount: number;
  hasFrame: boolean;
  hasSource: boolean;
  hasVideo: boolean;
  created: string;
};

export type Source = { id: string; handle: string; market: "DE" | "US"; category: string; state: "Active" | "Disabled"; lastScraped: string };

export type ViralReel = {
  id: string;
  reelUrl: string;
  owner: string;
  market: "DE" | "US";
  category: string;
  caption: string;
  likes: number;
  comments: number;
  views: number;
  postedAt: string;
  viralScore: number;
  outperform: number;
  potential: number;
  status: "New" | "Imported" | "Dismissed";
};

export type ViralStatus = { provider: string | null; lastScrape: string; running: boolean; jobId: string | null; autoHours: number };
export type ScrapeResult = { created: number; found: number; sources: number; sourcesWithReels: number; errors: string[]; removed: number };

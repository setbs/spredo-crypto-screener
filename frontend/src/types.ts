export interface Project {
  id: string;
  name: string;
  symbol: string;
  market_cap: number;
  fdv: number;
  volume_24h: number;
  tvl: number;
  max_supply: number;
  total_supply: number;
  preview_listing: true;
}

export interface ProjectsResponse {
  projects: Project[];
  inspected_projects: InspectedProject[];
  meta: {
    mode: "live" | "demo";
    status: "scanning" | "complete" | "error";
    phase: "markets" | "details" | "complete";
    error: string | null;
    rejection_counts: Record<string, number>;
    fetched_at: string;
    cached: boolean;
    market_coins_scanned: number;
    candidates: number;
    details_checked: number;
    market_scan_truncated: boolean;
    detail_scan_truncated: boolean;
    warnings: string[];
  };
}

export interface InspectedProject {
  id: string;
  name: string;
  symbol: string;
  market_cap: number | null;
  fdv: number | null;
  volume_24h: number | null;
  tvl: number | null;
  preview_listing: boolean | null;
  rejection_reasons: string[];
}

export type SortKey = "market_cap" | "volume_24h";
export type SortDirection = "asc" | "desc";

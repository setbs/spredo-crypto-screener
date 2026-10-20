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
  meta: {
    mode: "live" | "demo";
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

export type SortKey = "market_cap" | "volume_24h";
export type SortDirection = "asc" | "desc";

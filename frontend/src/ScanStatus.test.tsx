import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ScanDiagnostics, ScanStatus } from "./ScanStatus";
import type { ProjectsResponse } from "./types";

function scan(status: ProjectsResponse["meta"]["status"]): ProjectsResponse {
  return {
    projects: [],
    inspected_projects: [{
      id: "observed-project",
      name: "Observed project",
      symbol: "obs",
      market_cap: 123_000,
      fdv: 456_000,
      volume_24h: 67_000,
      tvl: null,
      preview_listing: false,
      rejection_reasons: ["preview_listing is false", "TVL is unavailable"],
    }],
    meta: {
      mode: "live",
      status,
      phase: status === "complete" ? "complete" : "details",
      error: status === "error" ? "Rate limit exceeded" : null,
      rejection_counts: { "preview_listing is false": 22, "TVL is unavailable": 6 },
      fetched_at: "2026-10-20T12:00:00Z",
      cached: false,
      market_coins_scanned: 1_250,
      candidates: 200,
      details_checked: 30,
      market_scan_truncated: false,
      detail_scan_truncated: false,
      warnings: [],
    },
  };
}

describe("live scan state and evidence", () => {
  it("shows progress as incomplete until the backend reports completion", () => {
    const pending = renderToStaticMarkup(<ScanStatus data={scan("scanning")} />);
    expect(pending).toContain("Results are incomplete until the scan finishes");
    expect(pending).toContain("1,250 market listings");
    expect(pending).toContain("30 detail checks completed");
    expect(pending).not.toContain("Full scan complete");

    const complete = renderToStaticMarkup(<ScanStatus data={scan("complete")} />);
    expect(complete).toContain("Full scan complete");
    expect(complete).not.toContain("Results are incomplete");
  });

  it("preserves progress in the error state without declaring the scan complete", () => {
    const html = renderToStaticMarkup(<ScanStatus data={scan("error")} />);
    expect(html).toContain("Scan interrupted — progress saved");
    expect(html).toContain("30 detail checks completed");
    expect(html).not.toContain("Full scan complete");
  });

  it("labels rejected live evidence separately and preserves missing values", () => {
    const html = renderToStaticMarkup(<ScanDiagnostics data={scan("complete")} />);
    expect(html).toContain("Rejected project samples, not qualifying results");
    expect(html).toContain("Observed project");
    expect(html).toContain("$123K");
    expect(html).toContain("Unavailable");
    expect(html).toContain("preview_listing is false; TVL is unavailable");
    expect(html).toContain("the completed scan");
    expect(html).toContain("One project can fail multiple criteria");
  });

  it("does not label local fixtures as real inspected projects", () => {
    const data = scan("complete");
    data.meta.mode = "demo";
    expect(renderToStaticMarkup(<ScanDiagnostics data={data} />)).toBe("");
    expect(renderToStaticMarkup(<ScanStatus data={data} />)).toBe("");
  });
});

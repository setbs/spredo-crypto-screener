import { formatCurrency } from "./projects";
import type { ProjectsResponse } from "./types";

export function ScanStatus({ data }: { data: ProjectsResponse }) {
  const { meta } = data;
  if (meta.mode !== "live") return null;

  return (
    <section
      className={`scan-status scan-${meta.status}`}
      aria-label="Live scan progress"
      aria-live="polite"
    >
      <div className="scan-heading">
        <span className="scan-indicator" aria-hidden="true" />
        <strong>
          {meta.status === "scanning"
            ? meta.phase === "markets"
              ? "Scanning CoinGecko market pages…"
              : "Checking all candidate project details…"
            : meta.status === "error"
              ? "Scan interrupted — progress saved"
              : "Full scan complete"}
        </strong>
        <span>
          {meta.status === "scanning"
            ? "Updates automatically every 2 seconds"
            : meta.cached
              ? "Saved results"
              : "Latest results"}
        </span>
      </div>
      <p>
        {meta.market_coins_scanned.toLocaleString("en-US")} market listings
        scanned · {meta.candidates.toLocaleString("en-US")} candidates ·{" "}
        {meta.details_checked.toLocaleString("en-US")} detail checks completed
      </p>
      {meta.status === "scanning" && (
        <p className="scan-explanation">
          {meta.phase === "markets"
            ? "Loading every available market page before checking candidate details."
            : "Each candidate is checked against all six criteria. Rate limits can make the first scan take several minutes."}{" "}
          Results are incomplete until the scan finishes. You can leave this page
          open while the Python backend continues.
        </p>
      )}
    </section>
  );
}

export function ScanDiagnostics({ data }: { data: ProjectsResponse }) {
  if (data.meta.mode !== "live") return null;
  const currency = (value: number | null) =>
    value === null ? "Unavailable" : formatCurrency(value);
  const reasons = Object.entries(data.meta.rejection_counts).sort(
    (a, b) => b[1] - a[1],
  );
  if (!data.inspected_projects.length && !reasons.length) return null;

  return (
    <section className="diagnostics-panel" aria-labelledby="diagnostics-title">
      <div className="diagnostics-heading">
        <h2 id="diagnostics-title">Scan diagnostics — rejected projects</h2>
        <p>
          Actual CoinGecko values from the scan. The sample projects below failed the base
          criteria and are excluded from the qualifying results above. Missing
          values are not treated as zero.
        </p>
        <p>
          <code>preview_listing = true</code> means an upcoming listing. A project
          with a false or missing flag cannot pass the requested criteria.
        </p>
      </div>
      {data.projects.length === 0 && reasons.length > 0 && (
        <div className="rejection-counts">
          <strong>Rejection reasons across {data.meta.status === "complete" ? "the completed scan" : "the scan so far"}</strong>
          <ul>
            {reasons.map(([reason, count]) => (
              <li key={reason}>
                {reason}: <strong>{count.toLocaleString("en-US")}</strong>
              </li>
            ))}
          </ul>
          <p>One project can fail multiple criteria.</p>
        </div>
      )}
      {data.inspected_projects.length > 0 && <div className="table-scroll">
        <table className="diagnostics-table">
          <caption className="sr-only">
            Rejected project samples, not qualifying results. All monetary values
            are in USD.
          </caption>
          <thead>
            <tr>
              <th scope="col">Project</th>
              <th scope="col" className="numeric">Market cap</th>
              <th scope="col" className="numeric">FDV</th>
              <th scope="col" className="numeric">24h volume</th>
              <th scope="col" className="numeric">TVL</th>
              <th scope="col">Preview listing</th>
              <th scope="col">Why rejected</th>
            </tr>
          </thead>
          <tbody>
            {data.inspected_projects.map((project) => (
              <tr key={project.id}>
                <td>
                  <span className="project-name">{project.name}</span>
                  <span className="project-symbol">{project.symbol.toUpperCase()}</span>
                </td>
                <td className="numeric">{currency(project.market_cap)}</td>
                <td className="numeric">{currency(project.fdv)}</td>
                <td className="numeric">{currency(project.volume_24h)}</td>
                <td className="numeric">{currency(project.tvl)}</td>
                <td>{project.preview_listing === null ? "Unavailable" : String(project.preview_listing)}</td>
                <td className="rejection-reasons">{project.rejection_reasons.join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
    </section>
  );
}

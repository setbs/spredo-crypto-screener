import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { formatCurrency, formatFullCurrency, selectProjects } from "./projects";
import type { ProjectsResponse, SortDirection, SortKey } from "./types";

type IconName = "search" | "refresh" | "arrow" | "info" | "grid";

function Icon({
  name,
  className = "",
}: {
  name: IconName;
  className?: string;
}) {
  const paths: Record<IconName, ReactNode> = {
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 4 4" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5" />
        <path d="M6.1 7a7 7 0 0 1 11.5-2L20 8M4 16l2.4 3A7 7 0 0 0 18 17" />
      </>
    ),
    arrow: (
      <>
        <path d="M12 4v16m-6-6 6 6 6-6" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6m0-10v.1" />
      </>
    ),
    grid: (
      <>
        <rect x="4" y="4" width="6" height="6" rx="1" />
        <rect x="14" y="4" width="6" height="6" rx="1" />
        <rect x="4" y="14" width="6" height="6" rx="1" />
        <rect x="14" y="14" width="6" height="6" rx="1" />
      </>
    ),
  };
  return (
    <svg
      className={`icon ${className}`}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

function App() {
  const [data, setData] = useState<ProjectsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [fdvInput, setFdvInput] = useState("100000000");
  const [sortKey, setSortKey] = useState<SortKey>("market_cap");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const activeRequest = useRef<AbortController | null>(null);

  const loadProjects = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/projects", {
        signal: controller.signal,
      });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : `The API returned an error (${response.status}). Please try again.`,
        );
      }
      if (
        !Array.isArray(body.projects) ||
        !body.meta ||
        !["live", "demo"].includes(body.meta.mode)
      ) {
        throw new Error(
          "The API returned an unexpected response. Please try again.",
        );
      }
      setData(body as ProjectsResponse);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setError(
        cause instanceof TypeError || cause instanceof SyntaxError
          ? "Could not reach the project API. Make sure the Python backend is running, then try again."
          : cause instanceof Error
            ? cause.message
            : "Could not load projects. Please try again.",
      );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
    return () => activeRequest.current?.abort();
  }, [loadProjects]);

  const maxFdv = fdvInput.trim() === "" ? null : Number(fdvInput);
  const invalidFdv =
    maxFdv !== null && (!Number.isFinite(maxFdv) || maxFdv < 0);
  const projects = useMemo(
    () =>
      selectProjects(data?.projects ?? [], {
        search,
        maxFdv: invalidFdv ? null : maxFdv,
        sortKey,
        sortDirection,
      }),
    [data, search, maxFdv, invalidFdv, sortKey, sortDirection],
  );
  const marketCap = projects.reduce(
    (sum, project) => sum + project.market_cap,
    0,
  );
  const tradingVolume = projects.reduce(
    (sum, project) => sum + project.volume_24h,
    0,
  );
  const filtersChanged =
    search !== "" ||
    fdvInput !== "100000000" ||
    sortKey !== "market_cap" ||
    sortDirection !== "desc";
  const initialLoading = loading && !data;

  function resetFilters() {
    setSearch("");
    setFdvInput("100000000");
    setSortKey("market_cap");
    setSortDirection("desc");
  }

  function toggleSort(key: SortKey) {
    setSortDirection(
      key === sortKey && sortDirection === "desc" ? "asc" : "desc",
    );
    setSortKey(key);
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="./" aria-label="Float home">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
          </span>
          <span>
            float<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="header-divider" />
        <span className="header-section">
          <Icon name="grid" />
          Project screener
        </span>
        <div className="header-right">
          <span className="network-dot" />
          Powered by CoinGecko<span className="header-label">USD</span>
        </div>
      </header>

      <main>
        <section className="page-intro">
          <div>
            <p className="eyebrow">
              <span />
              LESS NOISE. MORE SIGNAL.
            </p>
            <h1>Project screener</h1>
            <p className="intro-copy">
              Discover crypto projects with fully issued supply and real market
              activity.
            </p>
          </div>
          <button
            className="button refresh-button"
            onClick={() => void loadProjects()}
            disabled={loading}
          >
            <Icon name="refresh" className={loading ? "spin" : ""} />
            {loading ? "Fetching data" : "Refresh data"}
          </button>
        </section>

        <details className="criteria-panel">
          <summary>
            <span className="criteria-title">
              <span className="criteria-check">✓</span>Six criteria. One focused
              list.
            </span>
            <span className="criteria-preview">
              FDV &lt; $100M <span>·</span> Fully issued supply
            </span>
            <span className="criteria-toggle">
              View criteria <span aria-hidden="true">⌄</span>
            </span>
          </summary>
          <div className="criteria-grid">
            {[
              "Market cap > $0",
              "Preview listing = true",
              "Max supply = total supply",
              "FDV < $100M",
              "24h volume > $50K",
              "TVL > $50K",
            ].map((criterion) => (
              <span key={criterion}>
                <span className="small-check">✓</span>
                {criterion}
              </span>
            ))}
          </div>
        </details>

        {data?.meta.mode === "demo" && (
          <div className="notice demo-notice" role="status">
            <Icon name="info" />
            <div>
              <strong>You’re viewing demo data.</strong> These are sample
              projects for exploring the screener. They are not live market
              results.
            </div>
          </div>
        )}
        {error && (
          <div className="notice error-notice" role="alert">
            <Icon name="info" />
            <div>
              <strong>Unable to load projects.</strong> {error}
              {data && " The previous results remain visible."}
            </div>
            <button
              className="text-button"
              onClick={() => void loadProjects()}
              disabled={loading}
            >
              Try again ↗
            </button>
          </div>
        )}
        {data && data.meta.warnings.length > 0 && (
          <div className="notice warning-notice">
            <Icon name="info" />
            <div>
              <strong>Data coverage note</strong>
              <ul>
                {data.meta.warnings.map((warning, index) => (
                  <li key={`${index}-${warning}`}>{warning}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <section
          className="stats-grid"
          aria-label="Summary of visible projects"
        >
          <article className="stat-card stat-primary">
            <div className="stat-label">
              Matching projects<span className="stat-decoration">↗</span>
            </div>
            <div className="stat-value">
              {data ? projects.length.toLocaleString("en-US") : "—"}
              <span className="stat-unit">projects</span>
            </div>
            <p>
              Of {data ? data.projects.length.toLocaleString("en-US") : "—"}{" "}
              projects passing the base criteria
            </p>
          </article>
          <article className="stat-card">
            <div className="stat-label">
              Combined market cap<span className="stat-mini-icon">◈</span>
            </div>
            <div className="stat-value" title={formatFullCurrency(marketCap)}>
              {data ? formatCurrency(marketCap) : "—"}
            </div>
            <p>Across your current results</p>
          </article>
          <article className="stat-card">
            <div className="stat-label">
              24h trading volume<span className="stat-mini-icon">▥</span>
            </div>
            <div
              className="stat-value"
              title={formatFullCurrency(tradingVolume)}
            >
              {data ? formatCurrency(tradingVolume) : "—"}
            </div>
            <p>Total activity in the last 24 hours</p>
          </article>
        </section>

        <section
          className="results-panel"
          aria-labelledby="results-title"
          aria-busy={loading}
        >
          <div className="results-heading">
            <div className="results-title">
              <h2 id="results-title">All projects</h2>
              <span className="count-badge">
                {data ? projects.length : "—"}
              </span>
            </div>
            <div className="data-status">
              {data ? (
                <>
                  <span className={`mode-badge ${data.meta.mode}`}>
                    <span />
                    {data.meta.mode === "live" ? "LIVE DATA" : "DEMO DATA"}
                  </span>
                  <span className="updated-at">
                    {data.meta.cached ? "Cached" : "Fetched"}{" "}
                    <time
                      dateTime={data.meta.fetched_at}
                      title={new Date(data.meta.fetched_at).toLocaleString()}
                    >
                      {new Date(data.meta.fetched_at).toLocaleTimeString(
                        undefined,
                        { hour: "2-digit", minute: "2-digit" },
                      )}
                    </time>
                  </span>
                </>
              ) : (
                <span className="updated-at">
                  {loading ? "Connecting to your backend…" : "No data loaded"}
                </span>
              )}
            </div>
          </div>

          <div className="filter-bar">
            <div className="field search-field">
              <label htmlFor="project-search">Search projects</label>
              <div className="input-wrap">
                <Icon name="search" />
                <input
                  id="project-search"
                  type="search"
                  placeholder="Search by name or symbol…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
            </div>
            <div className="field fdv-field">
              <label htmlFor="max-fdv">
                Max FDV <span>USD</span>
              </label>
              <div
                className={`input-wrap ${invalidFdv ? "input-invalid" : ""}`}
              >
                <span className="input-prefix">$</span>
                <input
                  id="max-fdv"
                  type="number"
                  min="0"
                  step="any"
                  placeholder="No additional limit"
                  value={fdvInput}
                  onChange={(event) => setFdvInput(event.target.value)}
                  aria-invalid={invalidFdv}
                  aria-describedby="fdv-hint"
                />
              </div>
            </div>
            <div className="field sort-field">
              <label htmlFor="sort-order">Sort by</label>
              <select
                id="sort-order"
                value={`${sortKey}:${sortDirection}`}
                onChange={(event) => {
                  const [key, direction] = event.target.value.split(":");
                  setSortKey(key as SortKey);
                  setSortDirection(direction as SortDirection);
                }}
              >
                <option value="market_cap:desc">Market cap: high to low</option>
                <option value="market_cap:asc">Market cap: low to high</option>
                <option value="volume_24h:desc">24h volume: high to low</option>
                <option value="volume_24h:asc">24h volume: low to high</option>
              </select>
            </div>
          </div>
          <div className="filter-helper">
            <span id="fdv-hint" className={invalidFdv ? "invalid-hint" : ""}>
              {invalidFdv
                ? "Enter a non-negative FDV limit."
                : "FDV must be strictly below your limit. Base criteria always apply."}
            </span>
            <button
              className="text-button reset-button"
              onClick={resetFilters}
              disabled={!filtersChanged}
            >
              Reset filters
            </button>
          </div>

          {initialLoading ? (
            <div className="table-loading" role="status">
              <div className="loading-orbit">
                <span />
              </div>
              <h3>Finding the signal</h3>
              <p>Fetching markets and checking project details.</p>
              <span>The first scan can take a little longer.</span>
            </div>
          ) : !data ? (
            <div className="empty-state">
              <div className="empty-icon">
                <Icon name="grid" />
              </div>
              <h3>Your project list will appear here</h3>
              <p>Connect to the Python API to get started.</p>
              <button
                className="button"
                onClick={() => void loadProjects()}
                disabled={loading}
              >
                Try again
              </button>
            </div>
          ) : projects.length === 0 ? (
            <div className="empty-state" role="status">
              <div className="empty-icon">
                <Icon name="search" />
              </div>
              <h3>
                {data.projects.length
                  ? "No projects match your filters"
                  : "No projects passed the base criteria"}
              </h3>
              <p>
                {data.projects.length
                  ? "Try another project name or increase your FDV limit."
                  : "These criteria are selective. Review the coverage notes or refresh later."}
              </p>
              {filtersChanged && (
                <button className="button" onClick={resetFilters}>
                  Reset filters
                </button>
              )}
            </div>
          ) : (
            <div className="table-scroll">
              <table>
                <caption className="sr-only">
                  Cryptocurrency projects passing all six backend criteria and
                  your current filters. All values in USD.
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="rank-column">
                      #
                    </th>
                    <th scope="col">Project</th>
                    <th
                      scope="col"
                      className="numeric"
                      aria-sort={
                        sortKey === "market_cap"
                          ? sortDirection === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      <button
                        className={`table-sort ${sortKey === "market_cap" ? "active" : ""}`}
                        onClick={() => toggleSort("market_cap")}
                      >
                        Market cap
                        <Icon
                          name="arrow"
                          className={
                            sortKey === "market_cap" && sortDirection === "asc"
                              ? "arrow-up"
                              : ""
                          }
                        />
                      </button>
                    </th>
                    <th scope="col" className="numeric">
                      <abbr title="Fully diluted valuation">FDV</abbr>
                    </th>
                    <th
                      scope="col"
                      className="numeric"
                      aria-sort={
                        sortKey === "volume_24h"
                          ? sortDirection === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      <button
                        className={`table-sort ${sortKey === "volume_24h" ? "active" : ""}`}
                        onClick={() => toggleSort("volume_24h")}
                      >
                        24h volume
                        <Icon
                          name="arrow"
                          className={
                            sortKey === "volume_24h" && sortDirection === "asc"
                              ? "arrow-up"
                              : ""
                          }
                        />
                      </button>
                    </th>
                    <th scope="col" className="numeric">
                      <abbr title="Total value locked">TVL</abbr>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project, index) => (
                    <tr key={project.id}>
                      <td className="rank-column">
                        {String(index + 1).padStart(2, "0")}
                      </td>
                      <td>
                        <div className="project-identity">
                          <span
                            className={`project-avatar avatar-${index % 5}`}
                            aria-hidden="true"
                          >
                            {project.symbol.slice(0, 2).toUpperCase()}
                          </span>
                          <div>
                            <span className="project-name">{project.name}</span>
                            <span className="project-symbol">
                              {project.symbol.toUpperCase()}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td
                        className="numeric market-cap"
                        title={formatFullCurrency(project.market_cap)}
                      >
                        {formatCurrency(project.market_cap)}
                      </td>
                      <td
                        className="numeric"
                        title={formatFullCurrency(project.fdv)}
                      >
                        {formatCurrency(project.fdv)}
                      </td>
                      <td
                        className="numeric volume-value"
                        title={formatFullCurrency(project.volume_24h)}
                      >
                        {formatCurrency(project.volume_24h)}
                      </td>
                      <td
                        className="numeric"
                        title={formatFullCurrency(project.tvl)}
                      >
                        {formatCurrency(project.tvl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="table-footer">
            <span aria-live="polite">
              {data
                ? `Showing ${projects.length} of ${data.projects.length} qualifying projects`
                : "Results from your Python backend"}
            </span>
            <span>All values in USD</span>
          </div>
        </section>

        {data && (
          <div className="coverage">
            <span className="coverage-dot" />
            <span>
              Scan coverage:{" "}
              <strong>
                {data.meta.market_coins_scanned.toLocaleString("en-US")}
              </strong>{" "}
              market listings ·{" "}
              <strong>{data.meta.candidates.toLocaleString("en-US")}</strong>{" "}
              candidates ·{" "}
              <strong>
                {data.meta.details_checked.toLocaleString("en-US")}
              </strong>{" "}
              detail checks
              {(data.meta.market_scan_truncated ||
                data.meta.detail_scan_truncated) &&
                " · Partial scan"}
            </span>
          </div>
        )}

        <footer className="page-footer">
          <span className="footer-brand">float.</span>
          <span>A little clarity in a crowded market.</span>
          <span>Market data is informational.</span>
        </footer>
      </main>
    </div>
  );
}

export default App;

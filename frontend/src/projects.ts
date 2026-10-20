import type { Project, SortDirection, SortKey } from "./types";

export interface ProjectFilters {
  search: string;
  maxFdv: number | null;
  sortKey: SortKey;
  sortDirection: SortDirection;
}

export function selectProjects(
  projects: Project[],
  filters: ProjectFilters,
): Project[] {
  const query = filters.search.trim().toLocaleLowerCase();
  const direction = filters.sortDirection === "asc" ? 1 : -1;

  return projects
    .filter((project) => {
      const matchesSearch =
        !query ||
        project.name.toLocaleLowerCase().includes(query) ||
        project.symbol.toLocaleLowerCase().includes(query);
      const matchesFdv =
        filters.maxFdv === null || project.fdv < filters.maxFdv;
      return matchesSearch && matchesFdv;
    })
    .sort(
      (a, b) =>
        direction * (a[filters.sortKey] - b[filters.sortKey]) ||
        a.name.localeCompare(b.name) ||
        a.id.localeCompare(b.id),
    );
}

const compactCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 2,
});

const fullCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function formatCurrency(value: number): string {
  return value < 1_000
    ? fullCurrency.format(value)
    : compactCurrency.format(value);
}

export function formatFullCurrency(value: number): string {
  return fullCurrency.format(value);
}

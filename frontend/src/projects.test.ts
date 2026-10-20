import { describe, expect, it } from "vitest";
import { selectProjects } from "./projects";
import type { Project } from "./types";

const projects: Project[] = [
  {
    id: "ether",
    name: "Ethereum Sample",
    symbol: "eth",
    market_cap: 300,
    fdv: 1_000,
    volume_24h: 20,
    tvl: 100,
    max_supply: 100,
    total_supply: 100,
    preview_listing: true,
  },
  {
    id: "amber",
    name: "Amber",
    symbol: "amb",
    market_cap: 100,
    fdv: 500,
    volume_24h: 50,
    tvl: 100,
    max_supply: 100,
    total_supply: 100,
    preview_listing: true,
  },
  {
    id: "beta",
    name: "Beta",
    symbol: "bet",
    market_cap: 200,
    fdv: 750,
    volume_24h: 10,
    tvl: 100,
    max_supply: 100,
    total_supply: 100,
    preview_listing: true,
  },
];

const defaults = {
  search: "",
  maxFdv: null,
  sortKey: "market_cap",
  sortDirection: "desc",
} as const;

describe("project filtering and sorting", () => {
  it("finds partial names case-insensitively and trims search input", () => {
    expect(
      selectProjects(projects, { ...defaults, search: "  tHeR  " }).map(
        (p) => p.id,
      ),
    ).toEqual(["ether"]);
  });

  it("also supports a symbol search", () => {
    expect(
      selectProjects(projects, { ...defaults, search: "AMB" }).map((p) => p.id),
    ).toEqual(["amber"]);
  });

  it("applies a strict FDV upper bound and handles zero", () => {
    expect(
      selectProjects(projects, { ...defaults, maxFdv: 750 }).map((p) => p.id),
    ).toEqual(["amber"]);
    expect(selectProjects(projects, { ...defaults, maxFdv: 0 })).toEqual([]);
  });

  it("combines the search and FDV filters", () => {
    expect(
      selectProjects(projects, { ...defaults, search: "eth", maxFdv: 1_000 }),
    ).toEqual([]);
  });

  it.each([
    ["market_cap", "asc", ["amber", "beta", "ether"]],
    ["market_cap", "desc", ["ether", "beta", "amber"]],
    ["volume_24h", "asc", ["beta", "ether", "amber"]],
    ["volume_24h", "desc", ["amber", "ether", "beta"]],
  ] as const)(
    "sorts %s %s without mutating source data",
    (sortKey, sortDirection, expected) => {
      const original = [...projects];
      expect(
        selectProjects(projects, { ...defaults, sortKey, sortDirection }).map(
          (p) => p.id,
        ),
      ).toEqual(expected);
      expect(projects).toEqual(original);
    },
  );

  it("returns an empty result when a search has no match", () => {
    expect(
      selectProjects(projects, { ...defaults, search: "missing" }),
    ).toEqual([]);
  });
});

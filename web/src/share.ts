export const viewIds = [
  "decision",
  "experiment",
  "assumptions",
  "history",
  "strategy",
] as const;
export type ViewId = (typeof viewIds)[number];

export function readShareState(
  hash: string,
  scenarioIds: string[],
): { view: ViewId; scenario?: string } {
  if (hash.length > 500) return { view: "decision" };
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const rawView = params.get("view");
  const rawScenario = params.get("scenario");
  return {
    view: viewIds.includes(rawView as ViewId)
      ? (rawView as ViewId)
      : "decision",
    ...(rawScenario && scenarioIds.includes(rawScenario)
      ? { scenario: rawScenario }
      : {}),
  };
}

export function shareHash(view: ViewId, scenario?: string): string {
  const params = new URLSearchParams({ view });
  if (scenario) params.set("scenario", scenario);
  return `#${params.toString()}`;
}

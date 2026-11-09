import type { Dashboard, Project, Recommendation } from "./api";

type Section = Dashboard["sections"][number];
export type FeaturedItem =
  | { kind: "project"; project: Project }
  | { kind: "article"; item: Recommendation; section: Section };

export function selectFeatured(data: Dashboard): FeaturedItem[] {
  const seen = new Set<string>();
  const projects = [...data.projects, ...data.emerging_projects].filter(
    (project) => {
      if (seen.has(project.article_id)) return false;
      seen.add(project.article_id);
      return true;
    },
  );
  seen.clear();
  const result: FeaturedItem[] = [];
  // Reserve two seats for observed growth / new projects, preserving server order.
  for (const project of projects.slice(0, 2)) {
    seen.add(project.article_id);
    result.push({ kind: "project", project });
  }
  const pools = data.sections.flatMap((section) => {
    const quota =
      data.policy?.section_limits[section.id] ?? section.items.length;
    if (quota <= 0) return [];
    const items = section.items.slice(0, quota).filter((item) => {
      if (seen.has(item.article.id)) return false;
      seen.add(item.article.id);
      return true;
    });
    return [{ section, items, quota, taken: 0 }];
  });
  while (result.length < 12) {
    let selected: (typeof pools)[number] | undefined;
    for (const pool of pools) {
      if (!pool.items.length) continue;
      const recent = Boolean(pool.items[0].exposure?.recent);
      const selectedRecent = Boolean(selected?.items[0].exposure?.recent);
      // Keep each server-ranked queue intact; compare exposure and shares only.
      if (
        !selected ||
        (selectedRecent && !recent) ||
        (selectedRecent === recent &&
          pool.taken / pool.quota < selected.taken / selected.quota)
      )
        selected = pool;
    }
    if (!selected) break;
    const item = selected.items.shift()!;
    selected.taken += 1;
    result.push({ kind: "article", item, section: selected.section });
  }
  const selectedIds = new Set(
    result.map((entry) =>
      entry.kind === "project"
        ? entry.project.article_id
        : entry.item.article.id,
    ),
  );
  for (const project of projects.slice(2)) {
    if (result.length >= 12) break;
    if (!selectedIds.has(project.article_id)) {
      selectedIds.add(project.article_id);
      result.push({ kind: "project", project });
    }
  }
  return result;
}

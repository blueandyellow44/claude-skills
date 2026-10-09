// Writes stops.json and route.json for one sample walk, plus the story quote
// (`wallyStory`) of a named stop, read from the app's own data/routes.ts. Run from the repo root:
//   npx tsx <skill>/scripts/export_walk.mts <walk-slug> "<quote stop name>" <workdir>
import { writeFileSync } from "node:fs";
import { join } from "node:path";
const { routes } = await import(join(process.cwd(), "data/routes.ts"));
const [slug, quoteStop, work] = process.argv.slice(2);
const all = routes as any[];
const r = all.find((x) => x.slug === slug);
if (!r) throw new Error(`no walk ${slug}; slugs: ${all.map((x) => x.slug).join(", ")}`);
const q = all.flatMap((x) => x.stops).find((s: any) => s.name === quoteStop && s.wallyStory);
if (!q) throw new Error(`no stop named "${quoteStop}" with a story quote (wallyStory)`);
writeFileSync(join(work, "stops.json"), JSON.stringify({
  title: r.title, color: r.colorHex, distance: r.distance, duration: r.duration,
  description: r.description, quote: q.wallyStory.split("\n\n")[0],
  stops: r.stops.map((s: any) => ({ id: s.id, name: s.name, kind: s.kind, history: s.history, wallyStory: s.wallyStory || "" })),
}));
writeFileSync(join(work, "route.json"), JSON.stringify({ path: r.path, stops: r.stops.map((s: any) => ({ id: s.id, name: s.name, gps: s.gps })) }));
console.log("exported", slug, "quote from", quoteStop);

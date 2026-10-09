---
name: address-index
description: "Refresh or repair the SF City Walks / wallywalks.app address autocomplete: the D1 table of every San Francisco address (DataSF Enterprise Addressing System), its key normalization, the local and remote loads, and the /api/geocode tiers. Use when the owner says an address does not complete, a new street or building is missing, 'autofill', or when DataSF has new rows. Built 2026-10-06 when Google's terms took Places off a non-Google map. Never Google Places."
allowed-tools:
  - Bash
  - Read
  - Edit
---

# address-index

## Goal

"68 mac" completes to "68 Macondray Ln" from our own table, for everyone, with no key and nobody else's server in the path. The ruling (2026-10-06): no Google branding, keep the current setup, better autofill for all SF addresses.

## Parts

- `scripts/addresses/build-sf-addresses.mjs` (`npm run addresses:build`): pulls `https://data.sf.gov/resource/ramy-di5m.json` in 50k pages (about 390k unit rows, cached in `.tmp/addresses/`; `--from-cache` reuses), collapses to base addresses (about 224k), writes `data/addresses/sf-addresses.sql` (gitignored, about 25 MB) and the committed `manifest.json` (counts, pulled-at).
- `lib/addressKey.ts`: ONE normalizer for both sides. Key = "<number> <street words, trailing type dropped>"; `skey` = street words alone; `nkey` = the city's landmark name. `parseQuery` turns what a person typed into the same shape. If the key rule changes, the table must be rebuilt AND the cache letter in `/geocode` bumped.
- `migrations/0007_sf_addresses.sql`, `db/schema.ts` `sfAddresses`.
- `lib/addressSearch.ts`: tiers in `/geocode`: number present → addresses by key prefix (a typed partial street type is forgiven by dropping the last word); no number → known places (`data/sfPlaces.ts`, `boardLandmarks`, `landmarks`) by name, then the city's named buildings, then streets grouped with a midpoint "(street)". Fewer than 3 results → Nominatim appended. Cache key `geocode:l:<q>`; change the letter when behavior changes.
- Loads: local runtime loads the SQL after migrations on every start (`scripts/local-runtime.mjs loadLocalAddresses`, about 10 s). Remote: `npx wrangler d1 execute wallywalks-app-db --remote --file data/addresses/sf-addresses.sql` with `wrangler.wallywalks-app.toml` copied over `wrangler.toml` and restored after (the file begins with DELETE, so a reload replaces the table whole; about 25 s).

## Refresh

1. `npm run addresses:build` and read the manifest's `baseAddresses` against the last one (224,269 on 2026-10-06; a drop of more than a few percent is a parse problem, not the city shrinking).
2. `npm run test:api` (the `addresses.test.ts` table covers the awkward streets: "Dr Carlton B Goodlett", "Avenue of the Palms", "22nd", "O'Farrell", "1200-1210").
3. Local: restart the runtime; curl `/api/geocode?q=68%20mac`.
4. Remote, on the owner's word (it is the shared production database): the d1 execute above, then `SELECT count(*)` and a curl against production.

## Rules

1. Google Places, Places UI Kit, Routes: never; the terms (14.2, 19.2) forbid their results on this map, and the ruling is no Google branding.
2. The remote load is a production change; it waits for the owner's word like a migration.
3. A query that fails is a test case first (`tests/api/addresses.test.ts`), a fix second.
4. When the owner rules out something this skill does, add it here in the same turn.

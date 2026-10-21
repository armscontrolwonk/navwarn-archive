# Optional map layers

The map shows these point layers when the files exist, and skips them otherwise.

| file | layer | properties used |
|---|---|---|
| `launch-sites.geojson` | 🚀 Launch sites | `name`, `country`, `code` |
| `nuclear-sites.geojson` | ☢️ Nuclear sites | `name`, `country`, `type` |

Each file is a GeoJSON FeatureCollection of Point features. Only add data you have the right to
publish: everything in this repository is public.

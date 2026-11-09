# topospine web app

Browser viewer for the topological spines exported by `../pipeline`.

```bash
cd web
npm install                 # Node 20+
npm test                    # core unit tests (no browser needed)
npm run sync-data           # copy ../pipeline/out/* into public/data and write index.json
npm run dev                 # http://localhost:5173  (?dataset=ring2d opens a given dataset)
npm run build               # static site in dist/ (works from any sub-path, e.g. GitHub Pages)
```

Workflow: export with the pipeline (`python -m topospine.cli configs/ring2d.yaml`), run
`npm run sync-data`, reload the page.

Controls: drag to pan, wheel to zoom, double-click to fit. In the plot, drag the blue line
(noise threshold) or the red line (variation threshold; drag to the right edge for ∞);
focus the plot and use ← → (shift for bigger steps), `l`/`h` to pick a line.

Layout (Model-View-Presenter): `src/core` is pure TypeScript (tested), `model/` holds state
and rules, `presenters/` map state to view models, `views/` draw them (`render/` owns GPU
resources), `services/` fetch data, and `main.ts` wires everything. See
`../docs/ARCHITECTURE.md`.

# Web-based exploration of extremum graphs using topological spines

E0 271 course project (Yashi, Priyank). Implements Correa, Lindstrom & Bremer,
*Topological Spines* (IEEE TVCG 2011).

```
pipeline/   Python: extremum graphs (steepest ascent / TTK), Algorithm 1, export
web/        TypeScript + Three.js: the spine in the browser
docs/       paper map, deviations, milestone notes, figures
```

Quick start:

```bash
cd pipeline && pip install -e ".[dev,viz]" && pytest -m "not slow"
python -m topospine.cli configs/ring2d.yaml
cd ../web && npm install && npm test && npm run sync-data && npm run dev
```

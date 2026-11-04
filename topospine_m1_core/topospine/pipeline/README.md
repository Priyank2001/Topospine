# topospine pipeline

Offline computation of extremum graphs (Correa et al. 2011) for the web-based topological
spine viewer.

## Setup

```bash
conda activate topospine          # or any Python >= 3.10 environment
cd pipeline
pip install -e ".[dev,viz]"       # add ,vtk for .vti input outside the TTK env
pytest -m "not slow"              # fast suite
pytest                            # everything (TTK test skips unless TTK is importable)
```

## Run

```bash
python -m topospine.cli configs/gauss2d.yaml --preview
python -m topospine.cli configs/ring2d.yaml --preview --p-lo 0.05 --p-hi 0.9 --saturation cancel
python -m topospine.cli configs/ackley2d.yaml --preview --p-lo 0.05
python -m topospine.cli configs/gauss3d.yaml          # 3-D, for the browser
python -m topospine.cli configs/gauss3d_ttk.yaml      # same volume through TTK (TTK env only)

# Swap one block of extraction from the command line (TTK env for `ttk`):
python -m topospine.cli configs/gauss3d_ttk.yaml --saddles ttk     # -> out/gauss3d_ttk_ttk-ttk
```

Extraction is two blocks: **regions** (`ascent` = ours, `ttk`) and **saddles** (`boundary` =
ours, `ttk`; TTK saddles need TTK regions). In a config, either name a preset
(`source: {type: native}` = ascent+boundary, `{type: ttk}` = ttk+boundary) or the blocks:
`source: {regions: ttk, saddles: ttk, connectivity: 26}`. `--regions` / `--saddles` override
the config and add a `_<regions>-<saddles>` suffix to the output folder (not to `--out`).
`graph.json` records what ran under `dataset.source` and `dataset.extraction`.

Outputs go to `pipeline/out/<name>/` (graph.json, labels.bin, regions.bin, field.bin or
points.bin, preview.png). The format is described in `schema/spine.schema.json`.

## Layout

```
src/topospine/
  core/        pure NumPy: datasets, neighbourhoods, gradient flow, Algorithm 1, Eqs. 1-3, histograms
  io/          readers, synthetic data, exporter
  sources/     native (ours) and TTK backends behind one protocol
  viz/         2-D preview figure
  config.py run.py cli.py
configs/       one YAML per dataset
schema/        JSON Schema of graph.json (shared with the web app)
```

See `../docs/M1_CORE_NOTES.md` for what each file does and why.

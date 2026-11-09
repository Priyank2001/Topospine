# Topospine

Project code lives in `topospine_m1_core/topospine/` (`pipeline/` Python, `web/` TypeScript, `docs/`).

- Before any code change, use the `topospine-dev` skill (`.claude/skills/topospine-dev/`) and read `topospine_m1_core/topospine/docs/ARCHITECTURE.md`.
- Workflow (phases, one file per turn, stop for approval) follows the `graphics-project` skill. On architecture, `topospine-dev` wins.
- Web app: Model–View–Presenter. Views are passive. Presenters have no DOM. Each piece of state has one owning model and changes only through named methods. Derived data is computed, never stored.
- OOP + SOLID throughout; new behaviour plugs in through interfaces and registries rather than by editing `if/else` chains.
- Tests go in the same change: `cd topospine_m1_core/topospine/web && npm test`, `cd topospine_m1_core/topospine/pipeline && pytest -m "not slow"`.
- Every new component, state field or extension point updates `docs/ARCHITECTURE.md` in the same change.

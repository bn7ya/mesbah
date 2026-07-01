# feature: projects (frontend)

`ProjectsPage` — landing page: grid of project glass-cards + a **multi-step
"new project" wizard** (one `p-dialog`, driven by a `step` signal).

- Loads `api.listProjects()`, `api.featuredModels()` (live from the HF API),
  `api.localModels()`, `api.system()` (for the VRAM slider max + default model).
- Step 0 picks the **kind**:
  - **fine-tune** → model **search box** (`api.searchModels`) + a featured grid
    (live, local models flagged) + custom repo; one step. Selecting a model calls
    `api.inspectModel` (context length + validation) and `api.downloadStatus` —
    if the model isn't local an inline warning offers a "تنزيل الآن" button with a
    progress bar (download continues globally). Default pick: first locally
    downloaded featured model → first featured → `SystemInfo.default_base_model`.
  - **scratch** → four steps:
    1. name + **architecture** (family, layers, hidden, heads, vocab, context;
       experts/experts-per-token when MoE) with a **live feasibility readout**
       from `api.estimateArchitecture` (params, verdict, loud warnings).
    2. **embedding**: new (random, trainable) vs pretrained — the latter searches
       models (`api.searchModels`) and validates dims via `api.inspectModel`,
       adopting the source `hidden_size`/`vocab`.
    3. **corpus**: `api.searchDatasets` + `api.datasetColumns` to pick a text field.
    4. **GPU paged training**: `paged_training` + `gpu_budget_gb` slider (max =
       SystemInfo VRAM) + `cpu_offload_gb`, with the compute-bound warning.
  - Create assembles the `ArchitectureSpec` + `default_train_config` and calls
    `api.createProject({ kind:'scratch', architecture, default_train_config })`.
- Cards show a `fine-tune`/`from scratch` tag from `Project.kind`.

Edit here to change the wizard steps, the architecture knobs, or the create flow.

<p align="center">
  <img src="media/gui-dr.png" alt="GUI-DR Banner" width="640">
</p>

# 🩺 GUI-DR: GUI Domain-Randomization for generating diagnostic GUI grounding evaluation data

Domain randomization for GUI grounding evaluation: generate perturbed web screenshots and step-level instructions from [Mind2Web](https://mind2web.github.io/) MHTML archives.

[**Blog**](https://fig.ai/blog/gui-perturbed) · [**Data**](https://huggingface.co/datasets/figai/GUI-Perturbed) · **Result Viewer** *(coming soon)*

---

## 📢 Updates

- **2025-03:** Initial release of [GUI-Perturbed](https://huggingface.co/datasets/figai/GUI-Perturbed), technical report, and data generation pipeline.

---

## 💾 Installation

**Requirements:** Python ≥ 3.11. The repo includes a [.python-version](.python-version) file (3.11) so [uv](https://docs.astral.sh/uv/) and [pyenv](https://github.com/pyenv/pyenv) use the right version. Mind2Web (or compatible) data must live under `mm_mind2web/`—see [Mind2Web](https://mind2web.github.io/) for acquisition.

We recommend using a **virtual environment** so dependencies stay isolated. You can use **uv** (faster, uses [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock)) or **pip + venv**.

### Option A: uv (recommended)

[Install uv](https://docs.astral.sh/uv/getting-started/installation/), then from the repo root:

```bash
git clone https://github.com/fig-ai/WebDomainRandomizer
cd WebDomainRandomizer

# Create .venv and install dependencies from pyproject.toml + uv.lock
uv sync

# Install Playwright browsers (required for the pipeline)
uv run playwright install
```

uv creates a `.venv` in the project and installs dependencies there. You can run the pipeline **without activating** the venv by prefixing with `uv run`:

```bash
uv run python src/main.py --split test_task
```

To activate the venv yourself: `source .venv/bin/activate` (Unix) or `.venv\Scripts\activate` (Windows), then `python src/main.py ...`.

### Option B: pip + venv

From the repo root:

```bash
git clone https://github.com/fig-ai/WebDomainRandomizer
cd WebDomainRandomizer

python3.11 -m venv .venv
source .venv/bin/activate

pip install -e .

# Install Playwright browsers (required for the pipeline)
playwright install
```

Then run the pipeline from the repo root **with the venv activated**:

```bash
python src/main.py --split test_task
```

### After installing (all options)

1. **Data directory:** The directory `mm_mind2web/` is gitignored. Create it at the repo root and add Mind2Web data in this layout:

   - `mm_mind2web/data/<split>-*.parquet`
   - `mm_mind2web/task/<task_uid>/processed/dom_content.json`
   - `mm_mind2web/task/<task_uid>/processed/snapshots/*.mhtml`
   Download the following two resources and organize them under `mm_mind2web/` at the root of your project:

   - **Parquet files (mm_mind2web):** Download the `mm_mind2web` parquet files from the [Multimodal-Mind2Web dataset page](https://huggingface.co/datasets/osunlp/Multimodal-Mind2Web) on Hugging Face. Put them in `mm_mind2web/data/` (e.g. `train-*.parquet`, `test_task-*.parquet`, etc.).
   - **MHTML (raw dump):** Download the Mind2Web raw dump (task folders with `processed/dom_content.json` and `processed/snapshots/*.mhtml`) following the [Mind2Web Repo README instructions](https://github.com/OSU-NLP-Group/Mind2Web?tab=readme-ov-file#raw-dump-with-full-traces-and-snapshots). Place or symlink the task trees so each task lives at `mm_mind2web/task/<task_uid>/` with `processed/dom_content.json` and `processed/snapshots/*.mhtml` inside it. This repo includes [scripts/globus_mind2web_downloader.sh](scripts/globus_mind2web_downloader.sh) to transfer the raw dump via Globus once you have a local endpoint and `.env` configured.

   The parquet files reference tasks by `task_uid`; the pipeline loads the corresponding MHTML from `mm_mind2web/task/<task_uid>/`, so the two sources must match (same task set and layout).

2. **(Optional)** For debug logging or scripts that use Globus/API keys, copy [.env.example](.env.example) to `.env` and set any variables you need.

---

## 🚀 Quick Start

Run the pipeline on the `test_task` split with the **Style** variant (default).

With **uv** (no need to activate the venv):

```bash
uv run python src/main.py --split test_task
```

With **pip/venv**, ensure the virtual environment is [activated](#option-b-pip--venv), then:

```bash
python src/main.py --split test_task
```

You should see tasks being processed; outputs are written to `outputs/run_<timestamp>_test_task/<task_uid>/` with `screenshots/` and `trajectory.json`. To run other variants or splits, see [Generating data](#-generating-data) below.

---

## 🧪 Generating data

One run produces one variant. Choose flags to match the variant you want. Run from the **repo root** with the venv active (pip) or prefix with `uv run` (uv).

### By variant

```bash
# Original (no perturbations)
python src/main.py --split test_task --enable_zoom false --enable_dense_info false --enable_style_variants false

# Precision (viewport zoom 0.7×)
python src/main.py --split test_task --enable_zoom true --zoom_level 0.7 --enable_dense_info false --enable_style_variants false

# Style (colors, fonts, restyling) — default
python src/main.py --split test_task --enable_style_variants true --enable_zoom false --enable_dense_info false

# Text Shrink (reduced font size)
python src/main.py --split test_task --enable_dense_info true --enable_style_variants false --enable_zoom false
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--split`, `-s` | `train` | Split: `train`, `test_domain`, `test_task`, `test_website`. |
| `--enable_zoom` | `False` | Enable viewport zoom (Precision). |
| `--zoom_level` | `0.7` | Zoom level: `0.7`, `0.5`, or `0.3`. |
| `--enable_dense_info` | `False` | Enable text shrink. |
| `--enable_style_variants` | `True` | Enable style randomization. |

### Output

`outputs/run_<timestamp>_<split>/<task_uid>/` contains `screenshots/` and `trajectory.json`. Use one run per variant when building evaluation data or downstream tooling.

### Pipeline overview

**Input:** Parquet files for the split, plus per-task `dom_content.json` and MHTML snapshots in `mm_mind2web/`.

**Flow:** Load parquet → for each task, load MHTML snapshots in order → per step: optionally inject UI modifications (style / zoom / text shrink) → resolve target element from parquet → capture screenshot and bbox → write `trajectory.json` and screenshots.

```mermaid
flowchart TB
  subgraph input [Input]
    Parquet[parquet files]
    MHTML[MHTML snapshots]
  end
  subgraph pipeline [Pipeline]
    ActionProc[action_processor]
    MHTMLProc[MHTMLProcessor]
    Inject[inject UI mods]
    Locate[locate element]
    Screenshot[screenshot + bbox]
  end
  subgraph output [Output]
    Trajectory[trajectory.json]
    Screens[screenshots/]
  end
  Parquet --> ActionProc
  MHTML --> ActionProc
  ActionProc --> MHTMLProc
  MHTMLProc --> Inject
  Inject --> Locate
  Locate --> Screenshot
  Screenshot --> Trajectory
  Screenshot --> Screens
```

**Perturbations**

| Variant | Config | Implementation |
|---------|--------|-----------------|
| **Original** | All off | No injection. |
| **Style** | `enable_style_variants=True` | [randomization](src/ui/randomization.py), [generator](src/ui/generator.py), [templates](src/ui/templates.py). |
| **Precision** | `enable_zoom=True`, `zoom_level` ∈ {0.7, 0.5, 0.3} | [zoom](src/ui/zoom.py). |
| **Text Shrink** | `enable_dense_info=True` | [dense_info](src/ui/dense_info.py). |

Instructions are generated per step from parquet `target_action_reprs` via [generate_step_instruction](src/utils/helpers.py). Config: [config](src/ui/config.py); injection: [injection](src/ui/injection.py).

---

## Data & resources

| Resource | Description |
|----------|-------------|
| **[Hugging Face: GUI-Perturbed](https://huggingface.co/datasets/figai/GUI-Perturbed)** | Released evaluation data (screenshots, instructions, ground-truth bboxes). |
| **Hugging Face Space: Data viewer** | Interactive viewer for original vs perturbed samples. *Planned; link will be added here and on the dataset card.* |

**Dataset summary**

| Aspect | Description |
|--------|-------------|
| **Source** | Mind2Web MHTML archives (real web pages, DOM preserved). |
| **Visual variants** | **Original**, **Style**, **Precision** (zoom 0.7×/0.5×/0.3×), **Text Shrink**. ~390 screens per variant per run (split-dependent). |
| **Schema** | `visual_variant`, `instruction_type`, `task_id`, `step_index`, `instruction`, `gt_bbox`, `screenshot`. See the [dataset card](https://huggingface.co/datasets/figai/GUI-Perturbed). |
| **Instructions** | **Direct** (from `target_action_reprs`); **relational** (in released schema). |

Use **this repo** to reproduce or extend the data; use the **Hugging Face dataset** for evaluation.

---

## Evaluation

To evaluate models on GUI-Perturbed, download the [Hugging Face dataset](https://huggingface.co/datasets/figai/GUI-Perturbed). The evaluation setup and results will be included in the upcoming **Blog Part 2**; The training experiments will be included in **Part 3**. Blog Part 1 (dataset & methodology): [fig.ai/blog/gui-perturbed](https://fig.ai/blog/gui-perturbed).

---

## Limitations

- **Perturbation realism** — We prioritize diagnostic coverage over photorealism; some variants may look synthetic but still reveal reliance on color, position, or layout.
- **Instruction diversity** — The pipeline produces direct referring expressions; relational phrasings appear in the released dataset; broader natural-language diversity is future work.
- **Web only** — Desktop, mobile, and cross-application flows are out of scope.

---

## ❓ FAQ

### Where do I get the Mind2Web data?

See the [Mind2Web project](https://mind2web.github.io/) for data access. Place it under `mm_mind2web/` with the structure described in [Installation](#-installation).

### Where is the released GUI-Perturbed dataset?

On Hugging Face: [figai/GUI-Perturbed](https://huggingface.co/datasets/figai/GUI-Perturbed). Use it for diagnostic evaluation; use this repo to generate more variants or extend the perturbation methods.

---

## Contributing

We welcome contributions: new perturbation types in `src/ui/`, bug reports, and improvements. Open an issue or pull request. If you use the dataset or this code in research, please cite the dataset and/or blog (see below).

---

## 📄 Citation

If you find GUI-Perturbed or this pipeline useful, please consider citing the dataset and/or the blog series.

```bibtex
@dataset{gui_perturbed_2026,
  title   = {GUI-Perturbed: A Domain-Randomized Dataset for GUI Grounding},
  author  = {[AUTHORS]},
  year    = {2026},
  url     = {https://huggingface.co/datasets/figai/GUI-Perturbed},
  note    = {Built on Mind2Web (Deng et al., 2023)}
}

@software{gui_dr_code_2026,
  title   = {WebDomainRandomizer: GUI Domain-Randomization for GUI Grounding Evaluation},
  author  = {[AUTHORS]},
  year    = {2026},
  url     = {https://github.com/fig-ai/WebDomainRandomizer},
  note    = {Data generation pipeline for GUI-Perturbed}
}

@online{gui_perturbed_blog_2026,
  title   = {GUI-Perturbed: A Domain Randomization Dataset for GUI Grounding},
  author  = {[AUTHORS]},
  year    = {2026},
  url     = {[LINK]},
  note    = {Part 1: Dataset \& methodology}
}
```
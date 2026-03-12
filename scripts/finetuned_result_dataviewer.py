import base64
import io
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast

import sys
import time

print("[result_viewer] MODULE LOADED", file=sys.stderr, flush=True)

# Load .env from repo root or script dir so HF_IMAGES_LOCAL_PATH is set when running e.g. streamlit run
def _load_dotenv():
    for base in (Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent):
        env_file = base / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    key = k.strip()
                    val = v.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            break


_load_dotenv()

# Path to local dataset (HF_IMAGES_LOCAL_PATH = where HF CLI downloaded it, or save_to_disk output).
HF_IMAGES_LOCAL_PATH = os.environ.get("HF_IMAGES_LOCAL_PATH", "").strip()

TECHNICAL_REPORT_1_LINK = "https://blog.fig.inc/training-on-gui-perturbed-why-more-data-isnt-enough"
CODE_LINK = "https://github.com/ManifoldRG/GUI-DR"
DATA_LINK = "https://huggingface.co/datasets/figai/GUI-Perturbed"
FIG_LINK = "https://fig.inc/"
MANIFOLDRG_LINK = "https://www.manifoldrg.com/"

# Media (logos): try script dir then repo root so it works from scripts/ or src/ (e.g. HF Space)
_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent
MEDIA_DIR = (_script_dir / "media") if (_script_dir / "media").exists() else (_repo_root / "media")
PERTURBATION_VARIANTS = ["precision", "style", "text_shrink"]


def _logo_data_uri(filename):
    """Return data URI for a logo under media/ for use in HTML img src."""
    path = MEDIA_DIR / filename
    if not path.exists():
        path = _repo_root / "media" / filename
    if not path.exists():
        return None
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    suffix = path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}.get(suffix.lstrip("."), "image/png")
    return f"data:{mime};base64,{b64}"


def _badge_icon_html(kind, fig_data_uri):
    """Return inline HTML for a small badge icon. kind: 'fig' | 'github' | 'huggingface'."""
    style = "width:14px;height:14px;margin-right:5px;flex-shrink:0;vertical-align:middle;"
    try:
        if kind == "fig" and fig_data_uri:
            return f'<img src="{fig_data_uri}" alt="" style="{style}object-fit:contain;">'
        if kind == "github":
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="' + style + '">'
                '<path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>'
                "</svg>"
            )
            return svg
        if kind == "huggingface":
            hf_path = (
                "M12.025 1.13c-5.77 0-10.449 4.647-10.449 10.378 0 1.112.178 2.181.503 3.185.064-.222.203-.444.416-.577a.96.96 0 0 1 .524-.15c.293 0 .584.124.84.284.278.173.48.408.71.694.226.282.458.611.684.951v-.014c.017-.324.106-.622.264-.874s.403-.487.762-.543c.3-.047.596.06.787.203s.31.313.4.467c.15.257.212.468.233.542.01.026.653 1.552 1.657 2.54.616.605 1.01 1.223 1.082 1.912.055.537-.096 1.059-.38 1.572.637.121 1.294.187 1.967.187.657 0 1.298-.063 1.921-.178-.287-.517-.44-1.041-.384-1.581.07-.69.465-1.307 1.081-1.913 1.004-.987 1.647-2.513 1.657-2.539.021-.074.083-.285.233-.542.09-.154.208-.323.4-.467a1.08 1.08 0 0 1 .787-.203c.359.056.604.29.762.543s.247.55.265.874v.015c.225-.34.457-.67.683-.952.23-.286.432-.52.71-.694.257-.16.547-.284.84-.285a.97.97 0 0 1 .524.151c.228.143.373.388.43.625l.006.04a10.3 10.3 0 0 0 .534-3.273c0-5.731-4.678-10.378-10.449-10.378M8.327 6.583a1.5 1.5 0 0 1 .713.174 1.487 1.487 0 0 1 .617 2.013c-.183.343-.762-.214-1.102-.094-.38.134-.532.914-.917.71a1.487 1.487 0 0 1 .69-2.803m7.486 0a1.487 1.487 0 0 1 .689 2.803c-.385.204-.536-.576-.916-.71-.34-.12-.92.437-1.103.094a1.487 1.487 0 0 1 .617-2.013 1.5 1.5 0 0 1 .713-.174m-10.68 1.55a.96.96 0 1 1 0 1.921.96.96 0 0 1 0-1.92m13.838 0a.96.96 0 1 1 0 1.92.96.96 0 0 1 0-1.92M8.489 11.458c.588.01 1.965 1.157 3.572 1.164 1.607-.007 2.984-1.155 3.572-1.164.196-.003.305.12.305.454 0 .886-.424 2.328-1.563 3.202-.22-.756-1.396-1.366-1.63-1.32q-.011.001-.02.006l-.044.026-.01.008-.03.024q-.018.017-.035.036l-.032.04a1 1 0 0 0-.058.09l-.014.025q-.049.088-.11.19a1 1 0 0 1-.083.116 1.2 1.2 0 0 1-.173.18q-.035.029-.075.058a1.3 1.3 0 0 1-.251-.243 1 1 0 0 1-.076-.107c-.124-.193-.177-.363-.337-.444-.034-.016-.104-.008-.2.022q-.094.03-.216.087-.06.028-.125.063l-.13.074q-.067.04-.136.086a3 3 0 0 0-.135.096 3 3 0 0 0-.26.219 2 2 0 0 0-.12.121 2 2 0 0 0-.106.128l-.002.002a2 2 0 0 0-.09.132l-.001.001a1.2 1.2 0 0 0-.105.212q-.013.036-.024.073c-1.139-.875-1.563-2.317-1.563-3.203 0-.334.109-.457.305-.454m.836 10.354c.824-1.19.766-2.082-.365-3.194-1.13-1.112-1.789-2.738-1.789-2.738s-.246-.945-.806-.858-.97 1.499.202 2.362c1.173.864-.233 1.45-.685.64-.45-.812-1.683-2.896-2.322-3.295s-1.089-.175-.938.647 2.822 2.813 2.562 3.244-1.176-.506-1.176-.506-2.866-2.567-3.49-1.898.473 1.23 2.037 2.16c1.564.932 1.686 1.178 1.464 1.53s-3.675-2.511-4-1.297c-.323 1.214 3.524 1.567 3.287 2.405-.238.839-2.71-1.587-3.216-.642-.506.946 3.49 2.056 3.522 2.064 1.29.33 4.568 1.028 5.713-.624m5.349 0c-.824-1.19-.766-2.082.365-3.194 1.13-1.112 1.789-2.738 1.789-2.738s.246-.945.806-.858.97 1.499-.202 2.362c-1.173.864.233 1.45.685.64.451-.812 1.683-2.896 2.322-3.295s1.089-.175.938.647-2.822 2.813-2.562 3.244 1.176-.506 1.176-.506 2.866-2.567 3.49-1.898-.473 1.23-2.037 2.16c-1.564.932-1.686 1.178-1.464 1.53s3.675-2.511 4-1.297c.323 1.214-3.524 1.567-3.287 2.405.238.839 2.71-1.587 3.216-.642.506.946-3.49 2.056-3.522 2.064-1.29.33-4.568 1.028-5.713-.624"
            )
            svg_str = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#FFD21E">'
                f'<path d="{hf_path}"/>'
                "</svg>"
            )
            b64 = base64.b64encode(svg_str.encode("utf-8")).decode("ascii")
            data_uri = f"data:image/svg+xml;base64,{b64}"
            return f'<img src="{data_uri}" alt="Hugging Face" style="{style}object-fit:contain;">'
    except Exception:
        pass
    return ""


st.set_page_config(page_title="GUI Perturbation Evaluation Viewer", page_icon="🔬", layout="wide")

# Theme and layout styles; system fonts only (no external CDN requests)
st.markdown("""
<style>
    /* Theme-aware colors: light and dark (macOS system preference) */
    :root {
        --gui-viewer-text: #23283c;
        --gui-viewer-bg: #f2f2f2;
        --gui-viewer-muted: rgb(128, 128, 128);
        --gui-viewer-heading: #23283c;
        --gui-viewer-badge-bg: rgba(35, 40, 60, 0.06);
        --gui-viewer-badge-border: rgba(35, 40, 60, 0.18);
        --gui-viewer-badge-bg-hover: rgba(35, 40, 60, 0.12);
        --gui-viewer-badge-border-hover: rgba(35, 40, 60, 0.3);
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --gui-viewer-text: #e4e4e7;
            --gui-viewer-bg: #1e1e1e;
            --gui-viewer-muted: #a1a1aa;
            --gui-viewer-heading: #f4f4f5;
            --gui-viewer-badge-bg: rgba(228, 228, 231, 0.08);
            --gui-viewer-badge-border: rgba(228, 228, 231, 0.2);
            --gui-viewer-badge-bg-hover: rgba(228, 228, 231, 0.14);
            --gui-viewer-badge-border-hover: rgba(228, 228, 231, 0.35);
        }
    }
    /* Base typography and background; theme-aware */
    body, .main, [data-testid="stAppViewContainer"] {
        color: var(--gui-viewer-text) !important;
        line-height: 1.5em !important;
        font-weight: 400 !important;
        font-size: 1.25rem !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
        background-color: var(--gui-viewer-bg) !important;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        color: var(--gui-viewer-text) !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
        background-color: var(--gui-viewer-bg) !important;
    }
    /* On full-screen desktop (>=1200px), constrain non-image sections to center.
       Images stay full width naturally. Each constrained section uses
       st.container(key="narrow_...") so CSS can target them. */
    @media (min-width: 1200px) {
        [class*="st-key-narrow_"] {
            max-width: 800px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
    }
    /* Prevent main title from being cut off when scrolled to top */
    [data-testid="stAppViewContainer"] {
        padding-top: 0.5rem;
    }
    .block-container > div:first-child {
        margin-top: 0.25rem;
    }
    /* Constrain comparison images so they fit in view */
    div[data-testid="column"] img {
        max-width: 100% !important;
        height: auto !important;
        max-height: 70vh !important;
        object-fit: contain !important;
    }
    /* Tighten image comparison spacing */
    .st-key-image_comparison [data-testid="stHtml"] {
        margin-bottom: 0 !important;
    }
    section[data-testid="stSidebar"] {
        background-color: var(--gui-viewer-bg) !important;
        color: var(--gui-viewer-text) !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    }
    /* Keep header visible so sidebar toggle button is shown */
    header[data-testid="stHeader"] {
        background-color: var(--gui-viewer-bg) !important;
    }
    /* Expander titles */
    [data-testid="stExpander"] summary {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
    }
    [data-testid="stExpander"] summary > span:first-child,
    [data-testid="stExpander"] summary [class*="icon"] {
        font-family: system-ui, sans-serif !important;
    }
    /* Header/sidebar toggle: icon font for the button icon only */
    header [role="button"],
    header [role="button"] *,
    header button,
    header button *,
    button[data-testid="baseButton-header"],
    button[data-testid="baseButton-header"] * {
        font-family: system-ui, sans-serif !important;
    }
    /* Text content */
    .block-container > p, .block-container > div .stMarkdown p,
    .stMarkdown p, .stCaption,
    label[data-testid="stWidgetLabel"] {
        color: var(--gui-viewer-text) !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    }
    /* Headings (h1-h6) */
    .block-container h1, .block-container h2, .block-container h3,
    .block-container h4, .block-container h5, .block-container h6,
    [data-testid="stAppViewContainer"] h1, [data-testid="stAppViewContainer"] h2,
    [data-testid="stAppViewContainer"] h3, [data-testid="stAppViewContainer"] h4,
    [data-testid="stAppViewContainer"] h5, [data-testid="stAppViewContainer"] h6 {
        color: var(--gui-viewer-heading) !important;
    }
    /* Sidebar headings and labels */
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p,
    .gui-viewer-muted { color: var(--gui-viewer-muted) !important; }
    .gui-viewer-text { color: var(--gui-viewer-text) !important; }
    .gui-viewer-heading { color: var(--gui-viewer-heading) !important; }
    /* Badge link styles */
    .gui-viewer-badge {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        color: var(--gui-viewer-text) !important;
        background-color: var(--gui-viewer-badge-bg) !important;
        border: 1px solid var(--gui-viewer-badge-border) !important;
        border-radius: 4px !important;
        transition: background-color 0.15s ease, border-color 0.15s ease;
    }
    .gui-viewer-badge:hover {
        background-color: var(--gui-viewer-badge-bg-hover) !important;
        border-color: var(--gui-viewer-badge-border-hover) !important;
        color: var(--gui-viewer-text) !important;
        opacity: 1;
    }
    /* MSE delta colors */
    .gui-viewer-mse-delta-up { color: #dc2626 !important; }
    .gui-viewer-mse-delta-down { color: #16a34a !important; }
    @media (prefers-color-scheme: dark) {
        .gui-viewer-mse-delta-up { color: #f87171 !important; }
        .gui-viewer-mse-delta-down { color: #4ade80 !important; }
    }
    /* Logo dark-mode: invert dark text so it's visible on dark bg */
    @media (prefers-color-scheme: dark) {
        .gui-viewer-logo-dark-invert {
            filter: invert(1) hue-rotate(180deg);
        }
    }
    /* Metrics column: compact text */
    .gui-viewer-metrics-column {
        font-size: 0.9rem !important;
        font-weight: 400 !important;
        line-height: 1.5 !important;
        margin-bottom: 0.25rem !important;
    }
    .gui-viewer-metrics-column .gui-viewer-mse-delta-up,
    .gui-viewer-metrics-column .gui-viewer-mse-delta-down {
        font-weight: 400 !important;
    }
    /* Task instruction bar */
    .gui-viewer-task-instr-bar {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        background-color: rgba(128, 128, 128, 0.12);
        border: 1px solid rgba(128, 128, 128, 0.25);
        color: var(--gui-viewer-text);
        font-size: 1rem;
        line-height: 1.4;
        margin-bottom: 0.5rem;
    }
    @media (prefers-color-scheme: dark) {
        .gui-viewer-task-instr-bar {
            background-color: rgba(255, 255, 255, 0.06);
            border-color: rgba(255, 255, 255, 0.12);
        }
    }
    .gui-viewer-task-instr-bar .instr-label {
        font-weight: 600;
        color: var(--gui-viewer-muted);
        flex-shrink: 0;
    }
    /* Success/failure status badges */
    .gui-viewer-status-success {
        display: inline-block;
        padding: 0.25rem 0.45rem;
        border-radius: 4px;
        background-color: rgba(34, 197, 94, 0.2);
        color: #16a34a;
        font-weight: 700;
        font-size: clamp(0.8rem, 1.5vw, 1rem);
        margin-bottom: 0.35rem;
    }
    .gui-viewer-status-failure {
        display: inline-block;
        padding: 0.25rem 0.45rem;
        border-radius: 4px;
        background-color: rgba(239, 68, 68, 0.2);
        color: #dc2626;
        font-weight: 700;
        font-size: clamp(0.8rem, 1.5vw, 1rem);
        margin-bottom: 0.35rem;
    }
    @media (prefers-color-scheme: dark) {
        .gui-viewer-status-success { color: #4ade80; background-color: rgba(34, 197, 94, 0.25); }
        .gui-viewer-status-failure { color: #f87171; background-color: rgba(239, 68, 68, 0.25); }
    }
    /* Compact header */
    .gui-viewer-compact-header {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.25rem;
        padding: 0.25rem 0 0.5rem 0;
    }
    .gui-viewer-compact-header .header-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
        justify-content: center;
    }
    .gui-viewer-compact-header h2 {
        margin: 0;
        color: var(--gui-viewer-heading);
        font-size: 1.3rem;
        font-weight: 700;
        white-space: nowrap;
    }
    .gui-viewer-compact-header .badges-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        justify-content: center;
    }
    @media (max-width: 600px) {
        .gui-viewer-compact-header h2 {
            font-size: 1rem;
        }
    }
    /* Prediction text in model results */
    .gui-viewer-pred-text {
        max-height: 12rem;
        overflow-y: auto;
        white-space: pre-wrap;
        word-break: break-word;
        font-size: 0.82rem;
        line-height: 1.35;
        padding: 0.35rem;
        border-radius: 4px;
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.15);
        font-family: monospace;
    }
    @media (prefers-color-scheme: dark) {
        .gui-viewer-pred-text {
            background-color: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.1);
        }
    }
    /* Model display checkboxes: compact row */
    .st-key-narrow_model_display [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
    }
    .st-key-narrow_model_display [data-testid="column"] {
        min-width: 0 !important;
    }
    /* Mobile: allow wrapping so checkboxes don't overflow */
    @media (max-width: 768px) {
        .st-key-narrow_model_display [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
    }
    /* Failure mode pills: no word breaking */
    .st-key-failure_mode_pills button {
        white-space: nowrap !important;
    }
    /* Mobile: stack image comparison columns vertically */
    @media (max-width: 768px) {
        .st-key-image_comparison [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        .st-key-image_comparison [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
    }
    /* --- Finetuned viewer extras (not in baseline) --- */
    /* Experiment group radio: allow text wrapping on mobile */
    .st-key-experiment_radio label {
        white-space: normal !important;
    }
    /* Buttons/pills with light backgrounds: ensure dark text for readability */
    .st-key-failure_mode_pills button {
        color: #000 !important;
    }
    .st-key-failure_mode_pills button[aria-checked="true"] {
        color: #e4e4e7 !important;
    }
    /* Dark mode overrides */
    @media (prefers-color-scheme: dark) {
        /* Pills: light bg -> black text */
        .st-key-failure_mode_pills button {
            color: #000 !important;
        }
        .st-key-failure_mode_pills button[aria-checked="true"],
        .st-key-failure_mode_pills button:hover {
            color: #e4e4e7 !important;
        }
        /* Model Results tabs: light text when not hovered */
        .st-key-narrow_results [role="tab"] {
            color: #e4e4e7 !important;
        }
        .st-key-narrow_results [role="tab"][aria-selected="true"] {
            color: #fff !important;
        }
        /* Experiment radio + model checkbox text: readable in dark mode */
        .st-key-narrow_model_display label,
        .st-key-narrow_model_display [data-testid="stMarkdownContainer"] p,
        .st-key-narrow_model_display [data-testid="stMarkdownContainer"] span {
            color: var(--gui-viewer-text) !important;
        }
    }
</style>
""", unsafe_allow_html=True)

def _parse_success(value):
    """Normalize hit_box_accuracy to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def _csv_mtime():
    """Return CSV modification time so cache invalidates when file changes."""
    for base in (_repo_root, _script_dir):
        candidate = base / "data" / "finetuned_results_full.csv"
        if candidate.exists():
            return candidate.stat().st_mtime
    return None


# 39 samples with no images in the HF dataset (marked "Invalid" in baseline analysis)
_INVALID_SAMPLES = {
    ("039969ee-8f9a-4c49-9260-88267339e885", 8),
    ("17a3488c-8b75-4ec6-9899-f32bcec2f808", 4),
    ("18c81087-23fc-4154-8f69-31d1ed10efa4", 0),
    ("18fc60d7-aa69-4c07-9bf1-64543eae52c9", 0),
    ("1c2baca4-8c20-4e04-b6f6-90db4f565a72", 6),
    ("20bc1709-b43e-4da1-a71e-440d8fb93fd3", 7),
    ("23372ead-d829-4e99-8429-1963d4bfe608", 0),
    ("24948950-6ab9-4a90-8aae-bd4f155ace1a", 4),
    ("24bbf21c-e433-46d6-8a3b-896b0015c0e5", 2),
    ("2854bdb8-783d-4ee9-a87c-4de3a5ac0654", 4),
    ("2cc71f04-851c-4a75-8728-a80783984a32", 0),
    ("2cc71f04-851c-4a75-8728-a80783984a32", 3),
    ("349f5f06-acda-4d1c-8569-c97a31c6107c", 6),
    ("369a4134-9710-4868-b6a2-3dc761294c45", 0),
    ("3b0a3ed2-e48c-4e9d-a954-d9cc7730c9fa", 6),
    ("432a58b4-450d-4768-b049-90f6681bc22e", 7),
    ("490dc61c-873d-47b6-9050-369cd18e1253", 7),
    ("5a05fede-f629-4323-a5f7-204d7dbe81cd", 0),
    ("5be47163-4986-47ee-be88-667d9ab73e36", 1),
    ("5c29c805-388d-471a-80e9-ca0fbaf820be", 0),
    ("5c29c805-388d-471a-80e9-ca0fbaf820be", 8),
    ("640e0425-bceb-45ff-ba4d-dbc5b62e31d5", 3),
    ("705c914c-d8f6-4c4b-8aef-94ef40e99e18", 1),
    ("82094208-02a3-46de-a55f-4c48924cb16c", 0),
    ("83e54729-fd0c-40fa-bab3-3005aa83188c", 1),
    ("87e6932d-6e44-426a-9208-bf1a1f542dd1", 2),
    ("89a03889-bbfe-4922-8c70-17b91f956b34", 2),
    ("92a49fdb-d88a-455d-a2b7-86a17b4b5b18", 2),
    ("9ceab2a3-7919-4f15-871a-21638fd93b24", 0),
    ("9ceab2a3-7919-4f15-871a-21638fd93b24", 2),
    ("a5dd5729-415a-4fe2-a840-4935bf9428d4", 2),
    ("afcc3ff5-c043-4787-8608-cb21dab9dc42", 1),
    ("b3f27ec6-dcb2-478a-ad46-e32a9f626ce3", 2),
    ("b47f2eb1-58d1-442d-a4b1-2463db44840f", 1),
    ("c1f584e2-e353-4298-b98b-fb21cbf2c16c", 3),
    ("cc5908a9-263b-4dd2-96ac-405fda7240e9", 0),
    ("d6545454-33e8-4a35-988e-fa6cc0eb5873", 3),
    ("f0e64c18-28ca-4627-b33c-260c998d5cab", 11),
    ("ff1de5de-7801-4187-a064-8e3bef382eda", 3),
}


@st.cache_data
def load_data(_mtime=None):
    """Load and clean data. Tries repo root (HF Space: /app/data/) then script dir."""
    csv_path = None
    for base in (_repo_root, _script_dir):
        candidate = base / "data" / "finetuned_results_full.csv"
        if candidate.exists():
            csv_path = candidate
            break
    if csv_path is None:
        return pd.DataFrame()

    df = pd.read_csv(csv_path, low_memory=False)
    # Filter out invalid samples (no images in HF dataset)
    df = df[~df.apply(lambda r: (str(r["task_id"]), int(r["step_index"])) in _INVALID_SAMPLES, axis=1)]
    df["success"] = pd.to_numeric(df["hit_box_accuracy"], errors="coerce").fillna(0).astype(bool)
    return df


def _debug_csv_paths():
    """Return list of (path_str, exists) for triage when no data found."""
    out = []
    for name, base in [("repo_root", _repo_root), ("script_dir", _script_dir)]:
        p = base / "data" / "finetuned_results_full.csv"
        out.append((f"{name}: {p}", p.exists()))
    out.append((f"__file__ = {__file__}", None))
    return out


def resolve_image_path(row):
    """Get image path for a row - variant-specific patterns then exact path."""
    image_path = row.get('image_path', '')
    if not image_path or pd.isna(image_path):
        return None
    if image_path.startswith('/mnt/'):
        image_path = image_path[5:]
    image_path_obj = Path(image_path)
    image_dir = _script_dir / image_path_obj.parent if not image_path_obj.is_absolute() else image_path_obj.parent
    step_idx = str(row.get('step_index'))
    variant = row.get('variant', '')
    for pattern in [
        f"step_{step_idx}_{variant}_*.png",
        f"step_{step_idx}_*{variant}*.png",
        f"*{variant}*step_{step_idx}*.png",
        f"step_{step_idx}_*.png",
    ]:
        matching = list(image_dir.glob(pattern))
        if matching:
            return matching[0]
    exact = _script_dir / image_path
    if exact.exists():
        return exact
    if HF_IMAGES_LOCAL_PATH:
        base = Path(HF_IMAGES_LOCAL_PATH)
        name = image_path_obj.name
        for candidate in (base / name, base / "images" / name):
            if candidate.exists():
                return candidate
    return None


def _get_local_dataset_path():
    """Return canonical path to local dataset root (snapshot or save_to_disk)."""
    if HF_IMAGES_LOCAL_PATH:
        return str(Path(HF_IMAGES_LOCAL_PATH).resolve())
    if Path("/data").is_dir():
        return "/data/gui_perturbed_subset"
    return str(_repo_root / "data" / "gui_perturbed_subset")


def _row_to_key(row):
    """(task_id, step_index, variant) from CSV row."""
    task_id, step_index, variant = row.get("task_id"), row.get("step_index"), row.get("variant")
    if pd.isna(task_id) or pd.isna(step_index) or pd.isna(variant):
        return None
    try:
        return (str(task_id), int(step_index), str(variant))
    except (TypeError, ValueError):
        return None


@st.cache_data
def _load_local_dataset(path):
    """Build a lazy index from parquet: only read key columns (no images). Returns (parquet_paths, key->(path, row_idx), error_msg)."""
    if not path:
        return None, None, "path is empty"
    base = Path(path).resolve()
    if not base.exists():
        return None, None, f"path does not exist: {base}"
    try:
        import pyarrow.parquet as pq
    except ImportError as e:
        return None, None, f"pyarrow import failed: {e}"
    data_dir = base / "data"
    if data_dir.is_dir():
        parquet_files = sorted(data_dir.glob("*.parquet"))
    else:
        parquet_files = list(base.rglob("*.parquet"))
    if not parquet_files:
        return None, None, f"no parquet files under {base}"
    index = {}
    paths = []
    for pf in parquet_files:
        try:
            t = pq.read_table(pf, columns=["task_id", "step_index", "visual_variant"])
            vcol = "visual_variant"
        except Exception:
            try:
                t = pq.read_table(pf, columns=["task_id", "step_index", "variant"])
                vcol = "variant"
            except Exception:
                continue
        paths.append(str(pf))
        task_ids = t.column("task_id")
        step_indices = t.column("step_index")
        variants = t.column(vcol)
        for i in range(t.num_rows):
            ti, si, v = task_ids[i], step_indices[i], variants[i]
            if ti is None or si is None or v is None:
                continue
            try:
                key = (str(ti.as_py()) if hasattr(ti, "as_py") else str(ti), int(si.as_py()) if hasattr(si, "as_py") else int(si), str(v.as_py()) if hasattr(v, "as_py") else str(v))
            except Exception:
                continue
            index[key] = (str(pf), i)
    if not index:
        return None, None, "no valid rows in parquet files"
    return paths, index, None


def _read_screenshot_from_parquet(file_path, row_idx):
    """Read a single row's screenshot from a parquet file. Returns PIL Image or None."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return None

    def _extract_image(row_val):
        if row_val is None:
            return None
        if hasattr(row_val, "as_py"):
            row_val = row_val.as_py()
        if isinstance(row_val, dict):
            b = row_val.get("bytes")
            if b is not None:
                if hasattr(b, "as_py"):
                    b = b.as_py()
                if not isinstance(b, bytes):
                    b = bytes(b)
                return Image.open(io.BytesIO(b))
        return None

    def _read_single_row(pf, col_name, row_idx):
        offset = 0
        for rg in range(pf.metadata.num_row_groups):
            rg_size = pf.metadata.row_group(rg).num_rows
            if row_idx < offset + rg_size:
                t = pf.read_row_group(rg, columns=[col_name])
                return t.column(col_name)[row_idx - offset]
            offset += rg_size
        return None

    try:
        pf = pq.ParquetFile(file_path)
        if row_idx < 0 or row_idx >= pf.metadata.num_rows:
            return None
        for col_name in ("screenshot", "image"):
            try:
                row_val = _read_single_row(pf, col_name, row_idx)
                img = _extract_image(row_val)
                if img is not None:
                    return img
            except Exception:
                continue
    except Exception:
        pass
    return None


def _ensure_dataset_loaded():
    path = _get_local_dataset_path()
    if "_ds_index" in st.session_state and "_ds_parquet_paths" in st.session_state:
        return
    try:
        result = _load_local_dataset(path)
    except Exception as e:
        print(f"[result_viewer] WARNING: failed to load local dataset: {e}", file=sys.stderr, flush=True)
        return
    if isinstance(result, (list, tuple)) and len(result) >= 2:
        parquet_paths, index = result[0], result[1]
        load_error = result[2] if len(result) > 2 else None
    else:
        parquet_paths, index, load_error = None, None, "unexpected return from _load_local_dataset"
    if parquet_paths is not None and index is not None:
        st.session_state["_ds_parquet_paths"] = parquet_paths
        st.session_state["_ds_index"] = index
        st.session_state["_ds_base_path"] = path


def _pil_from_row(row_data):
    """Convert dataset row's screenshot/image to PIL Image. Handles dict, bytes, PIL, and Arrow types."""
    if row_data is None:
        return None
    if not isinstance(row_data, dict) and hasattr(row_data, "keys"):
        row_data = dict(row_data)
    elif not isinstance(row_data, dict):
        return None
    img = row_data.get("screenshot") or row_data.get("image")
    if img is None:
        return None
    if hasattr(img, "as_py"):
        img = img.as_py()
    if img is None:
        return None
    if isinstance(img, Image.Image):
        return img
    if isinstance(img, bytes):
        return Image.open(io.BytesIO(img))
    if isinstance(img, dict):
        if "bytes" in img and img["bytes"]:
            b = img["bytes"]
            if hasattr(b, "as_py"):
                b = b.as_py()
            try:
                if not isinstance(b, bytes):
                    b = bytes(b)
                return Image.open(io.BytesIO(b))
            except Exception:
                pass
        path_val = img.get("path")
        if path_val and isinstance(path_val, str):
            base = HF_IMAGES_LOCAL_PATH or st.session_state.get("_ds_base_path") or _get_local_dataset_path()
            if base:
                base_path = Path(base).resolve()
                candidate = (base_path / path_val).resolve()
                if candidate.is_relative_to(base_path) and candidate.exists():
                    try:
                        return Image.open(candidate)
                    except Exception:
                        pass
                candidate2 = (base_path / "images" / path_val).resolve()
                if candidate2.is_relative_to(base_path) and candidate2.exists():
                    try:
                        return Image.open(candidate2)
                    except Exception:
                        pass
    if hasattr(img, "__array__"):
        try:
            import numpy as np
            arr = np.asarray(img)
            if arr.dtype == np.uint8 and arr.ndim >= 2:
                return Image.fromarray(arr)
        except Exception:
            pass
    return None


def get_image_for_row(row):
    """PIL for this row: local file first, else from local dataset (lazy single-row read from parquet)."""
    img_path = resolve_image_path(row)
    if img_path and img_path.exists():
        try:
            return Image.open(img_path)
        except Exception:
            pass
    _ensure_dataset_loaded()
    key = _row_to_key(row)
    if key is None:
        return None
    index = st.session_state.get("_ds_index")
    if not index or key not in index:
        return None
    file_path, row_idx = index[key]
    return _read_screenshot_from_parquet(file_path, row_idx)


def format_raw_prediction(raw_pred):
    """Return raw prediction as string for display, or None if missing."""
    return None if pd.isna(raw_pred) else str(raw_pred)

def parse_coords(coord_str):
    """Parse coordinate string like '[553, 86]' to (x, y) or None."""
    if pd.isna(coord_str):
        return None
    try:
        coords = ast.literal_eval(coord_str)
        if isinstance(coords, list) and len(coords) >= 2:
            return (int(coords[0]), int(coords[1]))
    except (ValueError, TypeError, SyntaxError):
        pass
    return None

# Solid cursor colors; semi-transparent so overlapping cursors stay visible
CONTRAST_OUTLINE = (50, 50, 50)
CURSOR_ALPHA = 180
MODEL_STYLES = {
    "baseline": {"color": (255, 165, 0), "label": "Baseline (UI-TARS-1.5)"},
    "all": {"color": (0, 120, 212), "label": "6.5k All"},
    "style": {"color": (16, 185, 129), "label": "6.5k Style"},
    "text_shrink_zoom": {"color": (239, 68, 68), "label": "6.5k Text Shrink"},
    "all_25k_3_epoch": {"color": (147, 51, 234), "label": "25k All"},
    "25k_salesforce_1_epoch": {"color": (234, 179, 8), "label": "25k Salesforce"},
    "25k_perturbed_1_epoch": {"color": (236, 72, 153), "label": "25k Perturbed"},
}


def _model_label(model):
    """Display label for a model key."""
    return MODEL_STYLES.get(model, {"label": model})["label"]

def _arrow_points(scale):
    """Arrow shape with tip at origin, pointing down-right. Returns list of (dx, dy)."""
    s = scale
    return [
        (0, 0),
        (0, 48 * s),
        (12 * s, 36 * s),
        (21 * s, 54 * s),
        (27 * s, 51 * s),
        (18 * s, 33 * s),
        (33 * s, 33 * s),
    ]

def _draw_cursor_arrow(draw, cx, cy, fill_color, scale=1.0, outline_color=None):
    """Draw arrow cursor with tip at (cx, cy)."""
    pts_rel = _arrow_points(scale)
    pts_int = [(int(cx + x), int(cy + y)) for x, y in pts_rel]
    outline = outline_color if outline_color is not None else CONTRAST_OUTLINE
    draw.polygon(pts_int, fill=fill_color, outline=outline, width=max(1, int(2 * scale)))

def draw_model_prediction(draw, coords, model, scale=1.0, alpha=255):
    """Draw a model's prediction as solid arrow cursor."""
    if not coords:
        return
    cx, cy = int(coords[0]), int(coords[1])
    style = MODEL_STYLES.get(model, {'color': (180, 180, 180), 'label': model})
    color = style.get('color', (180, 180, 180))
    fill_rgba = (*color, alpha)
    outline_rgba = (*CONTRAST_OUTLINE, 255)
    _draw_cursor_arrow(draw, cx, cy, fill_rgba, scale, outline_rgba)


def _draw_dashed_rect(draw, x, y, w, h, color, width, dash_length=8, gap_length=8):
    """Draw a dashed rectangle."""
    def draw_dashed_line(p1, p2, c, w):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = (dx**2 + dy**2) ** 0.5
        if dist == 0:
            return
        n = int(dist / (dash_length + gap_length))
        for i in range(n + 1):
            t0 = i * (dash_length + gap_length) / dist
            t1 = min(1.0, (i * (dash_length + gap_length) + dash_length) / dist)
            start = (p1[0] + dx * t0, p1[1] + dy * t0)
            end = (p1[0] + dx * t1, p1[1] + dy * t1)
            draw.line([start, end], fill=c, width=w)

    draw_dashed_line((x, y), (x + w, y), color, width)
    draw_dashed_line((x + w, y), (x + w, y + h), color, width)
    draw_dashed_line((x + w, y + h), (x, y + h), color, width)
    draw_dashed_line((x, y + h), (x, y), color, width)


def annotate_image_multi_model(img, rows_by_model, selected_models, draw_predictions=False):
    """Annotate image with GT bbox. If draw_predictions=True, also draw model cursor predictions."""
    annotated_img = img.copy().convert("RGBA")
    draw = ImageDraw.Draw(annotated_img)

    first_row = next(iter(rows_by_model.values()), None)
    if first_row is not None and pd.notna(first_row.get("ground_truth_bbox")):
        try:
            gt_bbox = ast.literal_eval(first_row["ground_truth_bbox"])
            if len(gt_bbox) >= 4:
                x, y, w, h = gt_bbox[0], gt_bbox[1], gt_bbox[2], gt_bbox[3]
                outer_color, inner_color = (255, 0, 0), (255, 255, 0)
                _draw_dashed_rect(draw, x, y, w, h, outer_color, 5)
                offset = 2
                if w > 2 * offset and h > 2 * offset:
                    _draw_dashed_rect(
                        draw, x + offset, y + offset, w - 2 * offset, h - 2 * offset, inner_color, 3
                    )
        except (ValueError, TypeError, SyntaxError):
            pass

    if draw_predictions:
        for model in selected_models:
            if model in rows_by_model:
                row = rows_by_model[model]
                coords = parse_coords(row.get('coordinates'))
                draw_model_prediction(draw, coords, model, alpha=CURSOR_ALPHA)

    return annotated_img


# Max display width for images sent via WebSocket
_MAX_IMG_W = 1100

def _prep_for_display(img):
    """Resize to display width and convert to RGB JPEG to minimise WebSocket payload."""
    if img.width > _MAX_IMG_W:
        ratio = _MAX_IMG_W / img.width
        img = img.resize((_MAX_IMG_W, int(img.height * ratio)), Image.LANCZOS)
    return img.convert("RGB")


def _render_model_status(row):
    """Render just the Success/Failure badge."""
    success = row['success']
    status_class = "gui-viewer-status-success" if success else "gui-viewer-status-failure"
    status_text = "Success" if success else "Failure"
    st.markdown(f"<div class='{status_class}'>{status_text}</div>", unsafe_allow_html=True)


def _render_model_card_details(row, orig_row=None):
    """Render MSE, Coords, optional MSE diff, and raw_pred."""
    mse_val = f"{row['bbox_center_mse']:.1f}"
    coords_str = "N/A"
    if pd.notna(row.get('coordinates')):
        try:
            coords = ast.literal_eval(row['coordinates'])
            coords_str = f"({coords[0]:.0f}, {coords[1]:.0f})"
        except Exception:
            pass
    mse_line = f"MSE: {mse_val}"
    if orig_row is not None:
        mse_delta = row['bbox_center_mse'] - orig_row['bbox_center_mse']
        delta_class = "gui-viewer-mse-delta-up" if mse_delta > 0 else "gui-viewer-mse-delta-down" if mse_delta < 0 else "gui-viewer-muted"
        mse_line += f" (<span class='{delta_class}'>{mse_delta:+.1f}</span>)"
    lines = [mse_line, f"Coords: {coords_str}"]
    st.markdown(
        "<div class='gui-viewer-metrics-column'>" + "<br>".join(lines) + "</div>",
        unsafe_allow_html=True,
    )
    pred = format_raw_prediction(row.get('raw_prediction'))
    if pred:
        st.markdown(f"<div class='gui-viewer-pred-text'>{pred}</div>", unsafe_allow_html=True)


FAILURE_MODE_OPTIONS = ["All", "Has Failure", "Divergent Outcomes"]

# Experiment groups for comparison
EXPERIMENT_GROUPS = {
    "Which perturbation types help?": {
        "models": ["baseline", "all", "style", "text_shrink_zoom"],
    },
    "Does more data help?": {
        "models": ["baseline", "all", "all_25k_3_epoch"],
    },
    "Real data versus synthetic data": {
        "models": ["baseline", "25k_perturbed_1_epoch", "25k_salesforce_1_epoch"],
    },
}


def _build_available_samples(df_filtered, selected_variant, failure_mode="All", exp_models=None):
    """Build full list, filtered list, and (task_id, step_index) -> 1-based index.

    Failure modes:
    - "Has Failure": keep samples where at least one model in the experiment
      group fails on any variant (original or perturbed).
    - "Divergent Outcomes": keep samples where baseline succeeds on the
      perturbed variant but at least one other model fails on it.
    """
    df_rel = df_filtered[df_filtered["variant"].isin(["original", selected_variant])]
    if df_rel.empty:
        return [], [], {}
    variant_count = df_rel.groupby(["task_id", "step_index"])["variant"].nunique()
    valid_index = variant_count[variant_count >= 2].index

    instructions = (
        df_filtered.groupby(["task_id", "step_index"])["instruction"]
        .first()
        .reindex(valid_index)
    )

    available_samples_all = [
        {"task_id": tid, "step_index": sidx,
         "instruction": instr if pd.notna(instr) else ""}
        for (tid, sidx), instr in instructions.items()
    ]
    full_list_index_by_sample = {
        (s["task_id"], s["step_index"]): i + 1 for i, s in enumerate(available_samples_all)
    }

    filtered_pairs = set(valid_index.tolist())

    # Has Failure: keep only samples where at least one model in the experiment
    # group fails on any eval data variant (original or perturbed)
    if failure_mode == "Has Failure" and exp_models:
        df_exp = df_filtered[
            (df_filtered["variant"].isin(["original", selected_variant])) &
            (df_filtered["model"].isin(exp_models))
        ]
        grouped = df_exp.groupby(["task_id", "step_index"])["hit_box_accuracy"]
        gap_pairs = set()
        for (tid, sidx), group in grouped:
            vals = group.astype(float).values
            if not vals.all():  # at least one model fails on some variant
                gap_pairs.add((tid, sidx))
        filtered_pairs = filtered_pairs & gap_pairs

    # Divergent Outcomes: keep only samples where the baseline model succeeds
    # on the perturbed variant but at least one other model in the experiment
    # group fails on that same perturbed variant
    if failure_mode == "Divergent Outcomes" and exp_models:
        non_baseline = [m for m in exp_models if m != "baseline"]
        df_variant = df_filtered[
            (df_filtered["variant"] == selected_variant) &
            (df_filtered["model"].isin(exp_models))
        ]
        gap_pairs = set()
        for (tid, sidx), grp in df_variant.groupby(["task_id", "step_index"]):
            model_results = dict(zip(grp["model"], grp["hit_box_accuracy"].astype(float)))
            baseline_ok = model_results.get("baseline", 0) == 1.0
            any_other_fail = any(model_results.get(m, 1.0) == 0.0 for m in non_baseline)
            if baseline_ok and any_other_fail:
                gap_pairs.add((tid, sidx))
        filtered_pairs = filtered_pairs & gap_pairs

    available_samples = [
        s for s in available_samples_all
        if (s["task_id"], s["step_index"]) in filtered_pairs
    ]
    return available_samples, available_samples_all, full_list_index_by_sample


def _apply_filter_preservation(available_samples, available_samples_all, full_list_index_by_sample):
    """When filters changed, preserve current sample (same task/step or closest in full list)."""
    ss = st.session_state
    if ss.current_task_id is None or ss.current_step_index is None:
        return
    prev_key = (ss.current_task_id, ss.current_step_index)
    samples_lookup = {(s["task_id"], s["step_index"]): i for i, s in enumerate(available_samples)}
    if prev_key in samples_lookup:
        idx = samples_lookup[prev_key]
        ss.current_sample_index = idx
        if "sample_nav_input" in ss:
            ss.sample_nav_input = idx + 1
        return
    prev_abs_1based = full_list_index_by_sample.get(prev_key)
    if prev_abs_1based is not None and available_samples:
        best_idx, best_dist = 0, float("inf")
        for idx, sample in enumerate(available_samples):
            s_key = (sample["task_id"], sample["step_index"])
            abs_1based = full_list_index_by_sample.get(s_key)
            if abs_1based is not None:
                d = abs(abs_1based - prev_abs_1based)
                if d < best_dist:
                    best_dist, best_idx = d, idx
        ss.current_sample_index = best_idx
    else:
        ss.current_sample_index = 0
    if "sample_nav_input" in ss:
        ss.sample_nav_input = ss.current_sample_index + 1


def _render_compact_header():
    """Single compact header: logos flanking title, badge links below."""
    fig_uri = _logo_data_uri("fig_logo_with_text.svg")
    manifold_uri = _logo_data_uri("manifoldlogo_with_text.webp")
    fig_icon_uri = _logo_data_uri("fig-logo.png")
    fig_badge_icon = _badge_icon_html("fig", fig_icon_uri)
    github_icon = _badge_icon_html("github", fig_icon_uri)
    hf_icon = _badge_icon_html("huggingface", fig_icon_uri)

    logo_style = "height:36px;object-fit:contain;"
    dark_class = "gui-viewer-logo-dark-invert"
    fig_logo_html = f'<a href="{FIG_LINK}" target="_blank" rel="noopener"><img src="{fig_uri}" style="{logo_style}"/></a>' if fig_uri else ''
    manifold_logo_html = f'<a href="{MANIFOLDRG_LINK}" target="_blank" rel="noopener"><img src="{manifold_uri}" class="{dark_class}" style="{logo_style}"/></a>' if manifold_uri else ''

    html = f"""
    <div class="gui-viewer-compact-header">
      <h2 style="margin:0;color:var(--gui-viewer-heading);font-size:1.3rem;font-weight:700;">GUI-Perturbed Finetuned Result Viewer</h2>
      <p style="margin:0.25rem 0 0.4rem;color:var(--gui-viewer-muted);font-size:0.85rem;line-height:1.4;">Explore how finetuned UI-TARS-1.5 variants perform on original vs. perturbed screenshots from GUI-Perturbed</p>
      <div class="header-row">
        {fig_logo_html}
        {manifold_logo_html}
      </div>
      <div class="badges-row">
        <a href="{TECHNICAL_REPORT_1_LINK}" target="_blank" rel="noopener" class="gui-viewer-badge"
           style="display:inline-flex;align-items:center;padding:4px 10px;text-decoration:none;">
          {fig_badge_icon}<span>Technical report</span></a>
        <a href="{CODE_LINK}" target="_blank" rel="noopener" class="gui-viewer-badge"
           style="display:inline-flex;align-items:center;padding:4px 10px;text-decoration:none;">
          {github_icon}<span>Code</span></a>
        <a href="{DATA_LINK}" target="_blank" rel="noopener" class="gui-viewer-badge"
           style="display:inline-flex;align-items:center;padding:4px 10px;text-decoration:none;">
          {hf_icon}<span>Data</span></a>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def _image_to_data_uri(img):
    """Convert PIL Image to JPEG base64 data URI."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _render_magnifier_image(img, caption, uid):
    """Render an image with hover/touch magnifier lens using st.html (inline, no iframe)."""
    display_img = _prep_for_display(img)
    data_uri = _image_to_data_uri(display_img)

    html = f"""
<div style="font-size:0.82rem;color:#888;margin-bottom:2px;">{caption}</div>
<div class="mag-c" id="c_{uid}" style="position:relative;width:100%;cursor:crosshair;">
  <img src="{data_uri}" id="i_{uid}" style="width:100%;display:block;" />
  <div id="l_{uid}" style="display:none;position:absolute;width:160px;height:160px;
    border-radius:50%;border:3px solid rgba(255,255,255,0.85);
    box-shadow:0 0 0 1px rgba(0,0,0,0.15),0 4px 16px rgba(0,0,0,0.25);
    background-repeat:no-repeat;pointer-events:none;z-index:10;"></div>
</div>
<div id="lb_{uid}" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;
  background:rgba(0,0,0,0.85);z-index:9999;cursor:pointer;
  justify-content:center;align-items:center;">
  <img src="{data_uri}" style="max-width:92vw;max-height:92vh;object-fit:contain;" />
</div>
<script>
(function(){{
  const c=document.getElementById('c_{uid}'),
        img=document.getElementById('i_{uid}'),
        lens=document.getElementById('l_{uid}'),
        lb=document.getElementById('lb_{uid}'),
        zoom=1.8, ls=160;
  let dragged=false, startX=0, startY=0;
  function upd(cx,cy){{
    const r=img.getBoundingClientRect();
    let px=cx-r.left, py=cy-r.top;
    px=Math.max(0,Math.min(px,r.width));
    py=Math.max(0,Math.min(py,r.height));
    lens.style.left=(px-ls/2)+'px';
    lens.style.top=(py-ls/2)+'px';
    const bw=r.width*zoom, bh=r.height*zoom;
    lens.style.backgroundImage='url('+img.src+')';
    lens.style.backgroundSize=bw+'px '+bh+'px';
    lens.style.backgroundPosition=(-px*zoom+ls/2)+'px '+(-py*zoom+ls/2)+'px';
    lens.style.display='block';
  }}
  c.addEventListener('mousedown',function(e){{ startX=e.clientX; startY=e.clientY; dragged=false; }});
  c.addEventListener('mousemove',function(e){{
    if(Math.abs(e.clientX-startX)>5||Math.abs(e.clientY-startY)>5) dragged=true;
    upd(e.clientX,e.clientY);
  }});
  c.addEventListener('mouseup',function(){{
    if(!dragged){{ lens.style.display='none'; lb.style.display='flex'; }}
  }});
  c.addEventListener('mouseleave',function(){{ lens.style.display='none'; }});
  c.addEventListener('touchmove',function(e){{ e.preventDefault(); dragged=true; upd(e.touches[0].clientX,e.touches[0].clientY); }},{{passive:false}});
  c.addEventListener('touchstart',function(e){{ dragged=false; startX=e.touches[0].clientX; startY=e.touches[0].clientY; upd(e.touches[0].clientX,e.touches[0].clientY); }});
  c.addEventListener('touchend',function(){{ lens.style.display='none'; if(!dragged) lb.style.display='flex'; }});
  lb.addEventListener('click',function(){{ lb.style.display='none'; }});
  document.addEventListener('keydown',function(e){{ if(e.key==='Escape') lb.style.display='none'; }});
}})();
</script>"""
    st.html(html, unsafe_allow_javascript=True)


def _render_images(original_rows_by_model, variant_rows_by_model, selected_models, variant_name, instruction=None):
    """Render task instruction and side-by-side annotated images (the hero content). Full width."""
    st.markdown("---")
    st.markdown("#### Model Prediction")

    if instruction:
        st.markdown(
            f"<div class='gui-viewer-task-instr-bar'>"
            f"<span class='instr-label'>Task:</span> "
            f"<span>{instruction}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    first_original = next(iter(original_rows_by_model.values()), None)
    first_variant = next(iter(variant_rows_by_model.values()), None)

    if "_ds_index" not in st.session_state or "_ds_parquet_paths" not in st.session_state:
        with st.spinner("Loading image index..."):
            _ensure_dataset_loaded()

    img_original = get_image_for_row(first_original) if first_original is not None else None
    img_variant = get_image_for_row(first_variant) if first_variant is not None else None

    with st.container(key="image_comparison"):
        col1, col2 = st.columns(2)
        with col1:
            if img_original is not None:
                annotated = annotate_image_multi_model(img_original, original_rows_by_model, selected_models, draw_predictions=True)
                _render_magnifier_image(annotated, "Original", "orig")
            else:
                st.info("Image not available")
        with col2:
            if img_variant is not None:
                annotated = annotate_image_multi_model(img_variant, variant_rows_by_model, selected_models, draw_predictions=True)
                _render_magnifier_image(annotated, f"Perturbed ({variant_name.replace('_', ' ').title()})", "pert")
            else:
                st.info("Image not available")


@st.fragment
def _render_model_results(original_rows_by_model, variant_rows_by_model, selected_models):
    """Model results using tabs: one tab per model, each with Original vs Perturbed columns.

    Status badges are always visible; MSE/coords/prediction details toggled by a shared button.
    Uses @st.fragment so toggling details only reruns this section, not the whole page.
    """
    if not selected_models:
        return

    if "show_model_details" not in st.session_state:
        st.session_state.show_model_details = False

    show = st.session_state.show_model_details
    btn_label = "Hide Details" if show else "Show Details"
    if st.button(btn_label, key="toggle_model_details"):
        st.session_state.show_model_details = not show
        st.rerun(scope="fragment")

    tab_labels = [_model_label(m) for m in selected_models]
    tabs = st.tabs(tab_labels)
    for tab, model in zip(tabs, selected_models):
        with tab:
            orig_row = original_rows_by_model.get(model)
            var_row = variant_rows_by_model.get(model)

            # Always-visible status row
            col_o, col_p = st.columns(2)
            with col_o:
                st.markdown("**Original**")
                if orig_row is not None:
                    _render_model_status(orig_row)
                else:
                    st.caption("No original data")
            with col_p:
                st.markdown("**Perturbed**")
                if var_row is not None:
                    _render_model_status(var_row)
                else:
                    st.caption("No perturbed data")

            # Collapsible details (shared toggle)
            if st.session_state.show_model_details:
                det_o, det_p = st.columns(2)
                with det_o:
                    if orig_row is not None:
                        _render_model_card_details(orig_row)
                with det_p:
                    if var_row is not None:
                        _render_model_card_details(var_row, orig_row)


def main():
    def _lap(label, t0):
        print(f"[result_viewer] {label}: {time.perf_counter() - t0:.3f}s", file=sys.stderr, flush=True)
        return time.perf_counter()
    _t0 = time.perf_counter()
    _t = _t0
    print(f"\n[result_viewer] --- rerun start ---", file=sys.stderr, flush=True)

    # --- Compact header (constrained width) ---
    with st.container(key="narrow_header"):
        _render_compact_header()

    # --- Load data ---
    with st.spinner("Loading results..."):
        df = load_data(_mtime=_csv_mtime())
    _t = _lap("load_data", _t)
    if df.empty:
        st.error("No data found")
        with st.expander("Triage: path resolution", expanded=True):
            for path_str, exists in _debug_csv_paths():
                if exists is None:
                    st.text(path_str)
                else:
                    st.text(f"{'✓' if exists else '✗'} {path_str}")
        return

    # --- Compute state from session defaults (widgets rendered later read from previous rerun) ---
    query_types = sorted(df['query_type'].unique().tolist())
    use_reasoning_options = sorted(df['use_reasoning'].unique().tolist())
    _default_query_type = "direct_query" if "direct_query" in query_types else (query_types[0] if query_types else None)
    if "query_type_filter" not in st.session_state and _default_query_type is not None:
        st.session_state.query_type_filter = _default_query_type
    selected_query_type = st.session_state.get("query_type_filter", _default_query_type)
    selected_use_reasoning = st.session_state.get("use_reasoning_filter", use_reasoning_options[0] if use_reasoning_options else None)
    if selected_query_type not in query_types:
        selected_query_type = query_types[0] if query_types else None
    if selected_use_reasoning not in use_reasoning_options:
        selected_use_reasoning = use_reasoning_options[0] if use_reasoning_options else None

    df_filtered = df[
        (df['query_type'] == selected_query_type) &
        (df['use_reasoning'] == selected_use_reasoning)
    ]

    all_models = sorted(df_filtered['model'].unique().tolist())

    _t = _lap("filter extraction + base filter + session state init", _t)

    perturbation_variants = PERTURBATION_VARIANTS
    if "selected_variant" not in st.session_state:
        st.session_state.selected_variant = "style" if "style" in perturbation_variants else perturbation_variants[0]

    # Experiment group selection
    if "selected_experiment" not in st.session_state:
        st.session_state.selected_experiment = list(EXPERIMENT_GROUPS.keys())[0]
    exp_group = EXPERIMENT_GROUPS[st.session_state.selected_experiment]
    exp_models = [m for m in exp_group["models"] if m in all_models]
    # Read checkbox state from previous rerun so images only show checked models
    selected_models = [m for m in exp_models if st.session_state.get(f"model_{m}", True)]

    if 'failure_mode_pills' not in st.session_state:
        st.session_state.failure_mode_pills = "All"

    # Initialize navigation state
    if 'current_sample_index' not in st.session_state:
        st.session_state.current_sample_index = 0
    if 'current_task_id' not in st.session_state:
        st.session_state.current_task_id = None
    if 'current_step_index' not in st.session_state:
        st.session_state.current_step_index = None
    if 'previous_variant' not in st.session_state:
        st.session_state.previous_variant = st.session_state.selected_variant
    if 'sample_nav_input' not in st.session_state:
        st.session_state.sample_nav_input = st.session_state.current_sample_index + 1

    # Build available samples
    _active_failure_mode = st.session_state.get("failure_mode_pills", "All")
    if _active_failure_mode is None:
        _active_failure_mode = "All"
    available_samples, available_samples_all, full_list_index_by_sample = _build_available_samples(
        df_filtered,
        st.session_state.selected_variant,
        _active_failure_mode,
        exp_models=exp_models,
    )
    _t = _lap("_build_available_samples", _t)

    if not available_samples:
        st.error(
            f"No samples found with both original and {st.session_state.selected_variant} perturbation "
            f"for filter \"{_active_failure_mode}\""
        )
        return

    # Preserve current sample when filters change
    current_filter_signature = (
        selected_query_type,
        selected_use_reasoning,
        st.session_state.selected_variant,
        _active_failure_mode,
        st.session_state.selected_experiment,
    )
    filters_changed = st.session_state.get("_filter_signature") != current_filter_signature
    if filters_changed:
        st.session_state._filter_signature = current_filter_signature
        _apply_filter_preservation(
            available_samples, available_samples_all, full_list_index_by_sample
        )
    _t = _lap("filter preservation", _t)

    if st.session_state.previous_variant != st.session_state.selected_variant:
        st.session_state.previous_variant = st.session_state.selected_variant

    st.session_state.num_available_samples = len(available_samples)

    if st.session_state.current_sample_index >= len(available_samples):
        st.session_state.current_sample_index = 0

    current_sample = available_samples[st.session_state.current_sample_index]
    st.session_state.current_task_id = current_sample['task_id']
    st.session_state.current_step_index = current_sample['step_index']

    # Build rows by model for current sample — only experiment group models
    sample_data = df_filtered[
        (df_filtered['task_id'] == current_sample['task_id']) &
        (df_filtered['step_index'] == current_sample['step_index'])
    ]
    _t = _lap("sample data filter", _t)

    original_rows_by_model = {}
    variant_rows_by_model = {}
    for model in exp_models:
        model_data = sample_data[sample_data['model'] == model]
        original_data = model_data[model_data['variant'] == 'original']
        variant_data = model_data[model_data['variant'] == st.session_state.selected_variant]
        if not original_data.empty:
            original_rows_by_model[model] = original_data.iloc[0]
        if not variant_data.empty:
            variant_rows_by_model[model] = variant_data.iloc[0]
    _t = _lap("build rows by model", _t)

    # ==========================================
    # RENDER: Images (hero content)
    # ==========================================
    _render_images(
        original_rows_by_model,
        variant_rows_by_model,
        selected_models,
        st.session_state.selected_variant,
        instruction=current_sample["instruction"],
    )
    _t = _lap("render images", _t)

    # ==========================================
    # RENDER: Experiment group selector + model checkboxes + divergent filter
    # ==========================================
    with st.container(key="narrow_model_display"):
        exp_names = list(EXPERIMENT_GROUPS.keys())
        new_experiment = st.radio(
            "Experiments",
            exp_names,
            index=exp_names.index(st.session_state.selected_experiment),
            horizontal=True,
            key="experiment_radio",
        )
        if new_experiment != st.session_state.selected_experiment:
            st.session_state.selected_experiment = new_experiment
            st.rerun()

        exp_group = EXPERIMENT_GROUPS[st.session_state.selected_experiment]
        exp_models = [m for m in exp_group["models"] if m in all_models]

        # Model checkboxes with cursor color swatches
        if exp_models:
            model_display_cols = st.columns(len(exp_models))
            for i, model in enumerate(exp_models):
                with model_display_cols[i]:
                    ms = MODEL_STYLES.get(model, {"color": (180, 180, 180), "label": model})
                    r, g, b = ms["color"]
                    swatch = (
                        f'<span style="display:inline-block;width:12px;height:12px;'
                        f'background:rgb({r},{g},{b});border:1px solid rgba(128,128,128,0.5);'
                        f'border-radius:2px;vertical-align:middle;margin-right:4px;"></span>'
                    )
                    st.markdown(
                        f"<div style='font-size:0.85rem;margin-bottom:-0.5rem;'>{swatch}"
                        f"<span style='vertical-align:middle;color:var(--gui-viewer-muted);'>cursor</span></div>",
                        unsafe_allow_html=True,
                    )
                    st.checkbox(
                        _model_label(model),
                        value=st.session_state.get(f"model_{model}", True),
                        key=f"model_{model}",
                    )

        # Failure mode filter
        st.pills(
            "Failure Mode Filter",
            FAILURE_MODE_OPTIONS,
            key="failure_mode_pills",
        )

    # Recompute selected_models from checkboxes within the experiment group
    selected_models = [m for m in exp_models if st.session_state.get(f"model_{m}", True)]

    # ==========================================
    # RENDER: Sample navigation
    # ==========================================
    def on_sample_change():
        new_val = st.session_state.sample_nav_input
        if new_val - 1 != st.session_state.current_sample_index:
            st.session_state.current_sample_index = new_val - 1

    with st.container(key="narrow_sample_nav"):
        position_in_full_list = full_list_index_by_sample.get(
            (current_sample['task_id'], current_sample['step_index'])
        )
        total_in_full_list = len(available_samples_all)
        nav_label = f"Sample ({st.session_state.current_sample_index + 1} of {len(available_samples)}"
        if position_in_full_list is not None and total_in_full_list != len(available_samples):
            nav_label += f" | {position_in_full_list} of {total_in_full_list} total"
        nav_label += ")"
        st.number_input(
            nav_label,
            min_value=1,
            max_value=len(available_samples),
            key="sample_nav_input",
            on_change=on_sample_change,
        )

    # ==========================================
    # RENDER: Model results — comparison table
    # ==========================================
    with st.container(key="narrow_results"):
        st.markdown("#### Model Results")
        if selected_models:
            _render_model_results(original_rows_by_model, variant_rows_by_model, selected_models)
        else:
            st.caption("Select a model above to view results.")
    _t = _lap("render model results", _t)

    # ==========================================
    # RENDER: Filters & Search
    # ==========================================
    with st.container(key="narrow_controls"):
        st.markdown("---")
        st.markdown("#### GUI-Perturbed Eval Data Filters & Search")

        # Filter dropdowns
        f = st.columns(3)
        with f[0]:
            new_variant = st.selectbox(
                "Visual Variant",
                perturbation_variants,
                index=perturbation_variants.index(st.session_state.selected_variant),
                format_func=lambda x: x.replace('_', ' ').title(),
                key="perturbation_select_main",
                help="Precision: viewport zoom. Style: visual randomization. Text Shrink: font size reduced.",
            )
        with f[1]:
            st.selectbox(
                "Instruction Variant",
                query_types,
                key="query_type_filter",
                format_func=lambda x: x.replace('_', ' ').replace('query', 'instruction').replace('Query', 'Instruction').title(),
                help="Direct Instruction vs Relational Instruction",
            )
        with f[2]:
            st.selectbox(
                "Reasoning",
                use_reasoning_options,
                key="use_reasoning_filter",
                format_func=lambda x: "Yes" if x else "No",
                help="Whether chain-of-thought reasoning was used",
            )

        # Search instructions
        def on_search():
            query = st.session_state.get("instruction_search", "").strip().lower()
            if not query:
                return
            n = len(available_samples)
            if n == 0:
                return
            start = (st.session_state.current_sample_index + 1) % n
            for offset in range(n):
                idx = (start + offset) % n
                instr = available_samples[idx].get("instruction", "").lower()
                if query in instr:
                    st.session_state.current_sample_index = idx
                    st.session_state.sample_nav_input = idx + 1
                    return

        st.text_input(
            "Search instructions",
            key="instruction_search",
            on_change=on_search,
            placeholder="Type to search task instructions...",
        )

    _t = _lap("control panel widgets", _t)

    # Handle variant change
    if new_variant != st.session_state.selected_variant:
        st.session_state.selected_variant = new_variant
        st.rerun()

    _lap("main() total", _t0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        st.error("Dashboard failed to load")
        st.exception(e)
        st.code(traceback.format_exc(), language="text")

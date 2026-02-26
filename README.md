# WebDomainRandomizer

A tool for evaluating AI agent performance on web tasks with domain randomization perturbations.

## Comparison UI

The comparison UI allows you to visually compare AI agent performance between original web interfaces and perturbed versions.

### Running the UI

1. **Install dependencies:**
   ```bash
   pip install streamlit pandas pillow
   ```

2. **Run the Streamlit app:**
   ```bash
   cd WebDomainRandomizer
   streamlit run comparison_ui.py
   ```

3. **Access the UI:**
   The app will open automatically in your browser at `http://localhost:8501`

### Features

- **Side-by-side comparison**: View original and perturbed screenshots with prediction overlays
- **Interactive navigation**: Use the draggable timeline slider to navigate through task steps
- **Multiple perturbations**: Compare against different perturbation types (precision/viewport zoom, style randomization, text shrink)
- **Performance metrics**: View prediction errors, success rates, and coordinate predictions
- **Debug mode**: Toggle technical debug information for troubleshooting
- **Research findings**: View primary research findings and insights at the bottom of the page
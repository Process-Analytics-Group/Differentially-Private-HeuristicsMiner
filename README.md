# Differentially Private Heuristics Miner (DPHM)

The **DPHM** discovers a dependency graph and a Petri net from an XES event log using noisy directly-follows statistics and a Heuristics Miner implementation based on PM4Py. A graphical user interface allows the user to adjust epsilon ($\epsilon$), mining thresholds, and optional rejection sampling criteria.

# Installation

Clone the repository and install the Python requirements:

```bash
git clone https://github.com/Process-Analytics-Group/Differentially-Private-HeuristicsMiner.git
cd Differentially-Private-HeuristicsMiner
python3 -m pip install -r requirements.txt
```

The application also requires:

- **Tkinter** and a graphical desktop session for the interface.
- **Graphviz**, including the `dot` executable on your system's `PATH`, for graph rendering. Installing the Python `graphviz` package alone does not install the executable.
- **Cairo**, as required by CairoSVG, for rendering the Petri net image.

Use the versions in [requirements.txt](requirements.txt).

# Execution

Start the application from the repository directory:

```bash
python3 main.py
```

Click **Open File...** and select an `.xes` event log. Loading the file automatically starts discovery. The upper canvas displays the **Dependency Graph**, and the lower canvas displays the **Petri Net**.

The event log must contain non-empty traces and activity names stored in the XES `concept:name` attribute. The repository does not include example event logs.

The DPHM offers two rejection sampling settings:

1. **No Rejection Sampling** — the default. The application renders a candidate without applying a quality-score threshold. Noise is still applied to the underlying statistics.
2. **Quality-based rejection sampling** — select **F1-Score**, **Fitness**, **Precision**, **Simplicity**, or **Generalization** and set a rejection sampling threshold. The candidate is accepted when its noisy score meets or exceeds that threshold.

**Info:** Configuration is performed through the GUI.

# Parameters

The following controls are available in the GUI:

| Control | Default / initialization | Allowed values | Description |
| --- | --- | --- | --- |
| Rejection Sampling Attribute | No Rejection Sampling | No Rejection Sampling, F1-Score, Fitness, Precision, Simplicity, Generalization | Selects the acceptance criterion. |
| Rejection Sampling Threshold | `0.0` | `0.0`–`1.0`, step `0.01` | Minimum noisy quality score required for acceptance. Ignored when no rejection sampling is selected. |
| Epsilon | `5.0` | `0.01`–`5.0`, step `0.01` | Controls Laplace noise: smaller values produce larger noise scales. |
| Dependency | `-1.0` | `-1.0`–`1.0`, step `0.01` | Dependency threshold used when constructing the Heuristics Net. |
| And | `0.01` | `0.01`–`1.0`, step `0.01` | Threshold for AND relations. |
| Noise | `0.01` | `0.01`–`1.0`, step `0.01` | DFG pre-cleaning threshold; this is separate from the Laplace noise controlled by epsilon. |
| Loop | `0.01` | `0.01`–`1.0`, step `0.01` | Length-two loop threshold passed to the miner. |
| Set min. count of DFG | `1` | Non-negative integers | Minimum noisy directly-follows count for a connection. |
| Set min. count of Activities | `1` | Non-negative integers | Minimum activity count derived from the noisy DFG. |

Releasing the **Epsilon** slider generates fresh noisy statistics. Releasing the other sliders, changing the rejection criterion, or setting a minimum count reruns discovery using the current noisy statistics. With a quality criterion selected, the acceptance score is noised again during evaluation.

# Example

To discover a model from your own event log with $\epsilon = 1.0$:

1. Run `python3 main.py`.
2. Set **Epsilon** to `1.0` before loading the log.
3. Leave **Rejection Sampling Attribute** at **No Rejection Sampling** for an initial result.
4. Click **Open File...** and select your `.xes` file.
5. Adjust **Dependency**, **And**, **Noise**, and the minimum counts as needed.
6. Optionally select **F1-Score** and set **Rejection Sampling Threshold** to `0.90`.
7. Click **Save DG** or **Save PN** to export the corresponding image.

The threshold is checked against a **noisy** score, so `0.90` does not guarantee that the unnoised F1-score is at least `0.90`. Results can differ between runs.

# Bounds used

Bounds are computed automatically in [DPHM.py](DPHM.py); no dataset-specific bounds or manual bound inputs are provided.

For $n$ unique activities, the implementation creates $n^2$ activity pairs, including self-pairs, plus $2n$ synthetic start/end pairs. Each pair contributes at most once per trace. After adding noise, the synthetic pairs are used to select start and end activities and are removed from the activity-pair matrix.

Let $c$ be the number of activity pairs with a positive noisy count. The code computes:

```python
lower = max(c, 5 * round((c - 15) / 5))
upper = min(c ** 2, 5 * round((c + 15) / 5))
lower = max(lower, n)
if upper >= n ** 2:
    upper = n ** 2 - 1
```

If both bounds are equal, that number of highest-scoring noisy pairs is retained. Otherwise, the number is sampled with `numpy.random.randint(lower, upper)`, whose upper bound is exclusive. The implementation does not guard against `lower > upper`; small logs or particular noise draws can therefore cause an invalid-bound error.

# Rejection sampling

The following settings are defined in `DPHM.__init__` and are not exposed as GUI controls:

| Setting | Value | Use in the implementation |
| --- | --- | --- |
| `max_sampling_tries` | `500` | Maximum number of attempts per call. |
| `gamma` | `0.01` | Probability of stopping without a result before each attempt. |
| `e0` | `0.9` | Matrix entries receive Laplace noise with scale `1 / (epsilon * e0)`. |
| `e1` | `0.1` | Quality scores receive Laplace noise with scale `(1 / number_of_traces) / (epsilon * e1)`. |

Candidates must pass a weak-connectivity check on the retained DFG. The retry limit and random stopping rule also apply when **No Rejection Sampling** is selected. A call can finish without displaying a new model; previously rendered images can remain visible.

# Visualization and export

- Drag with the left mouse button to pan an image.
- Use the mouse wheel to zoom. In the current implementation, positive wheel movement zooms out and negative movement zooms in.
- **Save DG** exports the dependency graph image.
- **Save PN** exports the Petri net image.
- The save dialog offers **JPEG** and **PNG**, with JPEG as the default. It saves the image at its current zoom size.
- **Quit** closes the application loop.

The dependency graph displays dependency scores rounded to two decimal places. Its rendering uses a strict `>` dependency-threshold comparison, while Heuristics Net construction uses `>=` and additional count filters; the two views need not contain identical connections. Export is image-only; the GUI does not provide PNML or BPMN export.

# Repository structure

| File | Purpose |
| --- | --- |
| [main.py](main.py) | Starts the GUI and its event loop. |
| [GUI.py](GUI.py) | File selection, parameter controls, canvases, zooming, panning, and image export. |
| [DPHM.py](DPHM.py) | Log preprocessing, noise generation, subset selection, Heuristics Net construction, rejection sampling, and rendering. |
| [requirements.txt](requirements.txt) | Pinned Python dependencies. |

---

This README describes the source at [commit `eafd854`](https://github.com/Process-Analytics-Group/Differentially-Private-HeuristicsMiner/tree/eafd854497367ef663dc5f3b5e3068a16c06cacb). Installation and GUI execution have not been validated as part of this documentation review.

# Running the notebooks on Kaggle

Kaggle runs the notebooks as they are; three things differ from Colab.

1. **Internet on.** The first cell clones this repository (the helper module and the synthetic sample)
   and the live mode reads https://interestratedecision.com/data/decisions.csv. In the notebook's
   settings, turn **Internet** on (it needs a phone-verified Kaggle account).
2. **Import the notebook from GitHub.** New Notebook, File, Import Notebook, the GitHub tab, then
   `Interest-Rate-Decision/notebooks` and one of `01-event-study.ipynb`, `02-surprise-vs-reaction.ipynb`,
   `03-hour-before-range.ipynb`.
3. **Candles as a private dataset.** Kaggle has no Node.js for `dukascopy-node` by default, so download
   the candles on your own machine (`python scripts/download_candles.py ...`), zip the `candles/` folder
   and upload it as a **private** Kaggle dataset: Dukascopy's data is not yours or ours to publish.
   Then point the notebook at it:

   ```python
   SAMPLE = False
   CANDLES_DIR = "/kaggle/input/<your-dataset>/candles"
   ```

Publishing the notebooks themselves on Kaggle is fine: they hold no Dukascopy data. Run them on the
sample before saving a public version, or clear the outputs, so no figure from licensed candles goes
public with them. Credit the decisions with a link to https://interestratedecision.com/?via=notebooks.

Suggested listing (title, then subtitle):

- *Central bank decisions: an event study in Python* / Fed, ECB, BoE and seven more on their pairs, three hours before to five after.
- *Rate surprise vs the reaction* / The move against the previous rate, or your own consensus.
- *The hour before and the close back* / InterestRateDecision.com's measurement of the first spike, in Python.

Tags: `finance`, `time series`, `economics`, `forex`, `python`.

# AI / ML projects

Machine learning and LLM work — model training and evaluation, fine-tuning workflows, and applied data science. Projects here are reproducible, with pinned dependencies and results reported honestly.

## Projects

- **[LLM fine-tuning workflow](llm-fine-tuning-workflow/)** — a config-driven LoRA fine-tuning pipeline for small language models: data preparation, training, evaluation, and local inference, all runnable on a laptop CPU. Cuts validation perplexity from 39.8 to 22.0 on a 900-example instruction dataset.
- **[Exoplanet transit classifier](exoplanet-transit-classifier/)** — classifies Kepler light curves as exoplanet transit or not, using the same pattern-recognition task as citizen-science transit hunting. Detrending + a 400-lag autocorrelation grid push a gradient-boosting model to 0.946 cross-validated ROC-AUC, with zero false positives on the held-out test set.

New projects are added here as they are completed.

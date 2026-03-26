# Research Data — Raw Outputs

This directory holds raw model outputs from research experiments.
These are the primary data source for the paper; the experiment log
(`docs/research/experiment_log.md`) is the analysis layer on top.

## Convention

Each test run produces a JSON file:

```
raw_outputs/{test_name}_{model}_{date}.json
```

### Required fields

```json
{
  "test_name": "alt_hypothesis_A_temperature",
  "model": "gemma-3-12b-it-4bit",
  "backend": "mlx",
  "date": "2026-03-26",
  "temperature": 0.3,
  "corpus": "ethnic_studies",
  "class_reading_source": "checkpoints/ethnic_studies_gemma12b_mlx_class_reading.json",
  "results": [
    {
      "student_id": "S022",
      "student_name": "Destiny Williams",
      "run": 1,
      "prompt": "... full prompt text ...",
      "system_prompt": "... full system prompt ...",
      "raw_output": "... complete model output ...",
      "classification": "ASSET",
      "time_seconds": 52.3
    }
  ]
}
```

### Rules

1. ALWAYS save complete prompts and raw model output text (full prose, not just classifications)
2. NEVER save to /tmp — use this directory
3. Include enough metadata to reproduce the run
4. One file per logical test (may contain multiple students/runs)

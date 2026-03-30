# Meeting Forecast Helper

This small app loads meeting notes in **JSON** and **Markdown**, identifies which files should be used to refresh forecasting inputs, and outputs a ranked list of top requirement questions.

## How source files are selected
A file is considered a refresh source when one of these is true:

- JSON has `use_for_refresh: true` or `refresh_source: true`
- JSON/Markdown instructions include the word `refresh`
- Markdown contains `[refresh-source]`

If no file is marked as refresh source, all discovered files are used.

## Run

```bash
python3 forecast_app.py examples --top 5 --out forecast_output.json
```

## Expected input shapes

### JSON

```json
{
  "last_updated": "2026-03-28",
  "use_for_refresh": true,
  "instructions": ["..."],
  "requirements": ["..."],
  "questions": ["..."]
}
```

### Markdown
Use headings like:

- `## Instructions`
- `## Requirements`
- `## Questions`

And bullet points under each heading.

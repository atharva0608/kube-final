# spot_risk_collection

## Purpose
The spot risk collection module presents a colour-coded visualisation of Spot Instance interruption frequency data per instance type. It is informational only—it helps operators understand the historical interruption landscape so they can make informed decisions about which instance types to prefer, but it does not function as a hard scheduling signal within the BalanceKube engine.

## Responsibilities
- Display a table of instance types within a selected AWS region, annotated with their interruption frequency band and numeric risk score.
- Colour-code each row by interruption frequency band:
  - **Green:** < 5% interruption rate
  - **Yellow:** 5–10%
  - **Orange:** 10–15%
  - **Red:** > 15%
- Show the risk score on a 0–10 scale for each instance type.
- Show historical trend information if available (e.g., whether the risk score has increased or decreased over the past 30 days).
- Display a prominent disclaimer: _"Historical data — not a guarantee of future interruption rates."_
- Allow the operator to filter by interruption frequency band or sort by risk score.

## Inputs
- **Source:** `GET /spot-risk/:region`
- **Format:**
```json
{
  "region": "string",
  "fetched_at": "ISO8601 timestamp",
  "instance_types": [
    {
      "instance_type": "string",
      "interruption_rate_pct": "number",
      "frequency_band": "< 5% | 5-10% | 10-15% | >15%",
      "risk_score": "number (0-10)",
      "trend": "improving | stable | worsening | unknown",
      "history": [{ "date": "string", "risk_score": "number" }]
    }
  ]
}
```
- **Source:** Region selector (operator-controlled UI state)

## Outputs
- **Destination:** Rendered risk table in the operator browser
- **Destination:** HTTP GET requests to backend API (read-only)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `interruption_rates`, `risk_scores`, `spot_risk_history`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/spot-risk/:region` | Fetch spot interruption risk data for all instance types in a region |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `DataTable` (sortable by risk score, filterable by band), `StatusBadge` (colour-coded band), `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for spot risk API response

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **No data for region:** If the selected region returns an empty instance list (e.g., pricing/risk data collection has not yet run), the module shows an informational empty state with a message indicating when data is expected to be available.
- **API error:** Shows an error card with a retry button.
- **Stale risk data:** If `fetched_at` is more than 24 hours old, a yellow banner warns the operator that the risk data may not reflect current AWS conditions.

## Future Enhancements
- Integration with the eligibility engine's instance type selection to highlight which instance types in the risk table are candidates for each workload.
- Direct link from a recommended instance type in the recommendations module to its row in this risk table.
- AZ-level granularity for interruption rates (currently region-level aggregate).

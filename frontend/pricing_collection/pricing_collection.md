# pricing_collection

## Purpose
The pricing collection module provides an operator-facing browser for the AWS EC2 pricing data that BalanceKube collects to compute cost savings estimates. It allows operators to inspect on-demand and spot prices per instance type and availability zone, understand the instance catalog, and verify that pricing data is fresh before trusting savings projections.

## Responsibilities
- Display a side-by-side comparison of on-demand price and current spot price for each instance type within a selected AWS region and availability zone.
- Show a price staleness warning banner if the most recent pricing data is older than 60 minutes.
- Render an instance catalog table showing vCPU count, memory (GiB), network performance tier, and instance family for all instance types in the catalog.
- Render a 30-day rolling spot price history chart for a selected instance type, showing price fluctuations over time.
- Allow operators to switch region context using a region selector dropdown.

## Inputs
- **Source:** `GET /pricing/:region/on-demand`
- **Format:** `Array<{ instance_type, vcpu, memory_gib, on_demand_price_usd_hr, fetched_at }>`
- **Source:** `GET /pricing/:region/spot`
- **Format:** `Array<{ instance_type, availability_zone, spot_price_usd_hr, fetched_at, history: Array<{ timestamp, price }> }>`
- **Source:** `GET /pricing/instance-catalog`
- **Format:** `Array<{ instance_type, vcpu, memory_gib, network_performance, instance_family, supported_architectures }>`
- **Source:** Region selector (operator-controlled UI state)

## Outputs
- **Destination:** Rendered pricing tables and spot price history chart in the operator browser
- **Destination:** HTTP GET requests to the backend API (read-only)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `on_demand_prices`, `spot_prices`, `instance_catalog`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/pricing/:region/on-demand` | Fetch current on-demand prices for all instance types in a region |
| `GET` | `/pricing/:region/spot` | Fetch current spot prices per instance type per AZ with 30-day history |
| `GET` | `/pricing/instance-catalog` | Fetch instance catalog (vCPU, memory, network tier, family) |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `DataTable` (sortable by price, vCPU, memory), Chart (spot price history line chart), `StatusBadge` (price staleness), `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for pricing API responses

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_PRICING_STALENESS_THRESHOLD_MIN` | Minutes after which a staleness warning is shown | `60` |

## Error Handling
- **Stale data warning:** Compares `fetched_at` from pricing data against the current time; shows a yellow banner if data exceeds `VITE_PRICING_STALENESS_THRESHOLD_MIN`.
- **Empty catalog:** Shows an informational message if the instance catalog is empty (e.g., first-time data collection not yet complete).
- **API error per tab:** Each pricing tab (on-demand, spot, catalog) handles errors independently; failure in one tab does not affect the others.
- **Region not found:** If the selected region has no pricing data, a contextual message is shown prompting the operator to verify that the pricing collection worker has run for that region.

## Future Enhancements
- Spot price volatility score per instance type (standard deviation of 30-day prices).
- Filter catalog by minimum vCPU, memory range, and instance family.
- Multi-region side-by-side price comparison.
- Export spot price history to CSV for offline analysis.

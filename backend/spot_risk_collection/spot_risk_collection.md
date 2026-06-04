# spot_risk_collection

## Purpose
The `spot_risk_collection` module fetches, parses, and stores AWS Spot Instance interruption risk data from the AWS Spot Instance Advisor. It exists as a separate module because spot risk is a distinct data concern — sourced from a specific AWS JSONP endpoint on its own polling schedule — that feeds the eligibility and recommendation engines as an informational signal about the historical likelihood of a Spot Instance being interrupted for a given instance type and region.

## Responsibilities
- Fetch the AWS Spot Instance Advisor dataset from `https://spot-price.s3.amazonaws.com/spot.js` on a scheduled interval
- Strip the JSONP wrapper (`callback(...)` format) before JSON parsing
- Map AWS Spot Advisor frequency bands to internal float midpoints and normalized 0–10 risk scores
- Upsert current risk scores into `risk_scores` and raw frequency bands into `interruption_rates`
- Append a historical record to `spot_risk_history` on each successful fetch (90-day rolling retention)
- Cache the most recent risk scores in Redis for low-latency consumption by the eligibility engine
- Retain the previous Redis cache value (do not evict) on fetch failure to preserve the last known good risk signal
- Expose no public REST endpoints — data is consumed internally only

## Inputs

### AWS Spot Instance Advisor (JSONP)
- **Source**: HTTP GET `https://spot-price.s3.amazonaws.com/spot.js`
- **Frequency**: Configurable via `SPOT_ADVISOR_POLL_INTERVAL_MS` (default: 3600000 ms = 1 hour)
- **Format**: JSONP string `callback({...})` — the JSONP wrapper is stripped by string manipulation before `JSON.parse()`
- **Parsed JSON structure**:
```json
{
  "spot_advisor": {
    "us-east-1": {
      "Linux": {
        "m5.xlarge": { "s": 2, "r": 11 },
        "c5.2xlarge": { "s": 0, "r": 5 }
      }
    }
  },
  "ranges": [
    { "index": 0, "label": "<5%",  "dots": 0, "max": 5 },
    { "index": 1, "label": "5-10%",  "dots": 1, "max": 10 },
    { "index": 2, "label": "10-15%", "dots": 2, "max": 15 },
    { "index": 3, "label": "15-20%", "dots": 3, "max": 20 },
    { "index": 4, "label": ">20%",   "dots": 4, "max": 100 }
  ]
}
```

**Field semantics**:
- `s`: savings percentage vs on-demand (informational only — not used by BalanceKube; we compute our own savings)
- `r`: interruption frequency range index (0–4), references `ranges` array

> **Important limitation**: Spot Advisor data is per-region, NOT per-AZ. It is historical aggregated data, NOT real-time. It is used only as an informational risk signal, not as a gating criterion.

## Outputs

### Database Writes
| Table | Write Pattern |
|---|---|
| `interruption_rates` | Upsert on `(instance_type, region)` — update `frequency_band` and `float_midpoint` |
| `risk_scores` | Upsert on `(instance_type, region)` — update `risk_score`, `interruption_band`, `updated_at` |
| `spot_risk_history` | Append-only insert per fetch cycle (90-day retention enforced by pruning worker) |

### Redis Cache
After each successful fetch:
- Key: `risk:{instance_type}:{region}` — Value: `{ riskScore: int, interruptionBand: string, updatedAt: ISO string }` — TTL: `86400` seconds (24 hours)

On fetch failure: **do not update or delete** existing Redis keys. Let the TTL serve stale data rather than exposing a gap in the risk signal.

### No Events Published
This module does not publish NATS events. Risk data is consumed directly from Redis and PostgreSQL.

## Events Produced
N/A — spot risk data is refreshed on a schedule. No events are emitted when risk scores change.

## Events Consumed
N/A — this module is entirely schedule-driven. It does not subscribe to NATS events.

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `interruption_rates` | `id`, `instance_type VARCHAR`, `region VARCHAR`, `frequency_band VARCHAR` (e.g. `'<5%'`), `float_midpoint NUMERIC(5,2)` (e.g. `2.5`), `updated_at TIMESTAMPTZ` | Unique constraint on `(instance_type, region)` for upsert |
| `risk_scores` | `id`, `instance_type VARCHAR`, `region VARCHAR`, `risk_score INT` (0–10), `interruption_band VARCHAR`, `risk_level VARCHAR` (`'low'`/`'medium'`/`'high'`), `updated_at TIMESTAMPTZ` | Unique constraint on `(instance_type, region)`. `risk_level` derived from `risk_score` at write time |
| `spot_risk_history` | `id`, `instance_type VARCHAR`, `region VARCHAR`, `risk_score INT`, `frequency_band VARCHAR`, `recorded_at TIMESTAMPTZ` | Append-only. Pruned to 90-day window by scheduled worker |

### Frequency Band → Float Midpoint Mapping
| Band Index | Label | Float Midpoint | Risk Score | Risk Level |
|---|---|---|---|---|
| 0 | `<5%` | 2.5 | 1 | low |
| 1 | `5-10%` | 7.5 | 3 | low |
| 2 | `10-15%` | 12.5 | 5 | medium |
| 3 | `15-20%` | 17.5 | 7 | medium |
| 4 | `>20%` | 25.0 | 9 | high |

**Risk score thresholds**:
- `≤ 3` → `low`
- `4–6` → `medium`
- `≥ 7` → `high`

### Tables Read (Cross-Domain, Read-Only)
None — this module reads only from the AWS Spot Advisor endpoint and Redis (to check whether a key exists before deciding to evict on failure).

## APIs
N/A — this is a background worker module. It exposes no REST endpoints. Risk scores are accessed by `eligibility_engine` and `recommendations` via direct database reads or Redis cache lookups.

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/logger` | Structured logging with `region`, `instanceType`, `fetchCycle` context |
| `database` | PostgreSQL pool; upsert helpers for risk tables |

### External Services
| Service | Access Method | Purpose |
|---|---|---|
| AWS Spot Instance Advisor | HTTP GET (unauthenticated public endpoint) | Source of interruption frequency band data |
| Redis | `ioredis` SET with EX | Cache current risk scores for eligibility engine |
| BullMQ | `bullmq` | Schedule recurring fetch worker (`spot-risk-worker`) |

### Sub-Modules
| Sub-Module | Responsibility |
|---|---|
| `aws_spot_advisor` | HTTP fetch; JSONP wrapper stripping; JSON parse; iterate region/OS/instance combos |
| `interruption_rates` | Map range index to frequency band label and float midpoint; write `interruption_rates` table |
| `historical_dataset` | Append to `spot_risk_history`; run pruning query to enforce 90-day retention |
| `risk_normalization` | Convert frequency band / float midpoint to 0–10 risk score; derive `risk_level` string |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `SPOT_ADVISOR_URL` | `https://spot-price.s3.amazonaws.com/spot.js` | URL for the Spot Advisor JSONP file |
| `SPOT_ADVISOR_POLL_INTERVAL_MS` | `3600000` | Poll interval in ms (1 hour) |
| `SPOT_RISK_REDIS_TTL` | `86400` | Redis TTL for risk score keys in seconds (24 hours) |
| `SPOT_RISK_HISTORY_RETENTION_DAYS` | `90` | Days to retain `spot_risk_history` rows |
| `SPOT_ADVISOR_HTTP_TIMEOUT_MS` | `15000` | HTTP fetch timeout in ms |
| `SPOT_ADVISOR_REGIONS` | all AWS regions | Comma-separated list of regions to extract from Spot Advisor payload |
| `SPOT_RISK_PRUNE_CRON` | `0 4 * * *` | Cron for `spot_risk_history` pruning worker (4 AM UTC daily) |

## Error Handling

| Scenario | Behavior |
|---|---|
| HTTP fetch of Spot Advisor JSONP fails (network error, non-200) | Log `IRATE_FETCH_FAILED` at WARN level. Do NOT evict Redis keys — retain previous value for its remaining TTL. Do NOT create an alert. Skip this poll cycle; next attempt at next interval. |
| JSONP stripping fails (unexpected format) | Log `IRATE_PARSE_FAILED` with raw response excerpt. Same fallback as HTTP failure. |
| JSON parse error after JSONP strip | Log `IRATE_JSON_PARSE_FAILED`. Same fallback. |
| DB upsert failure | Retry 3× with exponential backoff. On persistent failure, log `IRATE_DB_WRITE_FAILED`; move to dead-letter job. Redis still holds previous valid data. |
| Redis SET failure after DB write | Logged as `IRATE_REDIS_CACHE_FAILED`; DB row is authoritative; downstream reads fall back to DB query. |
| Unknown instance type in payload | Accepted and written — does not require an entry in `instance_catalog`. |
| Historical prune worker failure | Logged; skipped; next daily run will prune the combined window. No impact on active risk data. |

## Future Enhancements
- **Per-AZ risk granularity**: Supplement the regional Spot Advisor data with per-AZ interruption signals derived from Spot price volatility history, providing more precise placement recommendations
- **Real-time interruption signal**: Integrate AWS EventBridge `EC2 Spot Instance Interruption Warning` events (2-minute notice) to update in-flight execution plans
- **Risk trend alerting**: Publish a NATS event when a risk score increases by ≥ 2 points within a 24-hour period, triggering automatic reanalysis for affected workloads
- **Multi-cloud risk data**: Extend to GCP Spot Advisor equivalents and Azure Spot eviction rate APIs for multi-cloud parity
- **Weighted risk composite**: Combine Spot Advisor interruption rate with real-time spot price volatility and AZ capacity history into a single composite risk score

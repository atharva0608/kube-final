# pricing_collection

## Purpose
The `pricing_collection` module is responsible for fetching, normalizing, and storing AWS EC2 pricing data — including on-demand prices, real-time spot prices, and a static instance type catalog — used by the savings estimator in Phase 2. It exists as a separate module because pricing data has its own external data sources, polling schedules, and normalization logic entirely distinct from the cluster agent push path; it is a platform-side background concern, not a per-cluster concern.

## Responsibilities
- Fetch on-demand EC2 pricing from the AWS Pricing bulk JSON API daily for all configured regions
- Fetch real-time spot price history from `ec2:DescribeSpotPriceHistory` every 15 minutes for all configured instance types and regions
- Build and maintain a static instance type catalog (vCPU count, memory GiB, network performance class, instance family) sourced from `ec2:DescribeInstanceTypes`
- Normalize all prices to a canonical $/hour float; derive $/month and per-resource-unit breakdowns ($/vCPU/hr, $/GiB/hr)
- Cache the most recent spot prices in Redis for low-latency consumption by the recommendation engine
- Persist all pricing rows to PostgreSQL for historical analysis and savings trend computation
- Expose no public REST endpoints — all data is consumed internally by `recommendations` and `snapshot_assembly`

## Inputs

### AWS Pricing Bulk JSON API (On-Demand)
- **Source**: HTTP GET `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/{region}/index.json`
- **Frequency**: Once per day (configurable via `PRICING_POLL_CRON`)
- **Format**: AWS Pricing API JSON. Key structure:
```json
{
  "products": {
    "<sku>": {
      "attributes": {
        "instanceType": "m5.xlarge",
        "location": "US East (N. Virginia)",
        "operatingSystem": "Linux",
        "tenancy": "Shared",
        "capacityStatus": "Used"
      }
    }
  },
  "terms": {
    "OnDemand": {
      "<sku>": {
        "<offerTermCode>": {
          "priceDimensions": {
            "<rateCode>": {
              "pricePerUnit": { "USD": "0.1920000000" }
            }
          }
        }
      }
    }
  }
}
```
- **Filter**: Only Linux/UNIX, Shared tenancy, `capacityStatus=Used`, `operatingSystem=Linux`

### AWS EC2 Spot Price History API
- **Source**: AWS SDK `ec2:DescribeSpotPriceHistory` per region
- **Frequency**: Every 15 minutes (configurable via `SPOT_PRICE_POLL_INTERVAL_MS`)
- **Format**: AWS SDK response:
```typescript
{
  SpotPrices: {
    InstanceType: string;
    AvailabilityZone: string;
    SpotPrice: string;         // string float, e.g. "0.0456"
    Timestamp: Date;
    ProductDescription: string;
  }[]
}
```
- **Filter**: `ProductDescription = 'Linux/UNIX'`

### AWS EC2 Instance Types API
- **Source**: AWS SDK `ec2:DescribeInstanceTypes`
- **Frequency**: Weekly refresh or on-demand when unknown instance type encountered
- **Format**: AWS SDK `InstanceTypeInfo[]`

## Outputs

### Database Writes
| Table | Write Pattern |
|---|---|
| `on_demand_prices` | Upsert on `(instance_type, region)` — update `price_usd_hr` and `updated_at` |
| `spot_prices` | Insert new row per poll per `(instance_type, region, az)` — retain history |
| `instance_catalog` | Upsert on `instance_type` — update all columns |

### Redis Cache (Spot Prices)
After each successful spot price poll, write:
- Key: `price:{instance_type}:{az}` — Value: `{ spotPriceUsdHr: float, collectedAt: ISO string }` — TTL: `600` seconds (10 minutes)
- Key: `price:ondemand:{instance_type}:{region}` — Value: `{ priceUsdHr: float }` — TTL: `86400` seconds (24 hours)

These keys are read by `recommendations` during savings estimation to avoid a DB round-trip.

### No Events Published
This module does not publish NATS events. Pricing data availability is assumed eventually consistent by downstream modules.

## Events Produced
N/A — pricing data is background-refreshed on a schedule. No events are emitted on price updates.

## Events Consumed
N/A — this module is entirely schedule-driven. It does not subscribe to NATS events.

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `on_demand_prices` | `id`, `instance_type VARCHAR`, `region VARCHAR`, `price_usd_hr NUMERIC(10,6)`, `price_usd_month NUMERIC(10,4)`, `price_per_vcpu_hr NUMERIC(10,6)`, `price_per_gi_hr NUMERIC(10,6)`, `updated_at TIMESTAMPTZ` | Derived columns computed on write: `price_usd_month = price_usd_hr × 730`, `price_per_vcpu_hr = price_usd_hr / vcpu_count` (joined from instance_catalog) |
| `spot_prices` | `id`, `instance_type VARCHAR`, `region VARCHAR`, `az VARCHAR`, `price_usd_hr NUMERIC(10,6)`, `collected_at TIMESTAMPTZ` | Append-only; spot price history retained for savings trend analysis |
| `instance_catalog` | `instance_type VARCHAR PK`, `vcpu INT`, `memory_gi NUMERIC(8,3)`, `network_perf VARCHAR`, `family VARCHAR`, `gpu_count INT`, `gpu_model VARCHAR`, `bare_metal BOOL`, `burstable BOOL`, `updated_at TIMESTAMPTZ` | Single row per instance type; global (not per-region) |

### Indexes
- `spot_prices(instance_type, az, collected_at DESC)` — primary query for most recent spot price per AZ
- `on_demand_prices(instance_type, region)` — unique index (upsert key)
- Partial index `spot_prices WHERE collected_at > NOW() - INTERVAL '1 hour'` — for fast recent-price lookups

### Tables Read (Cross-Domain, Read-Only)
None — this module writes pricing tables and reads only from AWS APIs and Redis.

## APIs
N/A — this is a background worker module. It exposes no REST endpoints. All pricing data is accessed by other backend modules via direct database reads or Redis cache lookups.

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/logger` | Structured logging with `region`, `instanceType`, `pollType` context |
| `database` | PostgreSQL pool; upsert helpers for pricing tables |

### External Services
| Service | SDK / Endpoint | Purpose |
|---|---|---|
| AWS Pricing Bulk API | HTTP GET (no SDK auth required — public endpoint) | Fetch on-demand Linux pricing for each region |
| AWS EC2 | `@aws-sdk/client-ec2` `DescribeSpotPriceHistoryCommand` | Fetch current spot prices per region/AZ |
| AWS EC2 | `@aws-sdk/client-ec2` `DescribeInstanceTypesCommand` | Populate instance type catalog |
| Redis | `ioredis` SET with EX | Cache current spot and on-demand prices for low-latency reads |
| BullMQ | `bullmq` | Schedule recurring poll workers (`pricing-ondemand-worker`, `pricing-spot-worker`, `pricing-catalog-worker`) |

### Sub-Modules
| Sub-Module | Responsibility |
|---|---|
| `on_demand` | Fetch and parse AWS Pricing bulk JSON; filter to Linux/Shared/Used; upsert into `on_demand_prices` |
| `spot_price` | Call `DescribeSpotPriceHistory`; parse spot prices; insert rows; update Redis cache |
| `instance_catalog` | Call `DescribeInstanceTypes`; map to catalog schema; upsert into `instance_catalog` |
| `normalization` | Unit conversions: $/hr → $/month (×730), per-vCPU, per-GiB breakdowns |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `PRICING_POLL_CRON` | `0 2 * * *` | Cron for on-demand price refresh (2 AM UTC daily) |
| `SPOT_PRICE_POLL_INTERVAL_MS` | `900000` | Spot price poll interval in ms (15 minutes) |
| `CATALOG_REFRESH_CRON` | `0 3 * * 0` | Cron for instance catalog refresh (weekly, Sunday 3 AM UTC) |
| `PRICING_REGIONS` | `us-east-1,us-west-2,eu-west-1,ap-southeast-1` | Comma-separated AWS regions to collect pricing for |
| `PRICING_INSTANCE_FAMILIES` | `m,c,r,t,i,g,p,x` | Instance family prefixes to include in catalog |
| `SPOT_PRICE_REDIS_TTL` | `600` | Spot price Redis cache TTL in seconds |
| `ONDEMAND_PRICE_REDIS_TTL` | `86400` | On-demand price Redis cache TTL in seconds |
| `PRICING_HTTP_TIMEOUT_MS` | `30000` | Timeout for AWS Pricing bulk JSON HTTP fetch |
| `PRICING_BULK_JSON_BASE_URL` | `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current` | Base URL for AWS Pricing bulk API |
| `AWS_REGION` | `us-east-1` | AWS region for EC2 API calls (platform-side) |

## Error Handling

| Scenario | Behavior |
|---|---|
| AWS Pricing bulk JSON fetch fails (HTTP error) | Retry 3× with exponential backoff (1s, 2s, 4s). On persistent failure, log `PRICING_ONDEMAND_FETCH_FAILED` and skip this region for this cycle; existing DB rows remain valid |
| `DescribeSpotPriceHistory` fails | Retry 3× with exponential backoff. On failure, log `PRICING_SPOT_FETCH_FAILED`; Redis TTL protects stale data for up to 10 minutes; after TTL expiry, recommendation engine falls back to DB query for most recent row |
| Redis SET fails after successful DB write | Logged as `PRICING_REDIS_CACHE_FAILED`; DB row is authoritative; downstream reads fall back to DB |
| Unknown instance type in spot price response | Trigger immediate `DescribeInstanceTypes` lookup for the unknown type; add to catalog before upserting spot price |
| On-demand price not found for an instance type | Logged as `PRICING_ONDEMAND_MISSING`; `on_demand_prices` row remains stale; savings estimate will show `null` for savings_usd_month for that workload |
| BullMQ worker job failure | Retried up to 3×. On exhaustion, moved to `dead_letter_jobs`; admin notification created |

## Future Enhancements
- **Reserved Instance / Savings Plan pricing**: Ingest AWS Reserved Instance and Compute Savings Plan pricing as additional comparison points alongside on-demand and spot
- **GCP and Azure pricing**: Extend the module to support GCP Preemptible VM and Azure Spot VM pricing for multi-cloud support
- **Graviton / Arm pricing**: Explicitly track `arm64` pricing separately and include in instance catalog for workloads that are architecture-agnostic
- **Price alert events**: Publish a NATS event when a spot price rises above on-demand price (spot price inversion) to trigger recommendation recomputation
- **Per-org regional scope**: Restrict pricing collection to only the regions where an org has active clusters, reducing unnecessary API call volume

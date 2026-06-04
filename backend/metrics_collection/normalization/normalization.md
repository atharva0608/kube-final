# Metrics Collection: Normalization

## Purpose
Standardizes disparate metrics units into the BalanceKube unified data model.

## Responsibilities
- Normalizes CPU metrics to millicores (`m`). `1 CPU = 1000m`. Handles inputs in nanocores (`n`).
- Normalizes Memory metrics to Mebibytes (`MiB`). Handles inputs in bytes.
- Normalizes Network throughput to Kilobits per second (`Kbps`). Handles bytes per interval.
- Normalizes Filesystem storage to Gibibytes (`GiB`).

## Inputs
- Source: Raw metrics from ingestion handlers.
- Format: Native Kubelet types.

## Outputs
- Destination: Database metrics tables.
- Format: Normalized floats.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- N/A

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A

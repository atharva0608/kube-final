# Workload Classification: Unknown Detection

## Purpose
Fallback categorization for unidentifiable workloads.

## Responsibilities
- Evaluates workloads that matched no other specific tags.
- Applies the `unknown` tag.
- Flags these workloads for mandatory operator review, as the system cannot safely infer their constraints.

## Inputs
- Source: Workload manifest and tag results from other detectors.
- Format: JSON.

## Outputs
- Destination: Tag generator.
- Format: Tag struct.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Relies on being the last detector evaluated.

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- Integration with an LLM to guess the workload type based on environment variables and open-source GitHub image labels.

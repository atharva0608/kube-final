# Workload Classification: Java Detection

## Purpose
Heuristic detector for Java workloads.

## Responsibilities
- Inspects container image names for substrings: `java`, `jdk`, `jre`, `openjdk`, `corretto`, `temurin`, `graalvm`, `azul`, `zulu`.
- Inspects environment variables for JVM tuning keys: `JAVA_OPTS`, `JVM_OPTS`, `JAVA_TOOL_OPTIONS`, `JAVA_HOME`.
- Applies the `java` tag if matches are found.

## Inputs
- Source: Workload manifest.
- Format: JSON.

## Outputs
- Destination: Tag generator.
- Format: Boolean or Tag struct.

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

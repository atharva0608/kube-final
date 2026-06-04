# Spot Risk Collection: AWS Spot Advisor

## Purpose
Integration parser for the AWS Spot Instance Advisor data source.

## Responsibilities
- Strips the JSONP wrapper (`callback(...)`) from the raw `spot.js` file fetched from S3.
- Parses the resulting JSON structure to extract regional frequency bands.

## Inputs
- Source: Raw string from `https://spot-price.s3.amazonaws.com/spot.js`.
- Format: JSONP string.

## Outputs
- Destination: Interruption Rates sub-module.
- Format: Array of interruption data objects.

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
- Fails gracefully if AWS changes the JSONP wrapper format.

## Future Enhancements
- N/A

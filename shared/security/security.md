# Shared: Security

## Purpose
Cryptographic utilities and authorization helpers.

## Responsibilities
- AES-256-GCM encryption and decryption for sensitive fields (e.g., AWS Role ARNs, Webhook URLs).
- SHA-256 hashing functions for API keys and Agent tokens.
- Password hashing using `bcrypt`.
- JWT token signing and verification logic.

## Inputs
- Source: Plaintext strings or objects.
- Format: Strings.

## Outputs
- Destination: Cyphertext, hashes, JWTs.
- Format: Strings.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Node.js `crypto` module.
- `bcrypt`
- `jsonwebtoken`

## Configuration
- `ENCRYPTION_KEY`: Master key for AES-256-GCM.
- `JWT_SECRET` or private key for RS256.

## Error Handling
- Throws decryption errors if ciphertext is tampered with.

## Future Enhancements
- AWS KMS integration for envelope encryption.

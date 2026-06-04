# Infrastructure: Network

## Purpose
Network topology and ingress configuration.

## Responsibilities
- Manages AWS Load Balancer Controller configurations.
- Configures Ingress resources, TLS termination (via ACM or cert-manager), and WAF rules.
- Defines NetworkPolicies to restrict cross-namespace and cross-pod communication.

## Inputs
- Source: IaC and Helm values.
- Format: YAML.

## Outputs
- Destination: AWS ALB, K8s CNI.
- Format: Cloud resources and CNI rules.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- AWS ALB Controller.

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- Service mesh (Istio/Linkerd) for internal mTLS.

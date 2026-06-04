# Frontend: Components

## Purpose
Reusable UI components.

## Responsibilities
- Implements the design system (buttons, inputs, modals, tables, badges).
- Encapsulates complex domain-specific UI (e.g., Topology Graph, Savings Estimator Card).
- Maintains strict separation between presentational components and container/smart components.

## Inputs
- Source: React props.
- Format: Strongly-typed TypeScript interfaces.

## Outputs
- Destination: DOM.
- Format: JSX/HTML.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Radix UI / Headless UI (for accessible primitives).
- Tailwind CSS.
- Lucide React (icons).

## Configuration
- N/A

## Error Handling
- Component-level error boundaries for complex visualizers.

## Future Enhancements
- Storybook integration for component documentation.

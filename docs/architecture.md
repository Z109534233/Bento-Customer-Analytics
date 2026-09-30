# Architecture

The original team system was a web-based analytics dashboard connected to POS/order data. The public portfolio edition deliberately separates the analytical logic from the private operational environment.

```mermaid
flowchart LR
    A[POS / Order Data] --> B[Private ingestion layer]
    B --> C[(Relational database)]
    C --> D[RFM segmentation]
    C --> E[Repurchase analysis]
    C --> F[Annualised customer value]
    C --> G[Churn heuristic]
    C --> H[Market basket analysis]
    D --> I[Dashboard]
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[Optional AI interpretation layer]
```

## Original stack

- PHP dashboard and server-side aggregation
- MySQL-compatible relational database
- Python automation jobs
- HTML/CSS/JavaScript dashboard components
- Gemini-based interpretation layer using environment variables for API credentials

## Public edition

- Python + pandas for reproducible analytics
- Synthetic demonstration data only
- No production URLs, credentials, customer names, phone numbers or deployment keys
- SQL schema rewritten around anonymous `customer_id`

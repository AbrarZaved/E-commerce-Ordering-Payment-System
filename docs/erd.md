# Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ ORDERITEM : contains
    ORDER ||--o{ PAYMENT : "paid via"
    PRODUCT ||--o{ ORDERITEM : "referenced by"
    CATEGORY ||--o{ PRODUCT : categorizes
    CATEGORY ||--o{ CATEGORY : "parent of"

    USER {
        bigint id PK
        string email UK
        string full_name
        bool is_staff
        bool is_active
        datetime date_joined
    }
    CATEGORY {
        bigint id PK
        string name
        string slug UK
        bigint parent_id FK
    }
    PRODUCT {
        bigint id PK
        string name
        string sku UK
        text description
        decimal price
        int stock
        string status
        bigint category_id FK
    }
    ORDER {
        bigint id PK
        bigint user_id FK
        decimal total_amount
        string status
        datetime created_at
    }
    ORDERITEM {
        bigint id PK
        bigint order_id FK
        bigint product_id FK
        int quantity
        decimal price
    }
    PAYMENT {
        bigint id PK
        bigint order_id FK
        string provider
        string transaction_id UK
        string status
        decimal amount
        json raw_response
    }
```

## Notes
- `Category.parent_id` is a self-referential FK enabling an arbitrary-depth tree.
- `OrderItem.price` is snapshotted at order time (immune to later product price edits).
- `OrderItem` has a unique `(order, product)` constraint; combine quantities instead of duplicate rows.
- `Payment.transaction_id` is unique per provider reference, enabling idempotent webhook lookups.

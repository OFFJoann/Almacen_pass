flowchart TD
    U["👤 Usuario<br/>(Navegador)"] -->|"HTTPS / TLS (ALB)"| W

    subgraph WEB["Capa Web — Django"]
        W["Django + Cabeceras<br/>HSTS · CSP · X-Frame DENY"]
        A["Login + MFA<br/>(django-otp)"]
        AX["Bloqueo intentos<br/>(Axes)"]
        S["Sesión<br/>Cookie Secure/HttpOnly"]
        W --> A --> AX --> S
    end

    S -->|"Vistas web"| E
    S -->|"Token (DRF)"| API

    subgraph APIG["APIs — DRF"]
        API["/api/entries<br/>TokenAuth + IsAuthenticated"]
        API --> E
    end

    subgraph ENC["Capa de Cifrado (en el servidor)"]
        E["AES-GCM<br/>password/TOTP: Argon2id<br/>usuario/notas: AES-GCM rápido"]
        K["🔑 Clave maestra<br/>derivada de SECRET_KEY<br/>(no zero-knowledge)"]
        E -.-> K
    end

    E -->|"ciphertext + nonce + salt"| DB
    E --> R

    subgraph STORE["Almacenamiento"]
        DB[("Postgres<br/>columnas *_encrypted<br/>(solo ciphertext)")]
        R[("Redis<br/>sesiones + caché")]
    end

    W --> AU["Auditoría + Historial<br/>(cada acción se registra)"]

    style U fill:#e1f0ff,stroke:#036
    style K fill:#ffe1e1,stroke:#900
    style DB fill:#e8ffe8,stroke:#060
    style R fill:#fff4e1,stroke:#960
    style ENC fill:#f3e8ff,stroke:#609

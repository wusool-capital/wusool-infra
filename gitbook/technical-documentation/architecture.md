# Architecture diagram

This is the current high-level architecture of the Wusool platform. It shows the shared Toolkit backend, external entry points, data stores, cloud services, and operational dependencies.

![Wusool platform architecture](../.gitbook/assets/wusool-platform-architecture.png)

## Interactive diagram

The interactive Archify version is served from the Toolkit EC2 host and protected by Basic Auth:

[Open the interactive architecture diagram](https://tools.wusoolcapital.com/architecture/)

Use the shared `architecture` username and the memorable phrase provisioned in the Toolkit Secrets Manager secret. Never commit or paste the phrase into this repository.

Source artifact: `docs/internal/architecture/wusool-platform.html`.

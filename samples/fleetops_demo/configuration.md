# FleetOps Configuration Manual

Version: 2.0. FICTIONAL DEMONSTRATION MATERIAL — examples are not executed by KnowledgeBridge.

## File location

The fictional deployment uses a fleetops.yaml file in its administrator-managed configuration directory. KnowledgeBridge does not read this path, change this file or start a service.

## Authentication settings

```yaml
require_mfa: true
session_idle_minutes: 30
api_page_size: 100
```

These are documented FleetOps 2.0 defaults. Set require_mfa explicitly during provisioning. The legacy configuration guide documents 1.0 defaults of false and 60; confirm the installed release and authoritative deployment policy before changing anything.

## Apply configuration

1. Validate the YAML using the FleetOps deployment team's documented process.
2. Schedule a maintenance window.
3. Restart the fictional API worker.
4. Open Administration > Security and verify the displayed settings.

## Missing specifications

This sample does not establish high-availability behavior, live reload support, accepted TLS cipher suites or disaster-recovery objectives. Future answering should identify that missing evidence.

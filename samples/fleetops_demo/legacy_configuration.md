# FleetOps Legacy Configuration Guide

Version: 1.0. FICTIONAL LEGACY DEMONSTRATION MATERIAL — retained intentionally for version-conflict evaluation.

## Authentication defaults

In the FleetOps 1.0 documentation, require_mfa defaults to false. This is a historical statement, not a recommendation to disable authentication controls. Consult the current deployment policy before interpreting this legacy value.

## Session lifetime

The documented session_idle_minutes default is 60 minutes. The 2.0 Configuration Manual states 30. These passages deliberately disagree by version and must remain distinguishable by source metadata.

## Report submission

The old client example uses POST /v1/report/submit. This guide does not establish whether that path remains supported by FleetOps 2.0.

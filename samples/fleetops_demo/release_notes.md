# FleetOps Release Notes

Version: 2.0. FICTIONAL DEMONSTRATION MATERIAL.

## Authentication changes

FleetOps 2.0 changes the documented require_mfa default from false to true for newly provisioned workspaces. Previously created workspaces keep their configured value. A release number does not by itself establish a specific workspace's security configuration.

## Session timeout change

The documented session_idle_minutes default for new workspaces is now 30, compared with 60 in the 1.0 Legacy Configuration Guide. Existing explicit values are retained during upgrade.

## API changes

The report submission endpoint is POST /v2/reports/{report_id}/submit. Clients must not infer this path from the old /v1/report/submit example. Review the current API Reference before changing a client.

## Known documentation gaps

Recovery-code management, automatic retry semantics and audit-event retention remain unspecified in this demonstration set. Do not invent values when the documentation does not establish them.

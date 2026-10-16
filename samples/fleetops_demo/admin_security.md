# FleetOps Administrator Security Guide

Version: 2.0. FICTIONAL DEMONSTRATION MATERIAL — not instructions for any real service.

## Administrator access

FleetOps administrators manage workspace security from Administration > Security. Only the fictional workspace-owner role can change organization-wide authentication settings. Verify the workspace name before making a change.

## Multi-factor authentication

For FleetOps 2.0, open Administration > Security > Authentication and set require_mfa=true. New administrator sessions must complete the configured second-factor enrollment. Existing active sessions keep their original expiry until revoked. The sample does not establish recovery-code regeneration behavior.

## Session lifetime

The FleetOps 2.0 default idle timeout is 30 minutes. Set session_idle_minutes in the configuration file and restart the fictional API worker to apply it to new sessions. The legacy 1.0 guide describes a different default; do not assume version labels alone establish authority for a deployed environment.

## Audit events

Security changes create an admin.security.updated event containing the workspace identifier and changed setting names. This fictional manual does not specify event retention or export destination.

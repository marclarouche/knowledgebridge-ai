# Recorded sample questions and answers

These are actual outputs from the October 16 fictional development run, not a live demonstration or human-validated answers. The run used a 60-second generation-request budget. Passage IDs identify that historical snapshot; a new index generation can invalidate navigation. See [full evidence](evidence/milestone5/knowledgebridge-m5-evaluation.json) and [evaluation limitations](evaluation_report.md).

## RQ-001: What does AUTH_REQUIRED mean?

Status: `answered`. Reason: `support_review_passed`. Elapsed: 60.2 seconds.

Requests without a valid workspace token return HTTP 401 with code AUTH_REQUIRED.

Source: FleetOps API Reference, version 2.0, `api_reference.md`, section Authentication. Passage `14f4ddf3-1104-54d0-8828-252fd0761e3f`; quote offsets [114, 195) within the passage.

> Requests without a valid workspace token return HTTP 401 with code AUTH_REQUIRED.

## RQ-003: What is the maximum page_size?

Status: `answered`. Reason: `support_review_passed`. Elapsed: 36.5 seconds.

The maximum page_size is 100.

Source: FleetOps API Reference, version 2.0, `api_reference.md`, section Read work orders. Passage `ebd37191-81ce-561b-87c1-49605e24415a`; quote offsets [91, 120) within the passage.

> The maximum page_size is 100.

## RQ-027: How can I regenerate recovery codes?

Status: `insufficient_evidence`. Reason: `missing_evidence`. Elapsed: 55.6 seconds.

I couldn't find sufficient information in the indexed documentation to answer that question.

No citations returned. This output does not establish a substantive answer.

## RQ-031: What is the default session_idle_minutes? Both legacy and current guides are present and the deployed version is unknown.

Status: `generation_failed`. Reason: `model_timeout`. Elapsed: 60.3 seconds.

The local answer service could not complete this request. Check Ollama and the configured models; your saved index is unchanged.

No citations returned. This output does not establish a substantive answer.

The failed conflict example is deliberately retained. The system did not return the expected conflict status; withholding an invalid draft is not successful conflict detection. Successful examples do not establish overall quality, and same-model support review remains fallible.

# FleetOps API Reference

Version: 2.0. FICTIONAL DEMONSTRATION MATERIAL. API examples are inert text.

## Authentication

Send an Authorization: Bearer <example-token> header. The literal example is not a credential. Requests without a valid workspace token return HTTP 401 with code AUTH_REQUIRED. This manual does not describe token creation or rotation.

## Submit a report

POST /v2/reports/{report_id}/submit submits a draft maintenance report for supervisor review. The operation does not publish the report or delete its draft data. A successful request returns HTTP 202 and status review_pending.

```json
{"report_id": "DEMO-104", "status": "review_pending"}
```

## Read work orders

GET /v2/work-orders accepts equipment_id and status query parameters. The maximum page_size is 100. The next_cursor value is opaque: pass it unchanged for another page.

## Error responses

REPORT_LOCKED means a supervisor review is already open. Inspect the report status before attempting another submission. The example does not establish whether retrying a failed network request is idempotent; ask the API owner before automating retries.

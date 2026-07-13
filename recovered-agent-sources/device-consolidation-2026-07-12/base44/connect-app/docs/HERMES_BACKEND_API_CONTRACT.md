

```http
GET  /health
GET  /jarvis/status
POST /jarvis/classify
POST /jarvis/handle
POST /work-packets/validate
POST /owner/authorize
GET  /jobs
POST /jobs
GET  /jobs/:id
GET  /models/routes
POST /models/route
GET  /memory/candidates
POST /memory/candidates/:id/approve
POST /memory/candidates/:id/reject
```

## Security boundary

Base44 may request actions. Hermes decides whether the action is allowed. For high-risk work, Hermes must require exact owner authorization before executing.

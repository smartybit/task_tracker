# Environment Deployment and Operations

The user requested three or more independent environments on 2026-10-19:

| Role | Purpose | Data policy |
| --- | --- | --- |
| Production | Real work, after production acceptance | Persistent; separate activation |
| Evaluation | User testing and evaluation of a selected release | Persistent; agent checks must not reset or upgrade it |
| Agent | Development, exploration and verification | Separate data; additional named environments may be created |

This Stage 11 milestone prepares evaluation and agent deployments. Production
activation and full Stage 11 operational acceptance remain separate work.

## Selected Implementation Defaults

- One Compose project per named environment, with its own PostgreSQL database,
  uploads, network, Django secret and image namespace.
- Gunicorn runs Django with debug disabled. A separate Nginx container serves the
  built frontend and forwards only the matching prefixed API paths. Node/Vite
  development servers remain available through the existing development setup.
- Evaluation uses `/time-tracker-eval/` on loopback port 8181; the first persistent
  agent environment uses `/time-tracker-agent/` on loopback port 8182. Production
  reserves `/time-tracker-prod/`; it is not activated by this milestone.
- Loopback HTTP is for SSH-tunnel access. Public HTTPS requires an explicit origin
  and host-proxy configuration that preserves the application mount. Existing
  public host configuration is inspected but not changed during preparation.
- Named, versioned builds isolate releases: rebuilding an agent environment does
  not change evaluation images or its next restart. Updates target an explicit
  environment name. Existing disposable test projects stay separate.

These are implementation defaults, not a claim that public hosting or full
backup/restoration acceptance is complete. Verified commands, actual deployment
state and outstanding work will be recorded here as implementation progresses.

## References

- [Multiple-instance routing and trust contract](multiple_instances.md).
- [Agreed backup policy](../architecture.md#agreed-backup-and-restoration-policy).
- [Django deployment guidance](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [Gunicorn proxy settings](https://gunicorn.org/reference/settings/).
- [Nginx proxy URI handling](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).

# Remarks API

Stage 8 adds plain-text remarks and shared stars. Reference and image tokens and
the optional `images` field on create/edit are documented in
[content_api.md](content_api.md), together with search. Internal paths below begin
with `/api/v1/`; external requests prepend the configured application mount
as described in [instance configuration](multiple_instances.md). All routes
require an authenticated session. Writes also require CSRF protection.

| Operation | Path | Input / response |
| --- | --- | --- |
| List conversation | `GET tasks/{task_id}/remarks/` | Standard `count`, `next`, `results` pagination; 50 per page in ascending creation-time/UUID order |
| List shared stars | `GET tasks/{task_id}/remarks/?starred=true` | Same ordering and pagination, restricted to starred remarks |
| Read one remark | `GET remarks/{id}/` | Current remark |
| Post | `POST tasks/{task_id}/remarks/` | `{ "body": "Text" }`; returns 201 |
| Edit | `PATCH remarks/{id}/` | `{ "body": "Corrected text", "expected_revision": 0 }` |
| Set shared star | `POST remarks/{id}/star/` | `{ "starred": true, "expected_revision": 1 }` |
| Delete permanently | `DELETE remarks/{id}/` | `{ "expected_revision": 2 }`; acknowledgement |

Readable remarks include `id`, `task`, `author`, `author_name`, `body`, `starred`,
`created_at`, `edited_at`, and `revision`. The original author and creation time
survive edits by other authorized users. Text edits set `edited_at`; star changes
leave that timestamp unchanged. Text is stored without trimming, but empty or
whitespace-only bodies are invalid. The browser renders text literally, including
line breaks; it does not interpret HTML. Unknown mutation fields are rejected.

Reads require task read **and** remark read permission for the containing task's
current project. Posting, editing, deleting, and starring require task read
**and** remark write; neither task write nor authorship is required. Organization
and project grants are additive. Administrators and task owners have no bypass.
Remark write without remark read is supported: successful writes return only
`id` and `revision`. The browser offers a composer in this case but hides the
conversation and its controls. Unavailable reads return a generic 404.

Every write locks the shared domain coordination row before checking current
permissions, containment, and revisions. Competing edits/stars/deletions cannot
silently overwrite each other. A stale revision returns `409 stale_revision`
without changing remark data or the domain revision. Read endpoints hold that
same lock while authorizing and serializing one page, so an individual response
uses a consistent permission/content state. Separate pages are separate reads.

Eligible task deletion requires task write and, when remarks exist, task read
plus remark write. The deletion preview's `delete.remarks` field gives the number
of remarks that will be removed, without exposing bodies or authors. Confirmed
deletion cascades into remarks; intervening remark changes invalidate the
domain-revision preview. Child tasks and time records still prevent deletion.

The task window loads all conversation pages and derives its separate starred
list in chronological order. Star links focus and scroll to the original remark.
Failed writes retain unsaved text. Stale or denied writes require explicit reload
and review; reloading confirms disposal of a changed edit. A successful write
followed by a failed reload is reported as saved and requires reload before
another write. Reloading retains the new-remark draft. Leaving/reloading the page
warns about unsaved text; closing or switching tasks ends that task window's local
draft. Cross-task draft persistence is not implemented in this milestone.

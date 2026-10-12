# Content API

All routes are under `/api/v1/` and require an active signed-in session. POSTs
require CSRF. Task and remark write routes retain their existing revision and
confirmation contracts; references do not create another write route.

## References

Descriptions and remark bodies remain plain text, with inline tokens
`[task:UUID]` and `[remark:UUID]`. The browser offers an accessible picker that
lists readable tasks, then readable remarks for the selected task. Inserting a
token replaces the textarea selection and returns focus to the textarea. Other
text, including HTML, is escaped. There is no arbitrary HTML or Markdown rendering.

Source writes transactionally synchronize a deduplicated set of `Reference`
records. Exactly one task or remark owns each record. Target UUIDs deliberately
have no foreign keys: renames/moves preserve them and deletion leaves a placeholder.
Unknown or restricted IDs may be stored without probing their existence. Removing
tokens removes their source records; deleting a source cascades its records.
Migration backfills tokens already present without changing source revisions.

`POST references/resolve/` accepts
`{"targets": [{"kind": "task", "id": "UUID"}]}`, with at most 100 targets.
Kinds are `task` or `remark`; unknown fields and malformed values return 400.
The response is `{"results": [...]}` in request order. Readable targets include
`kind`, `id`, `available: true`, `task` (the task window to open), and `label`
(current task title or a 120-character remark preview). Remark targets require
both task read and remark read; task targets require task read. Administrator
status provides no bypass. Reads hold the domain lock without advancing revision.

Restricted and deleted targets both return only `kind`, `id`, `available: false`,
and `label: "Unavailable reference"`; no title, author, snippet, or task location
is exposed. Browser links open the current task and focus the original remark,
rechecking destination permissions. Refresh references resolves labels again;
failed resolution offers a retry. Star previews show `Reference` for a token;
their links still navigate to the original source remark.

Images and multilingual search are still under implementation in Stage 8.

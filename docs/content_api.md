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

## Images

Task create/edit and remark create/edit accept optional `images`, an array of at
most five new uploads: `{"id": "new UUID", "data": "base64 bytes"}`. Each ID
must occur as `[image:UUID]` in the submitted description/body. IDs cannot be
reassigned. The editor selects files or accepts screenshot clipboard files and
adds these tokens at the cursor. It sends the images with the ordinary source
save, retaining text and pending uploads on failure. Remove a token to discard a
pending upload or delete an existing image. There is no separate attachment area.

The 2 MiB limit is inclusive, measured on decoded upload bytes. Pillow verifies
and decodes actual static PNG/JPEG/WebP content; filename and client MIME are not
trusted. Animated images and images above 20 million pixels are rejected.
Malformed base64, duplicate IDs, missing tokens and extra fields are invalid.
JSON transport uses base64; requests have a 16 MiB body budget. More than five
images can belong to a source; save additional batches separately.

Files use server-generated paths under `UPLOAD_ROOT`; PostgreSQL metadata has
exactly one source. Uploads, body changes, metadata and revisions form one domain
mutation. Failed mutations remove newly written files; old files are removed
only after a committed token/source deletion. Task-deletion previews count images
in both the description and its remarks. Write-only saves return the existing
safe acknowledgement without image details.

`GET images/UUID/` streams bytes after checking the source's current read access:
task read for descriptions; task read plus remark read for remarks. Moves and
revocation take effect on the next request. Missing/restricted images return 404;
anonymous requests are denied. Responses use the verified image MIME, safe UUID
filename, `nosniff`, and `Cache-Control: private, no-store`. No public upload URL
is configured. Unavailable inline images show a generic placeholder; Refresh
images retries the download. Existing displayed browser pixels cannot be recalled.

Development Compose stores uploads in the `development-uploads` named volume,
initialized for the application UID 1000. Tests use isolated temporary storage.
After a process crash or a failed cleanup callback, run
`python manage.py prune_content_images`: under the domain lock it removes orphan
files older than one hour and reports missing referenced files. It preserves recent
and referenced files. Back up PostgreSQL and uploads consistently; the full backup
and restoration procedure remains Stage 9 work.

Multilingual search is still under implementation in Stage 8.

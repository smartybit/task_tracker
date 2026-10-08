# Task Tracking Tool: Architecture

This document records selected technologies and implementation proposals.
[requirements.md](requirements.md) defines product behavior and business rules;
[testing_charter.md](testing_charter.md) defines verification priorities.
Proposals below preserve the approaches discussed so far and remain revisable.

## Accepted Decisions

- Backend: Python 3.13, Django 5.2 LTS, and Django REST Framework.
- Web frontend: React, TypeScript, and Vite.
- PostgreSQL is the only database engine, used for development, testing, and
  deployment. Cross-engine portability and migration are outside the scope.
- The first frontend is a web application. The architecture must allow additional
  frontends to use the same backend later.
- Permission checks, business rules, and report calculations are owned by the
  backend API so every client receives the same behavior.
- The deployment target is the current VDS where development is taking place.

## Proposed Application Structure

- Use one backend application with modules for accounts, access control,
  organizations/projects, tasks, remarks/images, timesheets, and reporting.
- Keep business operations in shared backend services so API endpoints, management
  screens, and future clients enforce consistent rules.
- Expose a versioned REST API with explicit request/response contracts. Keep API
  types and reusable client utilities separate from browser-specific components.
- Serve the React application as static assets and use the Django API for data.
- Use session authentication for the web application with the corresponding
  request protections. Select a native-client authentication mechanism when a
  mobile app is scoped; mobile requests must use the same authorization rules.
- Implement the application's administrator role with explicit data grants in
  every interface, including management screens. Catalog/account administration
  must not accidentally grant unrestricted access to tasks or time records.

## Proposed Data and Transaction Approach

- Model organizations, projects, tasks, statuses, users, access grants, remarks,
  images, and timesheet entries as related records with stable identifiers.
- Represent the task hierarchy with parent relationships. Enforce common-project
  and acyclic-hierarchy rules through the business operations that change the tree.
- Keep a status's first-use marker so immutability does not depend on whether
  any task still references it. Record task status changes while the task exists.
- Persist a running entry's start timestamp with an unset end timestamp. Compute
  its report duration as zero; closing the entry establishes its duration.
- Represent time intervals as start-inclusive and end-exclusive. Chronological
  segments are bounded by neighboring start times and an optional closing boundary.
  Split closed overnight work at exactly midnight in the configured working zone.
- Use database transactions for timesheet neighbor adjustments, ancestor reopening,
  hierarchy/project changes, and deletion checks. Complete each operation together
  or roll it back completely.
- Serialize competing edits to a user's timesheet by locking a persistent
  per-user timesheet record for the transaction. Protect hierarchy and deletion
  operations against concurrent changes with suitable locking and constraints.
- Treat source timestamps and current task relationships as authoritative. Derive
  totals from them rather than maintaining independent totals that can become stale.

## Proposed Reporting Implementation

- Build a shared authorized-record query that restricts projects and timesheet
  users according to the reporting rules in the requirements. Apply access
  restrictions before aggregation and consistently reuse them for CSV export.
- Calculate durations from closed entries, treating open entries as zero and
  excluding taskless entries from work reports and CSV.
- Use database aggregation for project and person/day summaries and direct hours
  per task. Compute descendant rollups from the task tree and direct totals in a
  batch, avoiding a separate database request for every node.
- Resolve project attribution through each task's current project and rollups
  through its current ancestors. Historical edits and moves affect later queries.
- Calculate reports on request initially. Add caching or precomputed summaries
  only if measured performance requires them and invalidation rules are defined.
- Sum original durations before converting to decimal hours and rounding output.
- Return structured report data to the frontend. Stream individual authorized
  records to CSV for the selected period, independently of interactive filters.
- Verify report results against independently calculated examples and exercise
  permission boundaries and concurrent mutations using PostgreSQL.

## Proposed Images and Content Handling

- Store image files in a persistent local volume, with metadata and ownership
  relationships in PostgreSQL. Images belong to descriptions or remarks, as
  specified in the requirements.
- Validate the actual image format and the selected upload size limit.
- Serve downloads through permission-checked endpoints, applying the containing
  task/remark's current permissions rather than exposing a public upload directory.
- Use stable identifiers for cross-references and resolve visibility on access.
  Keep file cleanup consistent with deletion of an eligible containing object.

## Proposed Deployment and Operations

- Use Docker Compose for reproducible development and VDS deployment.
- Keep runtime services to the backend, PostgreSQL, and a reverse proxy serving
  frontend assets and forwarding API requests. Select the application server and
  reverse proxy during deployment design.
- Build frontend assets in a build stage. Node.js is needed for frontend builds;
  the deployed browser application is served as static files.
- Persist database data and image files outside disposable application containers.
- Provide a local setup command to create the first administrator; account
  creation and password reset then follow the agreed administrator workflows.
- Define schema migration, startup, backup, and recovery procedures as deployment
  work progresses. Backup scope must account for both database data and image files.

## Future Android Frontend Options

No Android implementation has been selected or included in the first version.

- Make the initial web interface responsive and usable with touch input.
- Capacitor could package the web frontend as an Android application, reusing
  most browser UI code while adding native integrations where needed.
- React Native could provide a dedicated mobile interface using the same API,
  TypeScript data contracts, and suitable client utilities. Its native screen
  components would be built separately from the browser components.
- Choose between these options when Android workflows and native integrations
  are known. Offline editing would require additional synchronization and conflict
  rules; it is not an assumed capability of either approach.

## Open Technical and Operational Decisions

1. Who handles VDS backups, and what recovery procedure is expected?
2. Select the application server, reverse proxy, and any supplementary frontend
   libraries during implementation; these were not fixed by the stack decision.
3. Choose the deployment working time zone or fixed UTC offset, as identified
   in the requirements. Daylight-saving behavior remains outside product scope.

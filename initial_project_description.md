# Task Tracking Tool

## Purpose

The purpose of the application is to track the time spent, difficulties encountered, and decisions made while working on tasks.

Each task belongs to a user and may be part of a larger task. Tasks can therefore form a hierarchy.

A task has:
- a description;
- a status, such as **In Progress**, **Postponed**, or **Waiting for Customer Response**;
- a history of status changes.

A task can be assigned to a project, and each project belongs to an organization.

Each task should also have a notes or chat section where users can add remarks while working on the task. These remarks may describe progress, difficulties, open questions, or decisions made during the work.

The application should support multiple users.

The application should have a modular architecture. The first version should use a web application as the frontend. Mobile and desktop applications may be added as alternative frontends later.

PostgreSQL is the application's database engine.

## Task List and Timesheet

The user can view open tasks either as a hierarchical list or as a flat list. The task list can be filtered by project.

A timesheet section is displayed on the right-hand side of the interface. It contains three columns:
- Task
- Start Time
- End Time

The user can drag and drop a task into the timesheet. When this is done, a new row is created and the current time is recorded as the task's start time.

The user can adjust the start and end times manually.

When a new task is added to the timesheet, the end time of the previous task is automatically set to the start time of the new task.

Two special entries can also be added to the timesheet:
- **Break**
- **End of Working Day**

Their main purpose is to record the time when work on the previous task stopped.

The timesheet should have a **Day** field that filters the displayed timesheet entries by date.

Users must be able to edit past timesheets retroactively. For example, a user should be able to insert a task into a timesheet from several days ago, including between two existing entries.

When a task is inserted between existing entries, the system should adjust the surrounding entries so that no time intervals overlap.

## Task Remarks

A chat section is available in the task window.

The user can post arbitrary text as a remark. Each remark is stored together with:
- its author;
- its timestamp.

Remarks are displayed in chronological order, similarly to posts in a web forum.

Users should be able to mark remarks as **starred**. Starred remarks are also displayed in a separate section at the top of the task window, again in chronological order, so that important information is easy to find.

The user can click a remark in the starred list to jump to its original position in the main chronological stream of remarks.

## Cross-References

Users should be able to create cross-references to other tasks or remarks.

Cross-references may appear in:
- task descriptions;
- task remarks.

## Attachments

Users should be able to insert or attach images and screenshots to:
- tasks;
- task remarks;
- task descriptions.

## User Access Restrictions

Users can have either **Administrator** or **Regular User** privileges.

Administrators can configure access permissions for any user.

Every user, including administrators, has a list of organizations and/or projects for which they have access.

Permissions should be configurable separately for:
- tasks;
- timesheets;
- task remarks.

For each of these areas, access can be configured as none, read-only or read/write.

If access is granted at the organization level, the corresponding permission applies to all projects belonging to that organization.

If a user encounters a cross-reference to a task or remark that they are not allowed to access, the interface should indicate that the referenced object exists but is unavailable because of access restrictions.

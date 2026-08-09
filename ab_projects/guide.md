# Abdin Development Projects Guide

`ab_projects` is a development-team layer on top of native Odoo Projects. It
does not replace Odoo's project app. It keeps Odoo's projects, tasks, stages,
milestones, chatter, activities, timesheets, followers, and access behavior,
then adds the concepts a software team needs for day-to-day delivery.

The intended experience is:

```text
Project workspace
  -> project overview and health
  -> tasks grouped by the native Odoo workflow
  -> sprints for focused execution
  -> releases for launch scope
  -> reports for planning and delivery review
```

## Core Concepts

### Project

A project is still the native `project.project` record. The module extends it
with development-specific fields:

- Project Type: classification such as Web, Odoo, Backend/API, Internal Tool,
  or Maintenance.
- Technical Lead: the user responsible for technical direction.
- Project Health: Healthy, At Risk, or Critical.
- Health Note: context when the project is not healthy.
- Repository URL, Documentation URL, Staging URL, Production URL.
- Current Sprint, sprint count, release count, team members, and delivery
  metrics computed from tasks.

Project progress is computed from non-template tasks:

```text
completed non-template tasks / total non-template tasks
```

Completed tasks are detected using Odoo Project's native closed states.

### Task

A task is still the native `project.task` record. The module adds development
metadata:

- Task Type: Task, Bug, Feature, Improvement, or Technical Debt.
- Story Points: lightweight estimation size.
- Sprint: the focused execution cycle containing the task.
- Release: the release scope containing the task.
- Reviewer: user responsible for review.
- QA Responsible: user responsible for QA.
- Branch URL and Pull Request URL.
- Blocked flag and Blocked Reason.
- Technical Notes.
- Bug fields: Severity, Environment, Reproduction Steps, Expected Result, and
  Actual Result.

Changing a task's project automatically clears sprint or release links that
belong to another project. This prevents a task from being connected to a
sprint or release under the wrong project.

### Sprint

A sprint is an `ab.project.sprint` record. It groups tasks in a focused
development cycle for one project.

Sprint statuses:

- Planning
- Active
- Completed

A sprint has a start date, end date, goal, task list, and computed metrics:

- Planned Story Points
- Completed Story Points
- Task Count
- Remaining Tasks
- Completed Tasks
- Overdue Tasks
- Blocked Tasks
- Progress

The sprint end date must be on or after the start date.

### Release

A release is an `ab.project.release` record. It groups tasks into a launch or
version scope for one project.

Release statuses:

- Planned
- In Development
- Testing
- Released

A release has a target release date, description, task list, and computed
metrics:

- Task Count
- Completed Tasks
- Bugs
- Open Bugs
- Progress

Release progress is computed from completed tasks divided by all non-template
tasks in the release.

### Project Type

Project types are configured in `ab.project.type`. They are simple active
records used to classify projects and improve filtering. Default types include:

- Web
- Mobile
- Odoo
- Backend/API
- Internal Tool
- Maintenance

Only project managers or `ab_projects` administrators can create or edit
project types.

## Navigation

The module adds entries under the native Odoo Project app.

### Workspace

Path:

```text
Project -> Workspace
```

The workspace opens the project kanban/list/form flow. It is the main entry
point for reviewing projects and their health.

The project card focuses on:

- Project name
- Project type
- Health
- Progress

The full project form contains the deeper dashboard and team information.

### My Work

Path:

```text
Project -> Project Management -> My Work
```

My Work shows active tasks that need attention from the current user. A task is
included when it is not a template, not closed, and one of these is true:

- the current user is assigned to the task
- the current user is the reviewer
- the current user is the QA responsible

Default grouping is by sprint.

### Sprints

Path:

```text
Project -> Project Management -> Sprints
```

The sprint screen supports kanban, list, form, and graph views. It defaults to
active sprints.

Use this screen to:

- plan a sprint
- set sprint dates and goal
- review sprint progress
- open all sprint tasks
- identify blocked or overdue work

### Releases

Path:

```text
Project -> Project Management -> Releases
```

The release screen supports kanban, list, and form views.

Use this screen to:

- define release/version scope
- track readiness
- review bugs and open bugs
- open all release tasks
- maintain release notes

### Reports

Path:

```text
Project -> Reporting
```

The module adds:

- Development Tasks: pivot, graph, and list analysis for tasks by project and
  task type.
- Sprint Report: graph/list/form analysis for sprint story points.
- Bugs: bug-focused task analysis filtered to task type Bug.

### Configuration

Path:

```text
Project -> Configuration -> Project Types
```

This is available to project managers and `ab_projects` administrators.

## Project Form Flow

The project form adds three important development sections.

### Development Dashboard

The dashboard summarizes:

- Total Tasks
- Completed Tasks
- Overdue Tasks
- Blocked Tasks
- Progress
- Story Points
- Estimated Hours
- Logged Hours
- Current Sprint
- Team members

It also provides quick actions:

- Open Tasks
- Sprints
- Releases
- Open blocked tasks
- Open overdue tasks
- Open completed tasks

### Development Info

This section stores ownership and engineering links:

- Project Type
- Project Manager
- Technical Lead
- Start Date
- Target Date
- Project Health
- Health Note
- Repository URL
- Documentation URL
- Staging URL
- Production URL

### Team

The team page shows people involved and project tasks. Team members are
computed from:

- task assignees
- project manager
- technical lead

## Task Form Flow

The task form keeps the native Odoo task experience and adds two development
pages.

### Development

This page contains:

- Task Type
- Story Points
- Estimated Hours
- Logged Hours
- Sprint
- Release
- Reviewer
- QA Responsible
- Blocked
- Blocked Reason
- Branch URL
- Pull Request URL
- Technical Notes

The task header and kanban menu include a Toggle Blocked action. This flips the
blocked flag without changing the native task stage.

### Bug Details

This page appears when Task Type is Bug. It contains:

- Severity
- Environment
- Reproduction Steps
- Expected Result
- Actual Result

Use this page for bug context only. The task's actual workflow state still
comes from the native Odoo task stage/state.

## Kanban Behavior

The module improves cards visually but keeps Odoo's native behavior.

### Project Cards

Project cards are intentionally compact. They show the information needed to
scan a workspace quickly:

- project type
- health
- progress

Detailed metrics remain on the project form dashboard.

### Task Cards

Task cards show concise delivery signals:

- title
- story points
- task type
- bug severity, when applicable
- blocked badge, when blocked

Native Odoo task controls, priority, activities, assignees, and stage columns
remain available. The module does not create a separate Jira/Trello-style
workflow.

### Sprint And Release Cards

Sprint and release cards provide progress, count metrics, status badges, and
quick links into the related task scope.

## Metrics

### Project Metrics

Project metrics include all non-template tasks on the project.

- Total Tasks: all non-template tasks.
- Completed Tasks: tasks in Odoo closed states.
- Overdue Tasks: tasks with a deadline before now and not closed.
- Blocked Tasks: tasks where Blocked is enabled.
- Estimated Hours: sum of allocated hours.
- Logged Hours: sum of total hours spent.
- Story Points: sum of task story points.
- Progress: completed tasks divided by total tasks.

### Sprint Metrics

Sprint metrics include non-template tasks linked to the sprint.

- Planned Story Points: sum of linked task story points.
- Completed Story Points: sum of story points for closed linked tasks.
- Remaining Tasks: linked tasks minus closed linked tasks.
- Overdue Tasks: linked tasks with overdue deadlines and not closed.
- Blocked Tasks: linked tasks marked blocked.
- Progress: completed linked tasks divided by total linked tasks.

### Release Metrics

Release metrics include non-template tasks linked to the release.

- Task Count: all linked tasks.
- Completed Tasks: linked tasks in closed states.
- Bugs: linked tasks with Task Type = Bug.
- Open Bugs: linked bug tasks that are not closed.
- Progress: completed linked tasks divided by total linked tasks.

## Permissions

The module defines three project roles:

- Project User
- Project Lead
- Project Administrator

Project User implies Odoo's native Project User group.

Project Lead implies:

- Project User
- task dependencies
- milestones

Project Administrator implies:

- Project Lead
- Odoo Project Manager

Access summary:

- Project users can read project types, sprints, and releases.
- Project leads can create and edit sprints and releases, but cannot delete
  them.
- Project administrators and Odoo project managers can create, edit, and delete
  sprints and releases.
- Project types can be managed by project administrators and Odoo project
  managers.

Record rules keep sprints and releases aligned with Odoo project visibility and
multi-company rules. Administrators and Odoo project managers have an explicit
see-all rule for sprints and releases.

## Languages And RTL

The module provides Arabic translations in:

- `i18n/ar.po`
- `i18n/ar_001.po`

The UI stylesheet uses logical CSS properties so the layout works in both
English LTR and Arabic RTL. Examples include `inline-size`, `margin-inline`,
`padding-inline`, and `border-inline-start`.

In Odoo 19, the active Arabic language may have:

```text
code = ar_001
iso_code = ar
direction = rtl
```

When importing translations from the CLI, use the language ISO code accepted by
the database. In the current local database, importing with `-l ar` loads into
the active `ar_001` language.

## Implementation Map

Important files:

- `models/project_project.py`: project extensions, dashboard metrics, team
  computation, project quick actions.
- `models/project_task.py`: task development fields, project-change cleanup,
  blocked toggle action.
- `models/project_sprint.py`: sprint model, metrics, sprint task action.
- `models/project_release.py`: release model, metrics, release task action.
- `models/project_type.py`: project type configuration model.
- `views/project_project_views.xml`: project kanban, list, form dashboard,
  search, and workspace action.
- `views/project_task_views.xml`: task form, list, search, kanban, and My Work
  action.
- `views/project_sprint_views.xml`: sprint search/list/kanban/form/graph/action.
- `views/project_release_views.xml`: release search/list/kanban/form/action.
- `views/project_report_views.xml`: task, sprint, and bug reporting actions.
- `views/project_menus.xml`: menu placement under Odoo Project.
- `security/security_groups.xml`: role hierarchy.
- `security/ir.model.access.csv`: model ACLs.
- `security/record_rules.xml`: company and project visibility rules.
- `static/src/scss/ab_projects.scss`: module-scoped modern UI styling.

## Daily Operating Flow

1. Create or open a project from Workspace.
2. Set the project type, technical lead, health, and important links.
3. Create sprints for active development cycles.
4. Create releases for launch/version scope.
5. Add or triage tasks using native Odoo stages.
6. Set task type, story points, sprint, release, reviewer, and QA owner.
7. For bugs, complete severity, environment, reproduction steps, expected
   result, and actual result.
8. Use My Work for assigned, review, and QA responsibilities.
9. Use project dashboard, sprint cards, and release cards for delivery review.
10. Use reports for planning, bug review, and story-point analysis.

## Boundaries

This module intentionally avoids replacing Odoo Project. It should not be used
to implement a separate workflow engine, a duplicated task board, or a Jira-like
schema. The native Odoo project/task workflow remains the source of truth for
task movement and completion.

The module should remain self-contained:

- Do not modify Odoo core.
- Do not modify native `project` module files.
- Keep frontend CSS and any future JS scoped to `ab_projects`.
- Preserve native Odoo task, project, timesheet, chatter, activity, and
  security behavior.

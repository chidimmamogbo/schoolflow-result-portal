# School_Management_Platform_Capstone_Proposal.pdf

## Seite 1

School Management and Learning Platform Proposal | Page 1
Capstone Project Proposal
Unified School Management and Learning
Platform for Nigerian Schools
Market comparison, proposed feature set and system design
Prepared by: Chidimma Merit Mogbo
Date: October 2026
Purpose: Submitted to my tutor for approval, suggestions and improvements

## Seite 2

School Management and Learning Platform Proposal | Page 2
Contents

## Seite 3

School Management and Learning Platform Proposal | Page 3
1. Project Overview
This capstone project is a multi-school platform that combines a School Management System
(SMS) and a Learning Management System (LMS) in one product. It is designed for Nigerian
schools and aims to improve on the school software already on the market.
1.1 Objectives
• Unify school administration and online learning behind a single login.
• Let each school design its own report card layout, grading scale and term structure.
• Support online classes through four live class providers: Google Meet, Zoom, Agora
and a self-hosted inbuilt option.
• Include hostel management, school bus management and full staff management.
• Allow a super admin to switch features on or off for each school, with access to
every enabled feature controlled by role.
1.2 Scope note
The full feature list below is the product vision. Section 10 proposes a phased build so that the
capstone delivers a complete, working core first and treats the remaining modules as later
phases.
2. Market Review: Existing Nigerian School Systems
The review below is based on vendor websites and comparison articles published online.
These are largely marketing materials, so the claims should be read as what each vendor says
it offers, not as independently tested results.
System Notable features Observations
SAFSIMS Fee management with custom payment
items and partial payments, biometric
attendance, hostel and vehicle management,
online tests, mobile app, teacher-student live
chat, autosave for poor connectivity
Strong on finance and boarding
features. Cloud based and
dependent on internet access.
SchoolShell Student and staff records, payroll, grading,
admission, accounting, inventory, hostel
management, mobile app, chat
Broad module list including HR
and accounting.
Smart School Student, teacher and parent panels, LMS,
online classroom, exams, payroll, payment
gateways
Sold as a self-hosted, pay-once
license. Combines LMS and
SMS.
SchoolHub Student records, attendance, fees, report
cards, CBT, parent communication, multi-
branch management, AI-powered claims
Positioned for both small
schools and school networks.
ExcelMind Academic management, fee tracking,
attendance, HR and payroll, performance
reviews, document management
Emphasis on all-in-one
administration.
Edves Separate K12 and tertiary editions, parent-
student-teacher interface, online fee
payment
Clear split between school
levels.

## Seite 4

School Management and Learning Platform Proposal | Page 4
3. Gaps and Opportunities
The gaps below are my own analysis from the review. They are the areas where this project
can differentiate itself and should be validated with real schools.
• True SMS and LMS unification. Many products treat learning tools as an add-on to
the administration system.
• Flexible report cards. Layouts are often fixed templates. A visual designer lets each
school reproduce its own format.
• Per-school feature control. Few products let a provider switch individual modules
on or off per school with role-based access.
• Offline-first operation. Connectivity is unreliable in many parts of Nigeria, so core
tasks should keep working offline and sync later.
• Local communication channels. WhatsApp and SMS notifications reach parents
more reliably than app-only alerts.
• Insight, not just records. Early-warning analytics for falling grades, absences and
unpaid fees.
• Trust and compliance. Audit trails on score changes, result approval workflows and
compliance with the Nigeria Data Protection Act.
4. Proposed Feature Set
Status key: Existing means already common in current systems. Improved means present
elsewhere but proposed here with a better approach. New means a differentiator.
4.1 Core administration
Module Features Status
Admissions and
records
Online admission, student and parent records, class and arm
setup, sessions and terms, timetables
Existing
Attendance Manual, QR code and optional biometric attendance, parent
alerts
Existing
Fees and payments Custom fee items, partial payments, receipts, reminders,
Paystack or Flutterwave integration, financial reports
Existing
Communication Announcements, messaging, events calendar, WhatsApp, SMS
and email notifications by role
Improved
Portals Parent, student, teacher, bursar and principal portals Existing
Library and
inventory
Book catalogue and lending, school inventory tracking Existing
Accounting Income, expenses and financial summaries Existing
4.2 Academics, results and learning
Module Features Status
Result portal Score entry, CA and exam weighting, grading scales, positions,
class averages, remarks, affective and psychomotor domains,
Existing

## Seite 5

School Management and Learning Platform Proposal | Page 5
Module Features Status
cumulative results
Report card
designer
Drag-and-drop template editor so each school designs its own
report card (see Section 6)
New
Result approval
workflow
Teacher, head of department and principal approval before
publishing, with audit log of every score change
New
Learning
management
Courses, lesson content, assignments, submissions, grading,
resource library, progress tracking
Existing
CBT and online
exams
Question bank, randomized questions, auto-marking, timers,
basic anti-cheat controls
Improved
Live classes Four providers behind one interface, scheduling, automatic
attendance, recordings linked to courses (see Section 7)
New
Academic planning Scheme of work, lesson plans, teacher evaluation Improved
Early-warning
analytics
Flags students with falling grades, repeated absence or unpaid
fees
New
Transcripts and
certificates
Generated documents with QR verification, alumni records Improved
4.3 Boarding, transport and staff
Module Features Status
Hostel
management
Buildings, rooms and beds, allocation and transfers, boarder
fees, roll call, visitor log, exeat requests with parent approval,
maintenance tickets
Existing
School bus Routes, stops, vehicles, drivers, student assignment, bus fees,
maintenance and fuel logs, pickup and drop-off alerts, optional
live GPS tracking
Improved
Staff management Profiles and documents, contracts, subject and class
assignment, attendance and leave, payroll with allowances
and deductions, payslips, appraisals, duty roster
Existing
4.4 Platform features
• Multi-tenancy: many schools on one platform, each with its own branding and data
separation.
• Super admin console with per-school feature toggles.
• Role-based access control with custom roles per school.
• Offline-first mode with background sync.
• Data export, backups, access logs and consent handling aligned with the Nigeria
Data Protection Act.
5. Feature Toggles and Role-Based Access
Access is controlled in two layers, so a user reaches a feature only when both layers allow it.

## Seite 6

School Management and Learning Platform Proposal | Page 6
• Layer 1, feature flags per school. The super admin enables only the modules each
school needs, such as hostel, transport, LMS, live classes, CBT or payroll. A disabled
module disappears from menus and its server routes reject requests.
• Layer 2, role permissions within the school. Each role holds permissions such as
hostel.view or results.approve. A user gets access only if the module is on and their
role has the permission.
Role Typical access
Super admin Creates schools, switches modules on or off, manages subscriptions
and usage billing
School admin or principal Configures the school, creates custom roles, approves results, views
all reports
Teacher Own classes, attendance, score entry, assignments, live classes, CBT
Bursar or accountant Fees, payments, expenses, payroll reports
Hostel master Rooms, allocation, roll call, visitors, exeat requests
Transport coordinator Routes, vehicles, drivers, bus assignments
HR officer Staff records, leave, payroll
Parent Their children's results, fees, attendance, messages, exeat approvals
Student Own timetable, courses, assignments, results, live classes
Suggested data model: a school_features table (school_id, feature_key, enabled), plus roles,
permissions and role_permissions tables scoped to each school.
6. Report Card Designer
Schools differ in how they present results, so the system includes a visual template editor
instead of one fixed layout.
6.1 What a school can configure
• Logo, colours, fonts, header and footer.
• Placement of data blocks: student details, subject table, CA and exam columns,
grade, position, class average, attendance, affective and psychomotor domains,
remarks and signatures.
• Its own grading scale, score weighting and term structure.
• Separate templates per level, such as nursery, primary, junior secondary and senior
secondary.
6.2 Proposed approach
• A drag-and-drop canvas editor saves each template as structured JSON.
• The server merges student data into the template and renders a PDF.
• Bulk printing for a whole class, with a QR code on each card for result verification.

## Seite 7

School Management and Learning Platform Proposal | Page 7
7. Live Class System
The platform exposes one LiveClassProvider interface with four operations: createMeeting,
joinUrl, endMeeting and getAttendance. Each provider is an adapter behind this interface, so a
school can choose the one that fits its budget and the platform can add providers later
without changing the rest of the system.
Provider How it works Strengths Considerations
Google Meet Create events through the
Google Calendar API with a
conference link requested;
teacher connects via
Google OAuth
Familiar, no media
servers to run
Depends on school or
teacher Google
accounts and Google's
usage rules
Zoom Create meetings through
the Zoom REST API with
OAuth; webhooks supply
join and leave times for
attendance
Familiar, reliable Account and licensing
requirements should be
checked before
building
Agora
(managed
inbuilt)
Agora video SDK embedded
in the platform with a
token server and one
channel per class
No servers to manage,
fully branded
classroom, 10,000 free
minutes per month
Billed per participant
minute: HD video about
$3.99 and voice about
$0.99 per 1,000 minutes;
recording is billed
separately
Self-hosted
inbuilt (Jitsi
Meet or
BigBlueButton)
Jitsi embedded with
secured tokens, or
BigBlueButton integrated
through its API
No per-minute fees;
BigBlueButton is built
for classrooms with
whiteboard, polls and
breakout rooms
Needs a server, TURN,
SSL and a recording
server; BigBlueButton is
heavier to run; Jitsi has
no built-in whiteboard
7.1 Cost note on Agora
As a rough estimate, one teacher and 40 students in a one-hour class is about 2,460
participant minutes. If everyone used HD video, that is roughly 10 US dollars per lesson, and
the free monthly pool would cover only a few lessons. Costs fall sharply if students join with
audio and the teacher alone uses video, and if resolution is capped. The platform should
therefore track usage minutes per school so that the cost can be passed on, and Agora
should sit behind the same feature toggle as the other modules. Agora's billing terms,
including what happens after the free minutes are used, should be confirmed in its console
before launch.
7.2 Common live class features
• Scheduling linked to the timetable and course.
• Automatic attendance from join and leave logs.
• Recordings attached to the course in the LMS.
• In-class polls and chat where the provider supports them.

## Seite 8

School Management and Learning Platform Proposal | Page 8
8. Hostel, School Bus and Staff Management
8.1 Hostel
• Hostel buildings, rooms and beds with allocation and transfer history.
• Boarder fees linked to the fees module.
• Daily roll call, visitor log and exeat or leave requests with parent approval.
• Maintenance tickets and room inventory.
8.2 School bus
• Routes, stops, vehicles and drivers, with students assigned to routes.
• Bus fees linked to the fees module.
• Maintenance, fuel and driver document records.
• Pickup and drop-off notifications to parents, with live GPS tracking as an optional
extension.
8.3 Staff
• Staff profiles, documents and contracts.
• Subject and class assignment, attendance, leave and duty roster.
• Payroll with allowances and deductions, and payslip generation.
• Performance appraisals.
9. Technical Considerations
• Multi-tenant data isolation so no school can see another school's data.
• Offline-first design for attendance and score entry with background synchronisation.
• Audit logging for results, payments and permission changes.
• Compliance with the Nigeria Data Protection Act: consent, retention rules and
access logs, with extra care for children's data.
• Payment gateway integration for fee collection.
• Technology stack to be confirmed after tutor feedback (see Section 12).
10. Proposed Development Phases
Phase Deliverables
1. Foundation Multi-tenant core, authentication, roles and permissions, feature
flags, super admin console
2. School operations Students, classes, sessions, attendance, fees and payments
3. Results Result engine, approval workflow, report card designer and PDF
printing
4. Learning LMS courses, assignments, CBT
5. Live classes Provider interface with Google Meet, Zoom, Agora and self-hosted
adapters

## Seite 9

School Management and Learning Platform Proposal | Page 9
Phase Deliverables
6. Boarding, transport
and staff
Hostel, school bus, staff management and payroll
7. Enhancements Offline sync, analytics dashboard, WhatsApp and SMS alerts
Proposed capstone target: complete Phases 1 to 5 as a working system, and present Phases 6
and 7 as designed and partially implemented extensions. This is a suggestion for discussion.
11. Risks and Mitigations
Risk Mitigation
Scope is too large for the timeline Phased delivery with a working core first; toggles let
unfinished modules stay off
Live class cost or server load Provider adapters, usage tracking per school, bandwidth-
saving defaults
Poor internet at schools Offline-first design for critical tasks
Data protection and children's
data
Role-based access, audit logs, consent records, data export
and deletion tools
Report card designer complexity Start with a constrained block-based editor before adding
free-form layout
12. Questions for My Tutor
• Is the overall scope appropriate for a capstone, and is the suggested split between
core phases and extensions acceptable?
• Are there modules you would remove, merge or add?
• Do you have preferences on the technology stack, database design or hosting
approach?
• Should I include a pilot test with a real school, and what evidence of evaluation
would you expect?
• What documentation and demonstration format will the final submission need?
13. References
Information in Sections 2 and 7 was gathered from the following public sources in October
2026. Vendor pages are marketing material and pricing may change.
• Nairaland: Best School Management Software in Nigeria 2026, Detailed Comparison
(nairaland.com)
• SAFSIMS: School Management System in Nigeria (safsims.com)
• SchoolShell: Best School Management Software in Nigeria (schoolshell.com)
• Smart School Manager: School Management Software in Nigeria
(smartschoolmanager.com)

## Seite 10

School Management and Learning Platform Proposal | Page 10
• SchoolHub: Best School Management Apps in Nigeria (schoolhub.tech)
• ExcelMind: The Best School Management Software in Nigeria (blog.excelmind.org)
• Meetrix: Open Source Video Conference Server Software, 7 Self-Hosted Options
(meetrix.io)
• OSSFind: Open-source alternatives to Zoom (ossfind.com)
• WhiteLabelZoom: 7 Best Self-Hosted Video Conferencing Tools (whitelabelzoom.com)
• Jitsi Guide: Jitsi vs BigBlueButton (jitsi.guide)
• Agora documentation: Video Calling pricing (docs.agora.io) and Agora pricing page
(agora.io)
# REPORT_CARD_RESEARCH.md: what a Nigerian school report card contains

Research for Phase 5 item 8 (BUILD_PROMPT: "two real-world report-card formats the block editor must reproduce"). Requested by Chidimma on 2026-10-12: three real secondary cards and three real nursery and primary cards, to check our report card template and template editor. Searched and read on 2026-10-12.

## 1. What could and could not be found

Complete real report cards are rarely published, and when they are they carry a real child's name, scores and photo. Scribd uploads only show a short summary to automated readers, and Nairaland blocked access (HTTP 403). We also never copy a real child's data (fictional data only). So this research uses **the structure** of every card or format that could be read, never anyone's personal details.

| # | Level | Source | Type | How much was readable |
|---|---|---|---|---|
| S1 | JSS and SSS | Ogun State Ministry of Education, Science and Technology CA report sheet, as rebuilt in an open-source school system ([PR #240](https://github.com/adedejimakinde/luffy-school-saas/pull/240), [PR #236](https://github.com/adedejimakinde/luffy-school-saas/pull/236)) | State government format (second-hand) | Full layout, papers, traits and scale |
| S2 | JSS 3 | A terminal report sheet from an Ogun State school on Scribd (personal record, all rights reserved) | Real school card | Summary only: three-term scores, totals, averages, class ranks, attendance |
| S3 | JSS and SSS | Descriptions from Nigerian school software vendors ([SchoolHub](https://schoolhub.tech/blog/free-report-card-templates-nigerian-schools), [School Software Pro](https://www.schoolsoftware.com.ng/report-sheet-card-or-student-performance-report/), [OpenEduCat](https://openeducat.org/gradebook/k12/nigeria/)) | Vendor templates, not real cards | Section lists only |
| P1 | Primary | [FCT Universal Basic Education Board termly academic report](https://www.fctubeb.gov.ng/cummulative_reportcard) | Official government format | Full layout |
| P2 | Primary | Evangel Royal Schools result sheet on [Scribd](https://www.scribd.com/document/835172044/Primary-Report-Card) | Real school card | Summary only |
| N1 | Nursery | NAPPS Nursery 1 scheme subjects, Lagos State nursery schemes (Social habits, Health habits) ([schemeofwork.com](https://schemeofwork.com/social-habits-scheme-of-work-for-nursery-1-lagos-state/), [edudelighttutors](https://edudelighttutors.com/health-habits-scheme-nursery-two-lagos/)) and the SchoolHub nursery template | Curriculum and vendor template | Subjects and rating words |

**Result:** 2 full formats (S1, P1), 2 real cards readable only in summary (S2, P2), and vendor and curriculum sources for the rest. No complete real nursery card was found. **To close this properly, the best source is one or two real cards from schools you know**, photographed with names, photos and scores covered.

## 2. What the formats contain

### Header and identity
- State or school crest, issuing body (S1: "OGUN STATE GOVERNMENT / MINISTRY OF EDUCATION, SCIENCE AND TECHNOLOGY"; P1: "F.C.T UNIVERSAL BASIC EDUCATION BOARD"), school name, sometimes a school code.
- Title: "TERMLY ACADEMIC REPORT" (P1), "JSS / SSS continuous assessment report sheet" (S1).
- Student: name, admission number or state student number (P1 "FPSN", S1 "Learner's ID"), sex, date of birth, class and arm, term, session or academic year, number in class, passport photo. SSS cards often add the **department** (Science, Arts, Commercial) (S3).

### Scores
- **Components:** S1 uses 1st Test 10, 2nd Test 10, Assignment 10, Exam 70 (CA 30, exam 70). Vendors describe CA 30 and exam 70 too; research notes CA was cut from 40% to 30% for external exam submissions ([Springer, 2025](https://link.springer.com/article/10.1007/s44217-025-00512-8)). Many private schools use 40 and 60.
- **Per subject:** total, grade, remark, position in subject, class average, highest and lowest in class (P1 has all of these).
- **SSS:** subjects grouped (S1: General, Business, Humanities, Science and Mathematics, Technology, Trade, Other).
- **Third term:** 1st, 2nd and 3rd term columns, an annual (weighted) average and a promotion result (S1 and P1 both have this; P1's page is titled "cumulative report card").

### Summary
- Marks obtainable, marks obtained, percentage, class position (S1); average score, position, pass or fail, class highest and lowest final score, number in class (P1).

### Grading
- Secondary uses the WAEC nine-point scale: A1 75 to 100, B2 70 to 74, B3 65 to 69, C4 60 to 64, C5 55 to 59, C6 50 to 54, D7 45 to 49, E8 40 to 44, F9 0 to 39 ([Wikipedia](https://en.wikipedia.org/wiki/Academic_grading_in_Nigeria), [Legit.ng](https://www.legit.ng/education/1719642-waec-grades-points-how-universities-calculate-admission-score/); WAEC's own page was not found, so treat the bands as widely reported).
- A grading key printed on the card.

### Behaviour (affective and psychomotor)
- S1, on a 5 to 1 grid with a key: **Affective:** Punctuality, Neatness, Honesty, Self-control, Attentiveness in class, Leadership. **Psychomotor:** Handwriting, Games and sports, Fluency, Handling of tools, Drawing and painting, Crafts. **Key:** 5 Excellent, 4 Good, 3 Average, 2 Below average, 1 Unsatisfactory.
- Vendors list similar traits: punctuality, neatness, respect, honesty, attentiveness, social skills; psychomotor: handwriting, sports, craft, manual dexterity.

### Attendance, comments, signatures, footer
- Times school opened, times present, times absent.
- Class teacher's (or form master's) comment; principal's or head teacher's comment.
- Signatures with date, school stamp; P1 adds an authentication code and QR.
- Next term begins; promotion result on third term.
- S1 has a health block (height, weight) shown only on some copies. Some private school cards add next term's fees.

### Nursery
- Subjects (NAPPS Nursery 1): Literacy, Numeracy, Pre-science, Health habits, Social habits, Handwriting. Lagos schemes add Rhymes, Letter work, Number work; some schools add Practical life.
- Rating words instead of scores: Excellent, Very good, Good, Fair, Needs improvement (SchoolHub nursery template), plus class teacher's and head teacher's comments, attendance and next term.

## 3. Our template compared with the standard

| Standard item | In our design now? | Note |
|---|---|---|
| Header: logo, school name, address, motto, title, session and term | Yes | |
| Student: name, admission number, sex, date of birth, age, class and arm, photo, house, form teacher | Yes | |
| Department (SSS: Science, Arts, Commercial) | **No** | Common on SSS cards |
| Subject table: components, total, grade, remark, position, class average, highest, lowest, teacher's initials | Yes | P1 has all of them |
| Subjects grouped by category (SSS) | **No** | S1 |
| Summary: total, average, position, number in class, class average, subjects, promotion | Yes | |
| Marks obtainable, highest and lowest average in class | **No** | S1, P1 |
| Grading key | Yes | Default bands not written in the spec |
| Affective and psychomotor with key | Yes | Default traits and key words not written in the spec |
| Attendance | Yes | |
| Comments and signatures, stamp | Yes | |
| Next term begins, QR, report ID | Yes | Ours is stronger (verification) |
| Third-term cumulative columns, annual average | After the core (Cumulative style) | Both government formats have it |
| Nursery: rating words, areas, comments | Yes | Default areas lack Pre-science and Handwriting |
| Health block, next term fees | No | Left out on purpose: health data is sensitive; fee collection is roadmap |

**Conclusion:** our template already covers nearly everything a standard Nigerian card shows. The gaps are small: SSS department and subject groups, three summary figures, and written defaults (grade bands, traits and key, two nursery areas). The changes Chidimma approves are recorded in `CHANGES.md` ("Report card template: gaps from the Nigerian report card research").

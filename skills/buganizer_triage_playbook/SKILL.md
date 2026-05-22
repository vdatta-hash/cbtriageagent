---
name: buganizer-triage-playbook
description: >
  Triages NPS-GE-Security bugs and blockers tagged with Hotlist 8186342 (intake) and transitions them to 8278523 (triaged).
---

# Triage Playbook for NPS-GE-Security Issues (Hotlist 8186342)

This playbook directs the Buganizer Triage Agent on how to process and triage Cloud Blocker (CB) issues tagged with Hotlist **8186342**. The primary goal is to validate technical security gaps, verify owner/PM assignment, track business impact, and route issues to the correct product areas.

---

## 🎯 Role & Goals

*   **Role:** NPS-GE-Security Bug Triager.
*   **Goals:**
    1.  **Duplicate Detection:** Quickly identify duplicate issues and link them to canonical issues.
    2.  **Security Gap Validation:** Validate whether the request represents a genuine security gap or has existing workarounds.
    3.  **Correct Assignment:** Ensure correct Product Manager (PM) or security SME assignment based on the product area.
    4.  **Business Impact Linkage:** Verify that business impact (Vector Opportunity or Workload ID) is properly linked on Customer Requirement (CR) bugs.
    5.  **Complete Triage Lifecycle:** Transition completed issues from the intake hotlist (**8186342**) to the triaged hotlist (**8278523**).

---

## 🛑 Global Rules & Policies

1.  **NEVER** close a Cloud Blocker bug directly as `CLOSED`. Use specific resolution statuses like `DUPLICATE` or transition the status appropriately.
2.  **Opportunity Linkage comments** must *only* be added to **Customer Requirement (CR) bugs**, *never* to the main Cloud Blocker (CB) bug.
3.  **Always add a comment** explaining any changes made (e.g., reassigning, updating custom fields).

---

## 📋 Key Fields & Custom Fields Reference

To correctly parse and modify issue metadata, refer to this standard field schema:

| Field Name | ID / Identifier | Type | Possible Values | Description / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Component ID** | N/A | System | `550983` (Gemini 3 / Agent Registry)<br>`1848999` (ServiceNow/3P Connectors) | Product components where these bugs typically reside. |
| **PM Validated** | `321470` | ENUM | `Backlog`<br>`Awaiting PM Status`<br>`PM Validated: Workaround` | Indicates PM assessment status of the Cloud Blocker. |
| **Customer Name** | `1437198` | TEXT | e.g., "walmart inc", "Rivian Automotive" | Identifies the blocking customer. |
| **Connector Type** | `1437124` | TEXT | e.g., "ServiceNowFederated", "JiraFederated" | Type of federated integration/connector. |
| **3P Connector** | `1442178` | TEXT | e.g., "3P connector" | Denotes whether a third-party connector is under scope. |
| **Feature Request (FR)**| `1496657` | TEXT | e.g., "Feature Request (FR)" | Flags that the issue is a request for new capabilities. |

---

## 🔄 Triage Workflow

### Phase 1: Initial Review & Duplicate Check

1.  **Analyze Title & Description:**
    *   Review the Cloud Blocker's title, description, and any custom fields.
    *   Identify the core feature gap, affected product, and expected customer outcome.

2.  **Check for Existing Duplicates:**
    *   Use structured search or keyword lookup to check if the same customer request has already been logged.
    *   **IF** a historical duplicate is identified (matching `canonical_issue_id` or listed in `duplicate_issue_ids` such as `479608226` -> `475988445` or `493625712` -> `493627476`):
        *   Set the bug status to `DUPLICATE`.
        *   Link to the canonical issue ID.
        *   Add a comment: *"Marking as duplicate of b/[canonical_issue_id]."*
        *   Proceed directly to Phase 5.

---

### Phase 2: Validate the Technical Gap

If the issue is unique, perform a technical gap validation:

1.  **Check Existing Functionality & Security Workarounds:**
    *   Verify if the requested feature/capability is already available in Google Cloud by searching `cloud.google.com` or internal product roadmaps.
2.  **Identify Workarounds:**
    *   Determine if there is an alternative configuration, API, or pattern that meets the customer's underlying need.
    *   **IF** a workaround exists:
        *   Document the workaround step-by-step in a comment on the CB bug.
        *   Update **PM Validated (ID: 321470)** to `PM Validated: Workaround`.
3.  **Confirm Blocker Status:**
    *   Examine linked Customer Requirement (CR) bugs in the **Blocking** or **Dependencies** tabs.
    *   Confirm that the absence of this feature is genuinely blocking workload migration, adoption, or active revenue.

---

### Phase 3: Verify & Correct PM Assignment

Ensure the bug is assigned to the correct Product Manager (PM) or security SME:

1.  **Identify the Product Scope:**
    *   Determine the primary Google Cloud product or service needing modification (e.g., ServiceNow connector vs. Model Armor).
2.  **Check Current Assignee:**
    *   Verify if the active assignee matches the product owner. Use internal resources (e.g., `go/cloud-pst` or Moma) to identify product owners.
3.  **Perform Reassignment (IF necessary):**
    *   **IF** the currently assigned PM is incorrect:
        *   Find the correct PM's LDAP or target oncall team (e.g., `modelarmor-oncall@google.com`).
        *   Reassign the assignee field to the correct PM.
        *   Add a comment: `Reassigning to @[correct_pm_ldap] as this feature request falls under the scope of [Product Name].`

---

### Phase 4: Ensure Opportunity Linkage in CRs

To track business impact and revenue relevance:

1.  **Inspect Linked Customer Requirements (CRs):**
    *   Navigate to each CR bug linked to the Cloud Blocker.
2.  **Verify Vector Opportunity or Workload ID:**
    *   Ensure a Vector Opportunity ID or Workload ID is populated in the CR custom fields.
3.  **Flag Missing Opportunities:**
    *   **IF** the ID is missing:
        *   **DO NOT** comment on the main Cloud Blocker bug.
        *   **Instead, leave a comment directly on the CR bug** tagging the reporter:
            > *"Hi @[reporter_ldap], please add the relevant Vector Opportunity or Workload ID to this Customer Requirement to help us track the business impact."*

---

### Phase 5: Update Cloud Blocker Status & Complete Lifecycle

1.  **Set Status and Resolution:**
    *   Ensure the Cloud Blocker status is correctly set to reflect active triage.
    *   Ensure the bug is successfully assigned to the PM and set **PM Validated (ID: 321470)** to `Awaiting PM Status` for the PM's initial review.
2.  **Complete Triage Lifecycle (Hotlist Transition):**
    *   Add the issue to **NPS-GE-Security Bug-Triaged hotlist (ID: 8278523)**.
    *   Remove the issue from **NPS-GE-Security Bug hotlist (ID: 8186342)**.

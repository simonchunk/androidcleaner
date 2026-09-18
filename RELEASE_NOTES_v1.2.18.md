# v1.2.18 Local Test — structural UI fix

This build replaces the fragile mechanisms behind the repeated UI regressions.

- Checkboxes are no longer floating widgets over ttk.Treeview. The Android icon and
  a crisp drawn checkbox are one composite image in Treeview column #0, so Windows
  cannot paint the checkbox behind the table.
- Clicking the icon/checkbox area toggles that app. Checked state is blue with a
  white tick; protected apps show a drawn lock.
- App Assessment no longer uses action_apps(), which is removal-selection logic.
  It follows one persistent focused package across all tabs and table rebuilds.
- Assessment header height is fixed so content changes do not resize/reflow the card.
- Warning and Repair Intelligence headers use separate fixed-width vector-icon cells
  and text labels instead of compound image/text labels, fixing the spacing.
- Existing Android icon extraction, scanner icon-loading stage and risk badges remain.

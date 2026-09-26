## v1.0.0 (2026-09-26)

### BREAKING CHANGE

- Position and combined modes no longer start with the
alarm enabled. Users will see the alarm activate only when the actual
trigger condition is met (stationary/disconnect), providing clearer
feedback about when monitoring begins.

### Feat

- enable options flow to view and modify integration instance parameters
- combined mode rebuild
- add new parser based on pixelshober smartthings_find integration
- **position**: optimize GPS tracking and fix timer behavior
- unify alarm initialization behavior across all activation modes
- enhanced services and webnhook - Updated translations (EN/IT) with new messages - Fixed config flow UI (field ordering, password fields

### Fix

- implement reconfigure flow and resolve options flow config_entry property error
- prevent excessive duplicate activation notifications on tag flap
- prevent multiple alarm activation
- notifications services
- notification in connection mode and update translations
- remove broken card
- multi-instance integration and rename integration
- proper integration lifecycle cleanup and resource management

### Refactor

- the configuration wizard: reorganized fields, removed , consolidated the  function in , and added labels and text descriptions for all fields in the translation files.

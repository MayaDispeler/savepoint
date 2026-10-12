# LegacyWorld port (FR23, V23): not executed

Status: **drafted, not run.** The ported task needs the OpenMRS sandbox, which needs Docker, and Docker is not
installed on the build machine. No results are reported here.

Source: LegacyWorld, arXiv 2608.14131, task "OpenMRS Onboard Patient". OD07 (the benchmark's licence) is still open,
so `workflows/openmrs/onboard_patient.yaml` is an own-words contract for the same task shape (register a patient with
name, gender, birthdate and one identifier; a visit is not created). Nothing is copied from the benchmark.

When Docker is available: start OpenMRS (`apps/openmrs/compose.yml`), seed it, add an `OpenMrsAdapter` (MySQL snapshot
with `mysqldump --single-transaction` plus the files volume), run 10 trials in arms B and S, and report the result
in a separate table here, with the citation above.

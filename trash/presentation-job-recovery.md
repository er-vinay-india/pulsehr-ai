# Presentation generation after a server reload

Presentation generation runs in a background thread. A development-server reload
terminates that thread. Previously, job-manager construction and API startup
marked every pending/running job as failed with “Generation was interrupted by
server reload,” even when another manager's worker was still alive.

The job manager now persists the worker PID and recovery-attempt count alongside
the original generation scope. Startup claims jobs whose owning process has
stopped, resets their partial progress, and launches the existing pipeline again
under the same job ID. The source selection, brief, theme, instructions, and
other saved settings are retained. This rebuilds from the beginning; intermediate
pipeline stages are not checkpointed. It uses the pipeline's normal data loading
and evidence verification.

Status polling also recovers a specifically requested historical job with the
old reload-interruption error. It does not bulk retry historical failures.
Evidence/export validation failures, completed jobs, and cancelled jobs remain
terminal. SQL compare-and-set claims and live-process checks prevent duplicate
relaunches. Ownership uses the local host's PID namespace, matching the current
single-host SQLite deployment.

Automatic recovery is bounded to three interrupted rebuilds per job. After that,
the job reports repeated interruption and can be generated again once the server
is stable. Worker launch failures are recorded without breaking API startup.
Cancellation is persisted and late stage updates cannot overwrite a cancelled
job or a job owned by another process.

The existing progress screen maps recovery to the brief-setup phase. Completion
controls appear only for a successful `ready` stage; an error at 100% does not
certify a finished presentation. No slide theme or output-template changes are
part of this fix.

Focused checks:

```sh
cd backend
.venv/bin/python -m pytest tests/test_presentation_job_recovery.py
```

```sh
cd frontend
npm run test:deck
npm run build
```

The backend tests cover preserved scopes, duplicate claims, legacy-table
migration, legacy error recovery through the actual status endpoint, completed
deck attachment, cancellation, real validation failures, invalid saved settings,
retry bounds, and launch failures. Frontend checks render the actual progress
component for recovery, failure, and successful completion.

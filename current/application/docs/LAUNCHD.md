# macOS Launch Agent

## Launch-agent label

`com.comfiance.cre-foundry.metadata-watch`

## Schedule

The agent polls at minute 17 of every hour using
`StartCalendarInterval`.

The orchestration profile still decides whether the source is due.
Hourly polling therefore does not mean hourly source retrieval.

A missed calendar event caused by sleep is coalesced by launchd and
runs after the computer wakes. Powered-off periods remain dependent
on the next available calendar event after login.

## Production wrapper

`scripts/run_metadata_watch.sh`

The wrapper uses absolute paths and does not depend on Conda or an
interactive terminal.

Each completed invocation writes:

`logs/launchd_metadata_watch.status.json`

The status record includes UTC start time, UTC completion time and
process exit code.

## Safety

- Plantrak remains `access_state: review`.
- Bulk acquisition remains blocked.
- This agent can only invoke the metadata-watch profile.
- Source locks prevent overlapping retrieval.
- Due-only planning prevents unnecessary source access.

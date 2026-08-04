# IT & Ops projects

Infrastructure, automation, security, and operations tooling — built for reliability, repeatability, and IT service management. Projects here are tested, documented, and safe to run.

## Projects

- **[Infrastructure health monitor](infra-health-monitor/)** — a config-driven monitoring tool with SLO tracking: HTTP, TCP, disk, and process checks, SQLite history, rolling uptime vs availability targets, and transition/breach alerts with an optional webhook. A live demo caught a flaky service and a crashed worker, and the suite covers it with 60 hermetic tests.

- **[Disk failure prediction](disk-failure-prediction/)** — a machine-learning pipeline that flags drives at risk of imminent failure from S.M.A.R.T. telemetry. Trained on a 60,000-drive sample of Backblaze's real Q1 2024 data with an F1-tuned decision threshold: 0.9999 held-out ROC-AUC, 0.994 precision / 0.970 recall, with recall above 0.98 out to two weeks before failure and 0.976 at 30 days. Includes a scored-risk CLI for fresh snapshots and an honest breakdown of the false-alarm trade-off.

New projects are added here as they are completed.

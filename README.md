# wsload: Asyncio WebSocket Load-Testing Tool

`wsload` opens many concurrent WebSocket connections with Python `asyncio`,
sends messages, validates the responses, and measures **latency** and **throughput**.
It produces console, JSON, and CSV reports and returns a **pass/fail exit code**,
so it can act as a quality gate in CI.

> ⚠️ **Only load-test systems you own or have written permission to test.**
> Sending heavy traffic to third-party servers can violate their terms of service
> and may be treated as a denial-of-service attack. A local echo server is included
> for safe testing.

---

## Table of contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Project structure](#project-structure)
4. [Prerequisites](#prerequisites)
5. [Quick start](#quick-start)
6. [Usage](#usage)
7. [Scenario configuration](#scenario-configuration)
8. [Understanding the results](#understanding-the-results)
9. [Thresholds and exit codes](#thresholds-and-exit-codes)
10. [Running the tests](#running-the-tests)
11. [Continuous integration](#continuous-integration)
12. [Troubleshooting](#troubleshooting)
13. [Design decisions and limitations](#design-decisions-and-limitations)
14. [Roadmap](#roadmap)

---

## Features

- Hundreds or thousands of concurrent connections on a single event loop
- Configurable ramp-up, message size, think time, and timeouts
- Response validation: every reply is matched to its request by ID
- Latency percentiles (p50/p90/p95/p99), throughput, error rate, connect time
- Errors are classified by type (for example, `connect:ConnectionRefusedError` or `response_timeout`)
- YAML scenarios with CLI overrides
- Reports: console summary, detailed JSON per run, and `history.csv` for trends
- Thresholds with a non-zero exit code on failure (CI quality gate)
- Built-in echo server, including an artificial-delay mode for negative testing
- Unit and integration tests, plus a GitHub Actions pipeline

## How it works

```
 YAML scenario ─► config.py ─► runner.py ─► N × virtual_user (client.py) ─► WebSocket server
                                                     │
                                                     ▼
                     reporter.py  ◄──────────  metrics.py
          (console, JSON, history.csv, pass/fail exit code)
```

1. **config.py** loads and validates the scenario.
2. **runner.py** starts one `virtual_user` coroutine per connection with `asyncio.gather`.
3. Each **virtual user** waits for its ramp-up slot, connects, and then repeats
   *send → wait for reply → validate → record latency* for N messages.
4. **metrics.py** collects raw measurements and aggregates them.
5. **reporter.py** prints the summary, checks thresholds, and saves the reports.

## Project structure

| Path | Purpose |
|---|---|
| `src/wsload/cli.py` | Command-line interface (`wsload run`, `wsload server`) |
| `src/wsload/config.py` | Scenario model, YAML loading, validation |
| `src/wsload/client.py` | Virtual user: one connection, N messages |
| `src/wsload/runner.py` | Runs all virtual users concurrently |
| `src/wsload/metrics.py` | Measurements, percentiles, summary |
| `src/wsload/reporter.py` | Console/JSON/CSV output and threshold checks |
| `src/wsload/server.py` | Local echo server (test target) |
| `config/*.yaml` | Ready-made scenarios (`smoke`, `load`) |
| `tests/` | Unit and integration tests (pytest) |
| `.github/workflows/ci.yml` | CI pipeline |

## Prerequisites

- Python **3.10+** (`python --version`)
- Git
- On Linux and macOS, a raised open-file limit for high connection counts (see [Troubleshooting](#troubleshooting))

## Quick start

**1. Clone the repository and enter the folder**

```bash
git clone https://github.com/<your-username>/ws-loadtest.git
cd ws-loadtest
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\activate
```

**3. Install the tool, including the development dependencies**

```bash
pip install -e ".[dev]"
```

**4. Start the local echo server (Terminal 1)**

```bash
wsload server
```

Expected output: `Echo server listening on ws://127.0.0.1:8765 ...`

**5. Run the smoke test (Terminal 2, with the virtual environment activated)**

```bash
wsload run --config config/smoke.yaml
```

Example output (your numbers will vary):

```
=== wsload report: smoke ===
Target            : ws://127.0.0.1:8765
Connections       : 10 ok / 0 failed
Messages          : 100 ok / 100 planned
Duration          : 0.12 s
Throughput        : 833.33 msg/s
Error rate        : 0.00%
Latency (ms)      : min 0.4 | avg 1.1 | p50 0.9 | p90 1.8 | p95 2.1 | p99 3.4 | max 4.0
Connect time (ms) : avg 9.8 | p95 14.2
Errors            : none
Result            : PASSED
Report saved: results/smoke-20250101-120000.json
```

You can also run the tool with `python -m wsload ...` instead of `wsload ...`.

## Usage

### Run a load test

```bash
# Use a scenario file
wsload run --config config/load.yaml

# Override scenario values from the CLI (CLI values take precedence)
wsload run --config config/load.yaml -c 1000 --ramp-up 20

# Run without a file (defaults plus flags)
wsload run --uri ws://127.0.0.1:8765 -c 200 -m 50

# Print the results without saving report files
wsload run --config config/smoke.yaml --no-save
```

| Option | Description |
|---|---|
| `--config PATH` | YAML scenario file |
| `--uri URI` | Target (`ws://` or `wss://`) |
| `-c, --connections N` | Number of concurrent connections |
| `-m, --messages N` | Messages per connection |
| `--message-size N` | Payload padding in bytes |
| `--ramp-up SECONDS` | Spread connection starts over this time |
| `--out DIR` | Report directory (default: `results`) |
| `--no-save` | Do not write report files |

### Start the echo server

```bash
wsload server                    # ws://127.0.0.1:8765
wsload server --port 9000
wsload server --delay-ms 100     # simulate a slow backend (negative testing)
```

## Scenario configuration

```yaml
name: smoke                  # used in report file names
uri: ws://127.0.0.1:8765     # target server
connections: 10              # concurrent virtual users
messages_per_connection: 10  # messages each user sends
message_size: 64             # payload padding in bytes
ramp_up_s: 0                 # seconds to spread connection starts over
think_time_s: 0              # pause between messages per user
connect_timeout_s: 10        # max time to open a connection
response_timeout_s: 5        # max time to wait for each reply

thresholds:                  # optional; omit a key to skip that check
  max_p95_ms: 200
  max_error_rate: 0.0        # 0.01 = 1%
  min_throughput: 50         # successful messages per second
```

Unknown or misspelled keys are rejected with a clear error, so a typo can't
silently fall back to a default value.

**Total planned messages = `connections × messages_per_connection`.**

## Understanding the results

| Metric | Definition |
|---|---|
| **Latency** | Round-trip time from `send()` to receiving the *matching* reply on the same connection, measured with the monotonic `time.perf_counter()` |
| **p50 / p90 / p95 / p99** | Percentage of messages that completed at or below this latency (nearest-rank method). p95 = 200 ms means 95% of messages took 200 ms or less. |
| **Throughput** | Successful messages ÷ total wall-clock duration (includes connect and ramp-up time) |
| **Error rate** | Share of *planned* messages that did not complete successfully. Failed connections and stopped users count against it. |
| **Connect time** | Time to complete the TCP and WebSocket handshake |
| **Errors** | Count by type. `connect:*` = could not connect, `runtime:*` = connection broke during the test, `response_timeout` = no reply in time, `payload_mismatch` = wrong reply |

> Watch percentiles, not averages. A good average can hide a slow tail
> that real users still experience.

### Report files (`results/`)

- `<scenario>-<timestamp>.json` contains the full configuration, summary, and threshold results for one run.
- `history.csv` gets one row per run, so you can compare runs over time
  (comma-separated, UTF-8; open it in Excel or load it with pandas).

## Thresholds and exit codes

| Exit code | Meaning |
|---|---|
| `0` | All thresholds passed |
| `1` | At least one threshold failed, or no message succeeded |
| `2` | Configuration error (missing file, invalid YAML, invalid value) |

A pipeline step fails automatically when performance drops below the agreed limits.

## Running the tests

```bash
pytest -v
```

| File | Covers |
|---|---|
| `test_config.py` | YAML loading, validation, rejection of misspelled keys |
| `test_metrics.py` | Percentile math, error rate, throughput |
| `test_reporter.py` | Threshold pass/fail logic |
| `test_integration.py` | End-to-end against a real echo server on a random port: happy path, slow server, response timeout, unreachable server |

The integration tests start their own server, so you don't need to run one manually.

## Continuous integration

On every push and pull request, `.github/workflows/ci.yml`:

1. Installs the project.
2. Runs all tests.
3. Starts the echo server and runs the `smoke` scenario as a performance gate.
4. Uploads `results/` as a build artifact, even if the job fails.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Too many open files` / `OSError: [Errno 24]` | Raise the limit with `ulimit -n 10000` (Linux/macOS, current shell) |
| `connect:ConnectionRefusedError` | The server isn't running, or the URI or port is wrong |
| Many `connect:TimeoutError` errors at high load | The server can't accept connections fast enough. Increase `ramp_up_s` or `connect_timeout_s`. |
| `wsload: command not found` | Activate the virtual environment and run `pip install -e ".[dev]"` again, or use `python -m wsload` |
| Results vary a lot between runs | Close other heavy applications, run each scenario several times, and compare `history.csv` |
| Client CPU at 100% | The load generator is the bottleneck, so the results describe the client, not the server. Reduce the load or see the Roadmap. |

## Design decisions and limitations

- **asyncio instead of threads:** WebSocket load is I/O-bound. One event loop can
  hold thousands of idle connections with far less memory than one thread per connection.
- **No locks around metrics:** asyncio is single-threaded, and each metric update
  is one statement with no `await`, so updates can't interleave.
- **Response validation:** a reply only counts as a success if its ID matches the request.
  Speed without correctness isn't a pass.
- **Fault isolation:** an exception in one virtual user is recorded and classified.
  It never stops the whole test.
- **Stopping a user after a timeout:** a late reply would be read by the next `recv()`
  and corrupt the measurements, so that user stops.
- **Closed-loop model (limitation):** each user waits for a reply before sending the
  next message. When the server slows down, the offered load also drops, so the
  results can understate tail latency (*coordinated omission*). An open-loop,
  fixed-rate mode is on the roadmap.
- **Single process (limitation):** one CPU core generates the load. For very high load,
  run several processes or machines.

## Roadmap

- [ ] Duration-based runs (`duration_s`) as an alternative to a fixed message count
- [ ] Open-loop mode with a fixed message rate (avoids coordinated omission)
- [ ] Multi-process load generation for higher scale
- [ ] Latency charts (matplotlib) and an HTML report
- [ ] Docker Compose setup for the server and client
- [ ] Custom message templates and protocol plugins

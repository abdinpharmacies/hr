#!/usr/bin/env python3
import argparse
import csv
import math
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from string import Template
import commands as commands_config


def log(message: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def build_remote_command(user_command: str):
    summary_helpers = """
summarize() {
    printf '__SUMMARY__:%s\\n' "$*"
}

summarize_kv() {
    local key="$1"
    if [ "$#" -lt 2 ]; then
        summarize "$key"
        return 0
    fi
    shift
    printf '__SUMMARY__:%s=%s\\n' "$key" "$*"
}
"""
    script = f"{summary_helpers}\n{user_command}\n"
    return REMOTE_LAUNCH.replace("__TMUX_WRAPPER__", shlex.quote(TMUX_WRAPPER)).replace(
        "__SCRIPT_CONTENT__", shlex.quote(script)
    )


# Runs inside tmux, independently of the SSH connection. Never enable shell
# tracing here: rendered commands and their output can contain credentials.
TMUX_WRAPPER = r"""
set -u
umask 077
script_path="$1"
log_path="$2"
status_path="$3"
started_at=$(date '+%Y-%m-%dT%H:%M:%S%z')
finished_at=
state=running
exit_code=
script_exit_code=
log_exit_code=
write_status() {
    local status_tmp="${status_path}.tmp.$$"
    {
        printf 'state=%s\nstarted_at=%s\nfinished_at=%s\n' "$state" "$started_at" "$finished_at"
        printf 'exit_code=%s\nscript_exit_code=%s\nlog_exit_code=%s\n' "$exit_code" "$script_exit_code" "$log_exit_code"
    } > "$status_tmp" && mv -f -- "$status_tmp" "$status_path"
}
finish() {
    exit_code=$?
    trap - EXIT
    finished_at=$(date '+%Y-%m-%dT%H:%M:%S%z')
    state=failed
    if [[ "$exit_code" == 0 ]]; then state=succeeded; fi
    if ! write_status; then
        printf 'Unable to record update completion in %s\n' "$status_path" >&2
        exit 1
    fi
    exit "$exit_code"
}
trap finish EXIT
write_status || exit 1
# Keep history private, but let deployed files be readable by the Odoo user.
(umask 022; bash "$script_path") 2>&1 | tee "$log_path"
pipeline_codes=("${PIPESTATUS[@]}")
script_exit_code=${pipeline_codes[0]}
log_exit_code=${pipeline_codes[1]}
if [[ "$script_exit_code" != 0 ]]; then exit "$script_exit_code"; fi
exit "$log_exit_code"
"""

REMOTE_LAUNCH = r"""
set -e
umask 077
command -v tmux >/dev/null
updates_dir="$HOME/updates"
mkdir -p -- "$updates_dir"
chmod 700 -- "$updates_dir"
base_name="update_$(date '+%Y-%m-%d_%H-%M-%S')"
suffix=0
while :; do
    session_name="$base_name"
    if (( suffix > 0 )); then session_name="${base_name}_$suffix"; fi
    script_path="$updates_dir/$session_name.sh"
    log_path="$updates_dir/$session_name.log"
    status_path="$updates_dir/$session_name.status"
    if [[ ! -e "$log_path" && ! -L "$log_path" && ! -e "$status_path" && ! -L "$status_path" ]] &&
       ! tmux has-session -t "=$session_name" 2>/dev/null; then
        if (set -C; : > "$script_path") 2>/dev/null; then break; fi
        if [[ ! -e "$script_path" && ! -L "$script_path" ]]; then
            printf 'Cannot create update script in %s\n' "$updates_dir" >&2
            exit 1
        fi
    fi
    suffix=$((suffix + 1))
done
{
    printf '#!/usr/bin/env bash\n# Generated: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf '%s' __SCRIPT_CONTENT__
} > "$script_path"
chmod 700 -- "$script_path"
: > "$log_path"
printf 'state=queued\n' > "$status_path"
chmod 600 -- "$log_path" "$status_path"
printf '__SUMMARY__:update_script=%s\n' "$script_path"
printf '__SUMMARY__:update_log=%s\n' "$log_path"
printf '__SUMMARY__:update_status=%s\n' "$status_path"
printf '__SUMMARY__:tmux_session=%s\n' "$session_name"
if tmux new-session -d -s "$session_name" -c "$PWD" bash -c __TMUX_WRAPPER__ -- "$script_path" "$log_path" "$status_path"; then
    printf '__SUMMARY__:remote_state=running\n'
else
    launch_rc=$?
    printf 'state=failed\nexit_code=%s\nfinished_at=%s\n' "$launch_rc" "$(date '+%Y-%m-%dT%H:%M:%S%z')" > "$status_path"
    printf '__SUMMARY__:remote_state=failed\n'
    exit "$launch_rc"
fi
"""


def build_monitor_command(summary_kv, timeout):
    """Only observe files/session; ending this SSH process cannot kill the job."""
    assignments = "\n".join(
        f"{variable}={shlex.quote(summary_kv[key][-1])}"
        for variable, key in (
            ("log_path", "update_log"),
            ("status_path", "update_status"),
            ("session_name", "tmux_session"),
        )
    )
    return assignments + f"\nwait_seconds={max(1, math.ceil(timeout))}\n" + r"""
read_status() {
    state=unknown
    exit_code=
    while IFS='=' read -r key value; do
        case "$key" in
            state) state="$value" ;;
            exit_code) exit_code="$value" ;;
        esac
    done < "$status_path"
}
is_complete() {
    [[ "$exit_code" =~ ^(0|[1-9][0-9]{0,2})$ ]] && (( exit_code <= 255 )) &&
    { [[ "$state" == succeeded && "$exit_code" == 0 ]] ||
      { [[ "$state" == failed ]] && (( exit_code > 0 )); }; }
}
show_result() {
    cat -- "$log_path" || return 1
    printf '\n__SUMMARY__:remote_state=%s\n' "$state"
}
deadline=$((SECONDS + wait_seconds))
while :; do
    read_status
    if is_complete; then
        show_result || exit 1
        exit "$exit_code"
    fi
    if ! tmux has-session -t "=$session_name" 2>/dev/null; then
        # Completion may have been recorded between our first read and tmux exit.
        read_status
        if is_complete; then continue; fi
        state=unknown
        show_result
        printf 'Tmux session ended without a completion record; inspect the log.\n' >&2
        exit 125
    fi
    if (( SECONDS >= deadline )); then
        state=unknown
        show_result
        printf 'Monitoring timed out; the tmux update was not stopped.\n' >&2
        exit 124
    fi
    sleep 2
done
"""


def extract_summary_data(
    stdout: str,
    max_length: int = 200,
    max_notes: int = 10,
    max_values_per_key: int = 10,
):
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return [], {}

    # Prefer explicit summary marker if present.
    marker = "__SUMMARY__:"
    notes = []
    summary_kv = {}
    for line in lines:
        if line.startswith(marker):
            summary_payload = line[len(marker):].strip()
            if not summary_payload:
                continue

            if "=" in summary_payload:
                key, value = summary_payload.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key:
                    values = summary_kv.setdefault(key, [])
                    if len(values) < max_values_per_key:
                        values.append(value[:max_length])
                    continue

            notes.append(summary_payload[:max_length])

    if notes or summary_kv:
        return notes[:max_notes], summary_kv

    return [lines[-1][:max_length]], {}


def format_summary_text(summary_notes, summary_kv):
    parts = []
    parts.extend(summary_notes or [])
    for key, values in (summary_kv or {}).items():
        parts.append(f"{key}={' | '.join(values)}")
    return " | ".join(parts)


def load_commands_template():
    if not hasattr(commands_config, "commands"):
        raise ValueError("commands.py must define `commands`")
    commands_template = commands_config.commands

    if not isinstance(commands_template, str) or not commands_template.strip():
        raise ValueError("`commands` must be a non-empty string")
    return commands_template


def is_marked_for_ssh(value: str):
    marker = ("" if value is None else str(value)).strip().lower()
    return marker in {"1", "true", "yes", "y", "on", "run", "x", "ssh"}


def parse_server_list_input(input_text):
    """Parse server list input from various formats"""
    server_names = []
    # Replace commas with spaces and split
    for part in input_text.replace(',', ' ').split():
        server_name = part.strip()
        if server_name:
            server_names.append(server_name)
    return server_names


def load_jobs_from_csv(csv_path: str, commands_template: str, run_ssh_column: str, 
                       select_all=False, server_list=None):
    csv_file = Path(csv_path)
    if not csv_file.is_file():
        raise ValueError(f"CSV file not found: {csv_file}")

    jobs = []
    rows = []
    headers = []
    all_jobs = []  # Store all jobs before filtering for interactive mode
    
    with csv_file.open(mode="r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        seen = set()
        for raw_header in reader.fieldnames or []:
            header = ("" if raw_header is None else str(raw_header).strip())
            if not header or header in seen:
                continue
            seen.add(header)
            headers.append(header)

        if not headers:
            raise ValueError("CSV must contain headers")
        if "server" not in headers:
            raise ValueError("CSV must include required `server` header")
        if run_ssh_column not in headers:
            raise ValueError(f"CSV must include required `{run_ssh_column}` header")

        for line_no, row in enumerate(reader, start=2):
            normalized = {
                str(key).strip(): ("" if value is None else str(value).strip())
                for key, value in row.items()
                if key is not None and str(key).strip()
            }
            if not any(normalized.values()):
                continue

            rows.append(normalized)

            host = normalized.get("server", "")
            if not host:
                raise ValueError(f"CSV line {line_no} missing required `server` value")

            substitutions = {k: v for k, v in normalized.items()}
            command = Template(commands_template).safe_substitute(substitutions).strip()
            if not command:
                raise ValueError(f"CSV line {line_no} produced empty command")

            # Apply server list filter (case-insensitive, strip whitespace)
            if server_list:
                # Normalize host name for comparison
                normalized_host = host.strip().lower()
                # Check if any server in the list matches (case-insensitive)
                server_list_normalized = [s.strip().lower() for s in server_list]
                if normalized_host not in server_list_normalized:
                    continue

            # Determine if server should be selected for SSH
            # If server_list is provided, automatically select those servers
            if server_list:
                selected_for_ssh = True
            else:
                selected_for_ssh = select_all or is_marked_for_ssh(normalized.get(run_ssh_column, ""))
            
            job_data = {
                "item": len(all_jobs) + 1,
                "host": host,
                "command": command,
                "row": normalized,
                "selected_for_ssh": selected_for_ssh,
            }
            
            all_jobs.append(job_data)
            
            # Add to jobs if selected
            if selected_for_ssh:
                jobs.append(job_data)

    if not all_jobs:
        raise ValueError("CSV does not contain any server rows")

    return jobs, rows, headers



def show_filtering_menu():
    print("\n" + "="*60)
    print("FILTERING OPTIONS")
    print("="*60)
    print("1. --select-all (Run on all servers)")
    print("2. --server-list (Paste list of servers to run on)")
    print("3. Exit")
    print("="*60)
    return input("Enter your choice (1, 2, or 3): ").strip()




def write_rows(csv_path: str, rows, headers, extra_headers):
    output_headers = [h for h in headers if h]
    for header in extra_headers:
        if header and header not in output_headers:
            output_headers.append(header)

    # Keep UTF-8 BOM so Excel/Windows tools decode non-ASCII text correctly.
    with Path(csv_path).open(mode="w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=output_headers)
        writer.writeheader()
        for row in rows:
            output_row = {key: row.get(key, "") for key in output_headers}
            writer.writerow(output_row)


def run_host(alias, command, timeout=600, connect_timeout=5):
    cmd = [
        "ssh",
        "-o", f"ConnectTimeout={connect_timeout}",
        "-o", "ConnectionAttempts=1",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        alias,
        "bash", "-s",
    ]

    log(f"Connecting to {alias}")
    deadline = time.monotonic() + timeout
    summary_notes, summary_kv = [], {}

    def collect(stdout, max_length=200):
        notes, values = extract_summary_data(stdout, max_length=max_length)
        summary_notes.extend(notes)
        summary_kv.update(values)

    def display(stdout, stderr):
        if stdout:
            print(f"\n----- {alias} STDOUT -----\n{stdout}", flush=True)
        if stderr:
            print(f"\n----- {alias} STDERR -----\n{stderr}", flush=True)

    def ssh(remote_command):
        return subprocess.run(
            cmd,
            input=remote_command,
            text=True,
            errors="replace",
            capture_output=True,
            timeout=max(0.01, deadline - time.monotonic()),
        )

    try:
        launched = ssh(command)
        collect(launched.stdout, max_length=4096)
        display(launched.stdout, launched.stderr)
        if launched.returncode:
            if launched.returncode == 255:
                summary_kv["remote_state"] = ["unknown"]
            return alias, launched.returncode, summary_notes, summary_kv

        required = ("update_script", "update_log", "update_status", "tmux_session")
        if not all(summary_kv.get(key) for key in required):
            log(f"UNKNOWN {alias}: launch metadata missing; inspect ~/updates before retrying")
            summary_kv["remote_state"] = ["unknown"]
            return alias, 125, summary_notes, summary_kv
        log(f"{alias}: tmux session {summary_kv['tmux_session'][-1]}; "
            f"log {summary_kv['update_log'][-1]}")
        monitor = build_monitor_command(summary_kv, deadline - time.monotonic())
        result = ssh(monitor)
        collect(result.stdout)
        display(result.stdout, result.stderr)
        rc = result.returncode
        if summary_kv.get("remote_state", [""])[-1] not in ("succeeded", "failed"):
            summary_kv["remote_state"] = ["unknown"]
            rc = rc or 125
            log(f"{alias}: monitoring ended without a completion result; "
                "inspect the remote update before retrying")
        return alias, rc, summary_notes, summary_kv
    except subprocess.TimeoutExpired as exc:
        # TimeoutExpired can contain bytes even when subprocess uses text=True.
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        collect(stdout, max_length=4096)
        display(stdout, stderr)
        summary_kv["remote_state"] = ["unknown"]
        log(f"TIMEOUT {alias}: stopped waiting after {timeout}s; "
            "the remote tmux update was not stopped. Inspect ~/updates before retrying.")
        return alias, 124, summary_notes, summary_kv
    except Exception as exc:
        summary_kv["remote_state"] = ["unknown"]
        log(f"CONNECTION ERROR {alias}: {exc}; inspect ~/updates before retrying")
        return alias, 255, summary_notes, summary_kv


def summarize_status(rc, summary_kv=None):
    remote_state = (summary_kv or {}).get("remote_state", [""])[-1]
    if remote_state == "failed":
        return "FAILED"
    if rc == 125 and remote_state == "unknown":
        return "UNKNOWN"
    if rc == 0:
        return "OK"
    if rc == 255:
        return "CONNECTION FAILED"
    if rc == 124:
        return "TIMEOUT"
    return "FAILED"


def main():
    parser = argparse.ArgumentParser(
        description="Save commands.py as a timestamped script in each SSH user's ~/updates and run it in tmux.",
        epilog=("Scripts, logs and status files remain in ~/updates. Attach with tmux attach -t SESSION. "
                "Tmux survives SSH disconnections, not reboots. Privileged commands need noninteractive sudo. "
                "For production use --concurrency 1; inspect existing runs before retrying.")
    )
    parser.add_argument(
        "--servers-csv",
        default="servers.csv",
        help="Path to CSV file with server rows (must include `server` header, default: servers.csv)"
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue even if a remote command fails"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Maximum number of concurrent SSH connections (default: 20)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-host launch/monitoring timeout in seconds; remote tmux updates continue after timeout (default: 600)"
    )
    parser.add_argument(
        "--connect-timeout",
        type=int,
        default=5,
        help="SSH connection timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--status-column",
        default="status",
        help="CSV column used to write execution status (default: status)",
    )
    parser.add_argument(
        "--returncode-column",
        default="return_code",
        help="CSV column used to write process return code (default: return_code)",
    )
    parser.add_argument(
        "--summary-column",
        default="summary",
        help="CSV column used to write compact summary text (default: summary)",
    )
    parser.add_argument(
        "--summary-kv-prefix",
        default="summary_",
        help="Prefix for dynamic CSV columns generated from summarize_kv() keys (default: summary_)",
    )
    parser.add_argument(
        "--run-ssh-column",
        default="run_ssh",
        help="CSV column used to select rows for SSH (truthy: 1/true/yes/on/x, default: run_ssh)",
    )
    parser.add_argument(
        "--output-csv",
        help="Path to output CSV file (default: overwrite input CSV file)",
    )
    parser.add_argument(
        "--select-all",
        action="store_true",
        help="Select all servers regardless of run_ssh column",
    )
    parser.add_argument(
        "--server-list",
        help="Comma-separated list of servers to run SSH on (e.g., 'abdin-189,abdin-198')",
    )

    args = parser.parse_args()

    # Check if no filtering arguments were provided
    no_filter_args = not any([
        args.select_all,
        args.server_list
    ])
    
    # Show interactive menu if no filtering arguments were provided
    if no_filter_args:
        print("\nNo filtering options specified.")
        choice_input = show_filtering_menu()
        
        # Check if user wants to exit (entered '3')
        if choice_input.strip() == '3':
            print("Exiting...")
            sys.exit(0)
        
        if choice_input.strip() == '1':
            args.select_all = True
            print("✓ Selected: --select-all")
        elif choice_input.strip() == '2':
            print("\nPaste your list of servers (one per line).")
            print("Press Enter twice (empty line) when done:")
            
            server_input_lines = []
            empty_line_count = 0
            
            while True:
                try:
                    line = input()
                    if line.strip() == "":
                        empty_line_count += 1
                        if empty_line_count >= 2:
                            break
                    else:
                        empty_line_count = 0
                        server_input_lines.append(line)
                except EOFError:
                    break
            
            # Parse the input
            server_list_input = "\n".join(server_input_lines)
            server_names = parse_server_list_input(server_list_input)
            
            if server_names:
                args.server_list = server_names
                print(f"✓ Selected: --server-list with {len(server_names)} servers")
                print(f"  Servers: {', '.join(server_names[:5])}" + 
                      ("..." if len(server_names) > 5 else ""))
            else:
                print("No servers provided, using default behavior")
        else:
            print(f"Invalid choice '{choice_input}', using default behavior")
        
        print()  # Add blank line for readability

    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    if args.timeout < 1:
        parser.error("--timeout must be >= 1")

    if args.connect_timeout < 1:
        parser.error("--connect-timeout must be >= 1")

    args.status_column = args.status_column.strip()
    args.returncode_column = args.returncode_column.strip()
    args.summary_column = args.summary_column.strip()
    args.run_ssh_column = args.run_ssh_column.strip()
    if not args.status_column:
        parser.error("--status-column must not be empty")
    if not args.returncode_column:
        parser.error("--returncode-column must not be empty")
    if not args.summary_column:
        parser.error("--summary-column must not be empty")
    if not args.run_ssh_column:
        parser.error("--run-ssh-column must not be empty")

    if args.output_csv is None:
        # Create a timestamp-based output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_path = Path(args.servers_csv)
        args.output_csv = str(input_path.with_name(f"{input_path.stem}_{timestamp}{input_path.suffix}"))

    try:
        commands_template = load_commands_template()
        # Convert server_list string to list if provided via command line
        if args.server_list and isinstance(args.server_list, str):
            args.server_list = parse_server_list_input(args.server_list)
        
        jobs, rows, headers = load_jobs_from_csv(
            args.servers_csv, 
            commands_template, 
            args.run_ssh_column,
            select_all=args.select_all,
            server_list=args.server_list
        )
    except ValueError as e:
        parser.error(str(e))
    except Exception as e:
        parser.error(f"Failed to load configuration: {e}")

    results = {}
    stop_submitting = False
    # In non-interactive mode, jobs already contains only selected ones
    selected_indexes = list(range(len(jobs)))
    
    # If no servers are selected, show a message and exit
    if not selected_indexes:
        print("\nNo servers selected for SSH execution.")
        print("Use --select-all or ensure run_ssh column has truthy values.")
        sys.exit(0)
    
    jobs_iter = iter(selected_indexes)

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_index = {}

        for _ in range(min(args.concurrency, len(selected_indexes))):
            index = next(jobs_iter, None)
            if index is None:
                break
            job = jobs[index]
            host = job["host"]
            command = build_remote_command(job["command"])
            future = executor.submit(
                run_host, host, command, args.timeout, args.connect_timeout
            )
            future_to_index[future] = index

        while future_to_index:
            done, _ = wait(future_to_index, return_when=FIRST_COMPLETED)

            for future in done:
                index = future_to_index.pop(future)
                job = jobs[index]
                host = job["host"]

                try:
                    returned_host, rc, summary_notes, summary_kv = future.result()
                    results[index] = {
                        "host": returned_host,
                        "rc": rc,
                        "summary_notes": summary_notes,
                        "summary_kv": summary_kv,
                    }
                except Exception as e:
                    log(f"UNEXPECTED ERROR {host}: {e}")
                    results[index] = {
                        "host": host,
                        "rc": 255,
                        "summary_notes": [],
                        "summary_kv": {},
                    }
                    rc = 255

                # Transport failures are distinct from completed scripts exiting 124/255.
                remote_state = results[index].get("summary_kv", {}).get("remote_state", [""])[-1]
                if rc in (124, 255) and remote_state not in ("succeeded", "failed"):
                    log(f"Skipping {host} due to connection/timeout issue")
                    continue

                # Stop scheduling new hosts on remote command failure unless continue-on-error
                if rc != 0 and not args.continue_on_error:
                    log(f"Stopping new submissions due to failure on {host}")
                    stop_submitting = True

            while not stop_submitting and len(future_to_index) < args.concurrency:
                index = next(jobs_iter, None)
                if index is None:
                    break
                job = jobs[index]
                host = job["host"]
                command = build_remote_command(job["command"])
                future = executor.submit(
                    run_host, host, command, args.timeout, args.connect_timeout
                )
                future_to_index[future] = index

            if stop_submitting:
                for pending_future in future_to_index:
                    pending_index = future_to_index[pending_future]
                    pending_host = jobs[pending_index]["host"]
                    log(f"Waiting for already-started host to finish: {pending_host}")

                for future in list(future_to_index):
                    pending_index = future_to_index[future]
                    pending_host = jobs[pending_index]["host"]
                    try:
                        returned_host, rc, summary_notes, summary_kv = future.result()
                        results[pending_index] = {
                            "host": returned_host,
                            "rc": rc,
                            "summary_notes": summary_notes,
                            "summary_kv": summary_kv,
                        }
                    except Exception as e:
                        log(f"UNEXPECTED ERROR {pending_host}: {e}")
                        results[pending_index] = {
                            "host": pending_host,
                            "rc": 255,
                            "summary_notes": [],
                            "summary_kv": {},
                        }
                break

    extra_headers = [args.status_column, args.returncode_column, args.summary_column]
    
    # First, update all rows with default values
    for index, job in enumerate(jobs):
        row = job["row"]
        
        # Check if this job was selected for SSH
        if not job.get("selected_for_ssh"):
            row[args.status_column] = "NOT_SELECTED"
            row[args.returncode_column] = ""
            # Determine why it wasn't selected
            if args.select_all or args.server_list:
                row[args.summary_column] = "Filtered out by selection criteria"
            else:
                row[args.summary_column] = (
                    f"Set {args.run_ssh_column}=1/yes/true/on/x to run SSH"
                )
        else:
            # This job was selected for SSH
            result = results.get(index)
            
            if not result:
                row[args.status_column] = "SKIPPED"
                row[args.returncode_column] = ""
                row[args.summary_column] = ""
            else:
                rc = result["rc"]
                row[args.status_column] = summarize_status(rc, result.get("summary_kv"))
                row[args.returncode_column] = str(rc)
                row[args.summary_column] = format_summary_text(
                    result.get("summary_notes", []), result.get("summary_kv", {})
                )

                for key, values in result.get("summary_kv", {}).items():
                    csv_column = f"{args.summary_kv_prefix}{key}" if args.summary_kv_prefix else key
                    if not csv_column:
                        continue
                    row[csv_column] = " | ".join(values)
                    if csv_column not in extra_headers:
                        extra_headers.append(csv_column)

    write_rows(args.output_csv, rows, headers, extra_headers)

    # Open the result file
    try:
        if sys.platform == "win32":
            os.startfile(args.output_csv)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", args.output_csv], check=False)
        else:  # Linux and other Unix-like
            subprocess.run(["xdg-open", args.output_csv], check=False)
        log(f"Opened updated CSV file: {args.output_csv}")
    except Exception as e:
        log(f"Could not open CSV file automatically: {e}")
        print(f"CSV file updated: {args.output_csv}")

    print("\n====== SUMMARY ======")
    all_ok = True
    selected_count = 0
    ok_count = 0
    failed_count = 0
    skipped_count = 0
    not_selected_count = 0
    
    # Count statistics
    for index, job in enumerate(jobs):
        if not job.get("selected_for_ssh"):
            not_selected_count += 1
        else:
            selected_count += 1
            if index in results:
                rc = results[index]["rc"]
                if rc == 0:
                    ok_count += 1
                else:
                    failed_count += 1
                    all_ok = False
            else:
                skipped_count += 1
                all_ok = False
    
    # Print detailed results
    for index, job in enumerate(jobs):
        host = job["host"]

        if not job.get("selected_for_ssh"):
            if args.select_all:
                # Don't print filtered out servers unless in verbose mode
                pass
            else:
                print(f"{host}: NOT_SELECTED")
            continue

        # Don't increment selected_count here, it's already counted
        if index not in results:
            print(f"{host}: SKIPPED")
            continue

        rc = results[index]["rc"]
        status = summarize_status(rc, results[index].get("summary_kv"))
        summary_notes = results[index].get("summary_notes", [])
        summary_kv = results[index].get("summary_kv", {})
        summary_text = format_summary_text(summary_notes, summary_kv)
        if summary_text:
            print(f"{host}: {status} : {summary_text}")
        else:
            print(f"{host}: {status}")

    print("---------------------")
    print(
        f"TOTAL: {len(jobs)} | SELECTED: {selected_count} | OK: {ok_count} | FAILED: {failed_count} | SKIPPED: {skipped_count} | NOT_SELECTED: {not_selected_count}"
    )
    print(f"CSV FILE UPDATED: {args.output_csv}")
    print("=====================")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

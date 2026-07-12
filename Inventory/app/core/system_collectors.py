"""Collect scheduled tasks, processes, and services locally (read-only)."""

from __future__ import annotations

import csv
import io
import subprocess

from app.core.models import ProcessRecord, ScanError, ServiceRecord, TaskRecord


def _run_read_only(command: list[str], *, timeout: float = 120.0) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    return result.stdout or ""


def collect_scheduled_tasks(computer: str) -> tuple[list[TaskRecord], list[ScanError]]:
    errors: list[ScanError] = []
    output = _run_read_only(["schtasks", "/Query", "/FO", "CSV", "/V"])
    if not output.strip() or output.startswith("Traceback") or "Error" in output[:80]:
        errors.append(
            ScanError(
                computer=computer,
                path=computer,
                error="Scheduled task query returned no data.",
                phase="scheduled_tasks",
            )
        )
        return [], errors

    reader = csv.DictReader(io.StringIO(output))
    tasks: list[TaskRecord] = []
    for row in reader:
        tasks.append(
            TaskRecord(
                name=row.get("TaskName", "").strip(),
                program=row.get("Task To Run", "").strip(),
                arguments="",
                working_directory=row.get("Start In", "").strip(),
                status=row.get("Status", "").strip(),
                trigger=row.get("Triggers", "").strip(),
                computer=computer,
            )
        )
    return tasks, errors


def collect_processes(computer: str) -> tuple[list[ProcessRecord], list[ScanError]]:
    errors: list[ScanError] = []
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object Name,ExecutablePath,CommandLine | "
        "ConvertTo-Csv -NoTypeInformation"
    )
    output = _run_read_only(["powershell", "-NoProfile", "-Command", script])
    if not output.strip():
        errors.append(
            ScanError(
                computer=computer,
                path=computer,
                error="Process query returned no data.",
                phase="processes",
            )
        )
        return [], errors

    reader = csv.DictReader(io.StringIO(output))
    processes: list[ProcessRecord] = []
    for row in reader:
        processes.append(
            ProcessRecord(
                name=row.get("Name", "").strip(),
                executable=row.get("ExecutablePath", "").strip(),
                command_line=row.get("CommandLine", "").strip(),
                working_directory=row.get("ExecutablePath", "").strip(),
                computer=computer,
            )
        )
    return processes, errors


def collect_services(computer: str) -> tuple[list[ServiceRecord], list[ScanError]]:
    errors: list[ScanError] = []
    output = _run_read_only(["sc", "query", "type=", "service", "state=", "all"])
    if not output.strip():
        errors.append(
            ScanError(
                computer=computer,
                path=computer,
                error="Service query returned no data.",
                phase="services",
            )
        )
        return [], errors

    services: list[ServiceRecord] = []
    current_name = ""
    current_status = ""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("SERVICE_NAME:"):
            current_name = line.split(":", 1)[1].strip()
        elif line.startswith("STATE"):
            current_status = line.split(":", 2)[-1].strip()
            services.append(
                ServiceRecord(
                    name=current_name,
                    status=current_status,
                    startup_type="",
                    executable="",
                    computer=computer,
                )
            )
    return services, errors


def enrich_service_details(services: list[ServiceRecord]) -> None:
    for service in services:
        output = _run_read_only(["sc", "qc", service.name], timeout=30)
        if not output.strip():
            continue
        for line in output.splitlines():
            line = line.strip()
            if line.upper().startswith("START_TYPE"):
                service.startup_type = line.split(":", 1)[1].strip()
            if "BINARY_PATH_NAME" in line.upper():
                service.executable = line.split(":", 1)[1].strip().strip('"')

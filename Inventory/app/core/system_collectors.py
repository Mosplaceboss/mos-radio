"""Collect scheduled tasks, processes, and services (read-only)."""

from __future__ import annotations

import csv
import io
import subprocess

from app.core.models import ProcessRecord, ScanError, ServiceRecord, TaskRecord
from app.core.paths_util import is_computer_name, is_local_target


def _run_read_only(command: list[str], *, timeout: float = 120.0) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.stdout or ""


def _remote_computer(computer: str) -> str | None:
    if not computer or is_local_target(computer):
        return None
    if is_computer_name(computer):
        return computer
    if computer.startswith("\\\\"):
        return computer.lstrip("\\").split("\\", 1)[0]
    return None


def collect_scheduled_tasks(computer: str) -> tuple[list[TaskRecord], list[ScanError]]:
    errors: list[ScanError] = []
    target = _remote_computer(computer)
    command = ["schtasks", "/Query", "/FO", "CSV", "/V"]
    if target:
        command.extend(["/S", target])
    output = _run_read_only(command)
    if not output.strip():
        if target:
            errors.append(
                ScanError(
                    computer=computer,
                    path=target,
                    error="Remote scheduled task query returned no data.",
                    phase="scheduled_tasks",
                )
            )
        output = _run_read_only(["schtasks", "/Query", "/FO", "CSV", "/V"])

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
    target = _remote_computer(computer)
    if target:
        script = (
            f"$ErrorActionPreference='SilentlyContinue'; "
            f"Invoke-Command -ComputerName '{target}' -ScriptBlock {{ "
            "Get-CimInstance Win32_Process | "
            "Select-Object Name,ExecutablePath,CommandLine | "
            "ConvertTo-Csv -NoTypeInformation "
            "} | Out-String"
        )
        output = _run_read_only(["powershell", "-NoProfile", "-Command", script])
        if not output.strip():
            output = _run_read_only(
                ["wmic", fr"/node:{target}", "process", "get", "Name,ExecutablePath,CommandLine", "/format:csv"]
            )
        if not output.strip():
            errors.append(
                ScanError(
                    computer=computer,
                    path=target,
                    error="Remote process query returned no data.",
                    phase="processes",
                )
            )
            return [], errors
    else:
        script = (
            "Get-CimInstance Win32_Process | "
            "Select-Object Name,ExecutablePath,CommandLine | "
            "ConvertTo-Csv -NoTypeInformation"
        )
        output = _run_read_only(["powershell", "-NoProfile", "-Command", script])

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
    target = _remote_computer(computer)
    command = ["sc", "query", "type=", "service", "state=", "all"]
    if target:
        command = ["sc", rf"\\{target}", "query", "type=", "service", "state=", "all"]
    output = _run_read_only(command)
    if not output.strip() and target:
        errors.append(
            ScanError(
                computer=computer,
                path=target,
                error="Remote service query returned no data.",
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


def enrich_service_details(services: list[ServiceRecord]) -> list[ScanError]:
    errors: list[ScanError] = []
    for service in services:
        target = _remote_computer(service.computer)
        command = ["sc", "qc", service.name]
        if target:
            command = ["sc", rf"\\{target}", "qc", service.name]
        output = _run_read_only(command, timeout=30)
        if not output.strip():
            continue
        for line in output.splitlines():
            line = line.strip()
            if line.upper().startswith("START_TYPE"):
                service.startup_type = line.split(":", 1)[1].strip()
            if "BINARY_PATH_NAME" in line.upper():
                service.executable = line.split(":", 1)[1].strip().strip('"')
    return errors

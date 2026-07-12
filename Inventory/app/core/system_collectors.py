"""Collect scheduled tasks, processes, and services (read-only)."""

from __future__ import annotations

import csv
import io
import subprocess
from pathlib import Path

from app.core.models import ProcessRecord, ServiceRecord, TaskRecord


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


def collect_scheduled_tasks(computer: str) -> list[TaskRecord]:
    target = computer if computer.startswith("\\\\") else computer
    command = ["schtasks", "/Query", "/FO", "CSV", "/V"]
    if target and target not in {"", "."} and "\\" not in target and ":" not in target:
        command.extend(["/S", target])
    output = _run_read_only(command)
    if not output.strip():
        return collect_scheduled_tasks_local(computer)

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
    return tasks


def collect_scheduled_tasks_local(computer: str) -> list[TaskRecord]:
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
    return tasks


def collect_processes(computer: str) -> list[ProcessRecord]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object Name,ExecutablePath,CommandLine,@{n='WorkingDirectory';e={$_.ExecutablePath}} | "
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
                working_directory=row.get("WorkingDirectory", "").strip(),
                computer=computer,
            )
        )
    return processes


def collect_services(computer: str) -> list[ServiceRecord]:
    output = _run_read_only(["sc", "query", "type=", "service", "state=", "all"])
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
    return services


def enrich_service_details(services: list[ServiceRecord]) -> None:
    for service in services:
        output = _run_read_only(["sc", "qc", service.name])
        for line in output.splitlines():
            line = line.strip()
            if line.upper().startswith("START_TYPE"):
                service.startup_type = line.split(":", 1)[1].strip()
            if "BINARY_PATH_NAME" in line.upper():
                service.executable = line.split(":", 1)[1].strip().strip('"')

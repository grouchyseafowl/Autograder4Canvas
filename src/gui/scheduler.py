"""
Cross-platform scheduling for automation runs.
"""
import platform
import subprocess
import textwrap
from abc import ABC, abstractmethod
from pathlib import Path


class Scheduler(ABC):
    @abstractmethod
    def install(self, hour: int, minute: int, python_path: str, script_path: str) -> None: ...

    @abstractmethod
    def uninstall(self) -> None: ...

    @abstractmethod
    def is_installed(self) -> bool: ...


class MacScheduler(Scheduler):
    PLIST = Path.home() / "Library" / "LaunchAgents" / "com.autograder.automation.plist"

    def install(self, hour: int, minute: int, python_path: str, script_path: str) -> None:
        plist = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
                "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
                <key>Label</key>
                <string>com.autograder.automation</string>
                <key>ProgramArguments</key>
                <array>
                    <string>{python_path}</string>
                    <string>{script_path}</string>
                </array>
                <key>StartCalendarInterval</key>
                <dict>
                    <key>Hour</key>
                    <integer>{hour}</integer>
                    <key>Minute</key>
                    <integer>{minute}</integer>
                </dict>
                <key>RunAtLoad</key>
                <false/>
                <key>StandardOutPath</key>
                <string>{Path.home() / 'Library' / 'Logs' / 'autograder.log'}</string>
                <key>StandardErrorPath</key>
                <string>{Path.home() / 'Library' / 'Logs' / 'autograder_err.log'}</string>
            </dict>
            </plist>
        """)
        self.PLIST.parent.mkdir(parents=True, exist_ok=True)
        self.PLIST.write_text(plist)
        subprocess.run(["launchctl", "load", str(self.PLIST)], check=False)

    def uninstall(self) -> None:
        if self.PLIST.exists():
            subprocess.run(["launchctl", "unload", str(self.PLIST)], check=False)
            self.PLIST.unlink()

    def is_installed(self) -> bool:
        return self.PLIST.exists()


class WindowsScheduler(Scheduler):
    TASK_NAME = "AutograderCanvas"

    def install(self, hour: int, minute: int, python_path: str, script_path: str) -> None:
        time_str = f"{hour:02d}:{minute:02d}"
        subprocess.run(
            [
                "schtasks", "/create",
                "/tn", self.TASK_NAME,
                "/tr", f'"{python_path}" "{script_path}"',
                "/sc", "daily",
                "/st", time_str,
                "/f",
            ],
            check=True,
        )

    def uninstall(self) -> None:
        subprocess.run(["schtasks", "/delete", "/tn", self.TASK_NAME, "/f"], check=False)

    def is_installed(self) -> bool:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", self.TASK_NAME],
            capture_output=True,
        )
        return result.returncode == 0


class LinuxScheduler(Scheduler):
    MARKER = "# autograder-canvas-automation"

    def _get_crontab(self) -> str:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""

    def _set_crontab(self, content: str) -> None:
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=content)

    def install(self, hour: int, minute: int, python_path: str, script_path: str) -> None:
        existing = self._get_crontab()
        # Remove old entry
        lines = [l for l in existing.splitlines() if self.MARKER not in l]
        lines.append(f"{minute} {hour} * * * {python_path} {script_path} {self.MARKER}")
        self._set_crontab("\n".join(lines) + "\n")

    def uninstall(self) -> None:
        existing = self._get_crontab()
        lines = [l for l in existing.splitlines() if self.MARKER not in l]
        self._set_crontab("\n".join(lines) + "\n")

    def is_installed(self) -> bool:
        return self.MARKER in self._get_crontab()


def get_scheduler() -> Scheduler:
    s = platform.system()
    if s == "Darwin":
        return MacScheduler()
    if s == "Windows":
        return WindowsScheduler()
    return LinuxScheduler()

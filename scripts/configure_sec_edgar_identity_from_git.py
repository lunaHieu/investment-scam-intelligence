"""Create a private SEC EDGAR User-Agent identity from local Git configuration.

The script never prints the name or email and refuses noreply addresses.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def git_config_value(key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--get", key],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_contact_email(value: str) -> None:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("Local Git email is missing or invalid")
    if re.search(r"noreply|users\.noreply\.github\.com", value, re.IGNORECASE):
        raise ValueError("Local Git email is a noreply address")


def write_private_identity(path: Path, *, project: str, email: str, purpose: str) -> None:
    validate_contact_email(email)
    if not project.strip() or not purpose.strip():
        raise ValueError("Project and purpose are required")
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite private identity: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "organization_or_project": project.strip(),
        "contact_email": email.strip(),
        "purpose": purpose.strip(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--project",
        default="Investment Scam Intelligence Research Project",
    )
    parser.add_argument(
        "--purpose",
        default="academic investment-scam intelligence research",
    )
    args = parser.parse_args()
    email = git_config_value("user.email")
    write_private_identity(
        args.output,
        project=args.project,
        email=email,
        purpose=args.purpose,
    )
    print(
        json.dumps(
            {
                "created": True,
                "path": str(args.output),
                "contact_email_exposed": False,
                "private_file_hash_disclosed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

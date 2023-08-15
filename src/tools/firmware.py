from __future__ import annotations
import re
from typing import Optional

from github import Github

file_content: str = ""


def get_remote_version(device: str) -> Optional[int]:
    global file_content
    if len(file_content) == 0:
        repo = Github().get_repo("sanworks/Bpod_Gen2")
        filename = "Functions/Internal Functions/CurrentFirmwareList.m"
        file_content = repo.get_contents(filename).decoded_content.decode()
    result = re.search(rf"Firmware.{device}[= ]+(\d+)", file_content, re.IGNORECASE)
    return result.group(1) if result else None

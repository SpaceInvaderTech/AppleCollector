"""
Local, encrypted cache of the GET /haystacks device list (id, name, privateKey) for the local fetch CLI.
"""
import logging
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from app.dtos import BeamerDevice

logger = logging.getLogger(__name__)

MAX_AGE_SECONDS = 24 * 60 * 60


class MacKeychain:
    SERVICE = "spaceinvader-control-center"
    ACCOUNT = "key-cache"
    ITEM_NOT_FOUND = 44

    def get_or_create_fernet_key(self) -> bytes:
        found = subprocess.run(
            ["security", "find-generic-password", "-s", self.SERVICE, "-a", self.ACCOUNT, "-w"],
            capture_output=True, text=True,
        )
        if found.returncode == 0:
            return found.stdout.strip().encode()
        if found.returncode != self.ITEM_NOT_FOUND:
            raise RuntimeError(f"Reading the key-cache key from the Keychain failed (exit {found.returncode})")

        key = Fernet.generate_key()
        # Passed on stdin through `security -i` so the key never shows up in the process list.
        created = subprocess.run(
            ["security", "-i"],
            input=f"add-generic-password -s {self.SERVICE} -a {self.ACCOUNT} -w {key.decode()}\n",
            capture_output=True, text=True,
        )
        if created.returncode != 0:
            raise RuntimeError(f"Storing the key-cache key in the Keychain failed (exit {created.returncode})")
        logger.info("Created a new key-cache key in the Keychain")
        return key


class KeyCacheEntry(BaseModel):
    fetched_at: float
    devices: list[BeamerDevice]


class KeyCache(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    download: Callable[[], list[BeamerDevice]]
    keychain: MacKeychain = Field(default_factory=MacKeychain)
    clock: Callable[[], float] = time.time
    max_age_seconds: int = MAX_AGE_SECONDS

    _fernet: Fernet | None = PrivateAttr(default=None)

    def get_devices(self, tracker_ids: set[str] | None = None, refresh: bool = False) -> list[BeamerDevice]:
        """Devices for tracker_ids (all cached devices when None). Unknown ids are left out, not raised."""
        devices = None if refresh else self._load()
        if devices is None or (tracker_ids and not tracker_ids <= {d.name for d in devices}):
            devices = self._refresh()
        if tracker_ids:
            return [d for d in devices if d.name in tracker_ids]
        return devices

    def _refresh(self) -> list[BeamerDevice]:
        devices = self.download()
        self._save(devices)
        logger.info(f"Refreshed key cache with {len(devices)} devices")
        return devices

    def _load(self) -> list[BeamerDevice] | None:
        if not self.path.exists():
            return None
        try:
            entry = KeyCacheEntry.model_validate_json(self._get_fernet().decrypt(self.path.read_bytes()))
        except (InvalidToken, ValidationError):
            logger.warning("Key cache could not be decrypted; downloading it again")
            return None
        if self.clock() - entry.fetched_at > self.max_age_seconds:
            logger.info("Key cache is older than 24 h; downloading it again")
            return None
        return entry.devices

    def _save(self, devices: list[BeamerDevice]) -> None:
        entry = KeyCacheEntry(fetched_at=self.clock(), devices=devices)
        token = self._get_fernet().encrypt(
            entry.model_dump_json(include={"fetched_at": True, "devices": {"__all__": {"id", "name", "privateKey"}}}).encode()
        )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(token)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self.path)

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self.keychain.get_or_create_fernet_key())
        return self._fernet

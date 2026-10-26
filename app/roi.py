from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from app.models import ROISettings

log = logging.getLogger(__name__)


class ROIManager:
    """Per-camera ROI and motion parameters, persisted atomically."""

    def __init__(self, path: Path, camera_names: list[str]) -> None:
        self.path = Path(path)
        self.camera_names = set(camera_names)
        self._data: dict[str, ROISettings] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        default = ROISettings()
        self._data = {name: default.model_copy() for name in self.camera_names}
        if not self.path.exists():
            self._save_locked()
            return
        try:
            raw = json.loads(self.path.read_text())
        except Exception as e:
            log.error("Cannot parse ROI file: %s", e)
            return
        for name, val in raw.items():
            if name not in self.camera_names:
                log.warning("Ignoring unknown camera key in ROI file: %r", name)
                continue
            try:
                self._data[name] = ROISettings(**val)
            except Exception as e:
                log.warning("Invalid ROI for %s: %s", name, e)
        self._save_locked()

    def _save_locked(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: v.model_dump() for k, v in self._data.items()}, indent=2))
        tmp.replace(self.path)

    def get(self, camera_name: str) -> ROISettings:
        with self._lock:
            if camera_name not in self._data:
                raise KeyError(camera_name)
            return self._data[camera_name].model_copy()

    def set(self, camera_name: str, roi: ROISettings) -> None:
        if camera_name not in self.camera_names:
            raise KeyError(camera_name)
        with self._lock:
            self._data[camera_name] = roi
            self._save_locked()

    def reset(self, camera_name: str) -> None:
        if camera_name not in self.camera_names:
            raise KeyError(camera_name)
        with self._lock:
            self._data[camera_name] = ROISettings()
            self._save_locked()

    def resolve_motion_params(
        self,
        camera_name: str,
        default_threshold: int,
        default_min_area: int,
    ) -> tuple[int, int]:
        """Return (threshold, min_area) for this camera.

        Per-camera overrides win; otherwise the supplied global defaults
        are used. Raises KeyError for unknown cameras so callers can map
        that to HTTP 404 without special-casing None.
        """
        roi = self.get(camera_name)
        threshold = roi.motion_threshold if roi.motion_threshold is not None else default_threshold
        min_area = roi.min_area if roi.min_area is not None else default_min_area
        return threshold, min_area

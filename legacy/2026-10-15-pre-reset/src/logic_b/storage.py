from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class StoredFrame:
    dataset: str
    partition: str
    path: Path
    rows: int
    sha256: str


class LocalParquetStore:
    """Small local research lake with atomic parquet writes and manifests."""

    def __init__(self, root: str | Path = "data"):
        self.root=Path(root)
        self.raw=self.root/"raw"
        self.manifests=self.root/"manifests"

    @staticmethod
    def _safe(partition: str) -> str:
        return partition.replace("\\","/").strip("/")

    def frame_path(self,dataset: str,partition: str) -> Path:
        return self.raw/dataset/f"{self._safe(partition)}.parquet"

    def manifest_path(self,dataset: str,partition: str) -> Path:
        return self.manifests/dataset/f"{self._safe(partition)}.json"

    def exists(self,dataset: str,partition: str) -> bool:
        return self.frame_path(dataset,partition).exists()

    def write_frame(
        self,
        dataset: str,
        partition: str,
        frame: pd.DataFrame,
        *,
        metadata: dict[str,Any] | None=None,
    ) -> StoredFrame:
        path=self.frame_path(dataset,partition)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+".tmp")
        frame.to_parquet(tmp,index=False)
        os.replace(tmp,path)

        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest={
            "dataset":dataset,
            "partition":self._safe(partition),
            "path":str(path),
            "rows":int(len(frame)),
            "columns":list(frame.columns),
            "sha256":digest,
            "retrieved_at":datetime.now(timezone.utc).isoformat(),
            "schema_version":1,
            "metadata":metadata or {},
        }
        mpath=self.manifest_path(dataset,partition)
        mpath.parent.mkdir(parents=True,exist_ok=True)
        mtmp=mpath.with_suffix(".json.tmp")
        mtmp.write_text(
            json.dumps(manifest,ensure_ascii=False,indent=2),
            encoding="utf-8",
        )
        os.replace(mtmp,mpath)
        return StoredFrame(dataset,partition,path,len(frame),digest)

    def read_frame(self,dataset: str,partition: str) -> pd.DataFrame:
        path=self.frame_path(dataset,partition)
        if not path.exists():
            raise FileNotFoundError(
                f"missing dataset={dataset} partition={partition}: {path}"
            )
        return pd.read_parquet(path)

    def read_optional(
        self,dataset: str,partition: str
    ) -> pd.DataFrame | None:
        return (
            self.read_frame(dataset,partition)
            if self.exists(dataset,partition)
            else None
        )

    def list_partitions(self,dataset: str) -> list[str]:
        root=self.raw/dataset
        if not root.exists():
            return []
        return sorted(
            str(p.relative_to(root)).removesuffix(".parquet")
            for p in root.rglob("*.parquet")
        )

    def read_all_parts(self,dataset: str) -> pd.DataFrame:
        parts=self.list_partitions(dataset)
        if not parts:
            return pd.DataFrame()
        frames=[self.read_frame(dataset,p) for p in parts]
        return pd.concat(frames,ignore_index=True).drop_duplicates()

    def verify(self,dataset: str,partition: str) -> bool:
        path=self.frame_path(dataset,partition)
        mpath=self.manifest_path(dataset,partition)
        if not path.exists() or not mpath.exists():
            return False
        expected=json.loads(
            mpath.read_text(encoding="utf-8")
        )["sha256"]
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        return actual==expected

import csv
import hashlib
from pathlib import Path, PurePosixPath


class SourceFiles:
    def __init__(self, root):
        self.root = Path(root)
        self.redactions = {}
        path = self.root / "corpus/REDACTIONS.csv"
        if path.exists():
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    if row["document_id"] in self.redactions:
                        raise ValueError("Duplicate redaction identity")
                    self.redactions[row["document_id"]] = row

    def read(self, row):
        relative = PurePosixPath(row["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source path")
        path = self.root / relative
        if not path.is_file():
            raise FileNotFoundError(row["relative_path"])
        data = path.read_bytes()
        redaction = self.redactions.get(row.get("document_id"))
        if row.get("layout_status") == "REDACTED_SECRET":
            if (not redaction or
                redaction["original_path"] != row["original_path"] or
                redaction["original_sha256"] != row["sha256"]):
                raise ValueError("Redaction registry does not bind the upstream identity")
            if (len(data) != int(redaction["distributed_bytes"]) or
                hashlib.sha256(data).hexdigest() != redaction["distributed_sha256"]):
                raise ValueError("Distributed redacted-byte identity mismatch")
        else:
            if redaction:
                raise ValueError("Registered redaction is not marked in the manifest")
            blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            if (len(data) != int(row["bytes"]) or
                hashlib.sha256(data).hexdigest() != row["sha256"] or
                (row["git_blob_sha1"] and blob != row["git_blob_sha1"])):
                raise ValueError("Source-byte identity mismatch: " + row["relative_path"])
        return data

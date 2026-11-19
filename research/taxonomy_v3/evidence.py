"""Verify curated mappings against frozen bytes and inspectable document text."""
import hashlib
import json
from pathlib import Path
import re
from .model import normalize_name


def verify_documents(references: list[dict], snapshot_date: str | None = None) -> list[dict]:
    root = Path(__file__).parent.resolve()
    verified = []
    for reference in references:
        path = (root / reference['manifest']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('evidence path escapes research directory')
        obj = json.loads(path.read_text())
        if obj.get('status') != 'ok':
            raise ValueError('failed acquisition cannot certify a mapping')
        if snapshot_date and obj['observed_at'][:10] > snapshot_date:
            raise ValueError('evidence was captured after classification snapshot')
        for field, digest in [('raw_path','raw_sha256'),('text_path','text_sha256')]:
            artifact = (path.parent/obj[field]).resolve()
            if not artifact.is_relative_to(root) or hashlib.sha256(artifact.read_bytes()).hexdigest() != obj[digest]:
                raise ValueError('evidence byte hash mismatch')
        text = (path.parent/obj['text_path']).read_text()
        normalized = normalize_name(text).upper()
        for token in reference.get('required_tokens', []):
            if normalize_name(token).upper() not in normalized:
                raise ValueError(f'asserted evidence token absent: {token}')
        for pattern in reference.get('required_patterns', []):
            if re.search(pattern,text,re.MULTILINE) is None:
                raise ValueError(f'asserted evidence table row absent: {pattern}')
        verified.append(obj)
    return verified

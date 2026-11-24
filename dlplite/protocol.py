"""Version 1 inspection envelope and canonical content digest."""

import hashlib
import json
import re
from importlib.resources import files

import rfc8785
from jsonschema import Draft202012Validator

MAX_INSPECTION_REQUEST_BYTES = 4 * 1024 * 1024
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
MEDIA_TYPES = {"application/json", "text/plain", "text/markdown", "text/event-stream"}
SCHEMAS = json.loads(files("dlplite").joinpath("inspection.schema.json").read_bytes())["$defs"]
REQUEST = Draft202012Validator(SCHEMAS["ContentInspectionRequest"])


class InvalidInspection(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def canonical(value):
    return rfc8785.dumps(value)


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return value


def parse_json(raw):
    try:
        value = json.loads(raw, object_pairs_hook=unique_object)
        canonical(value)
    except (ValueError, RecursionError, rfc8785.CanonicalizationError):
        raise InvalidInspection("Invalid JSON") from None
    return value


def validate_request(document):
    if (
        not REQUEST.is_valid(document)
        or document["media_type"] not in MEDIA_TYPES
        or digest(document["content"]) != document["inspection_digest"]
    ):
        raise InvalidInspection("Invalid inspection request")
    return document


def read_token(path):
    token = path.read_bytes().strip()
    if not re.fullmatch(rb"[\x21-\x7e]{32,}", token):
        raise InvalidInspection(
            "Use an inspection token of at least 32 printable ASCII bytes without spaces"
        )
    return token

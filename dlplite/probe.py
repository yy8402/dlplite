"""Verify authenticated HTTPS readiness and the gateway's configured identity."""

import argparse
import ssl
import sys
import time
from pathlib import Path

import httpx

from .protocol import InvalidInspection, parse_json, read_token


def probe(url, gateway_id, policy_revision, *, token_file, ca_file=None, wait=0, transport=None):
    url = httpx.URL(url)
    if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
        raise InvalidInspection(
            "Readiness requires an HTTPS URL without credentials, query, or fragment"
        )
    context = ssl.create_default_context(cafile=ca_file)
    token = read_token(token_file).decode("ascii")
    expected = {"gateway_id": gateway_id, "policy_revision": policy_revision}
    deadline = time.monotonic() + wait
    with httpx.Client(
        verify=context,
        transport=transport,
        trust_env=False,
        follow_redirects=False,
        timeout=2,
        headers={"Authorization": "Bearer " + token},
    ) as client:
        while True:
            try:
                with client.stream("GET", url) as reply:
                    if reply.status_code == 200:
                        data = bytearray()
                        for chunk in reply.iter_bytes():
                            if len(data) + len(chunk) > 4096:
                                raise InvalidInspection("Invalid readiness response")
                            data.extend(chunk)
                        if parse_json(data) != expected:
                            raise InvalidInspection(
                                "Local DLP readiness returned an unexpected gateway ID or policy revision"
                            )
                        return
                    if reply.status_code != 503:
                        raise InvalidInspection(
                            f"Local DLP readiness returned HTTP {reply.status_code}"
                        )
            except httpx.TransportError:
                pass
            if time.monotonic() >= deadline:
                raise InvalidInspection("Local DLP did not become ready over authenticated HTTPS")
            time.sleep(0.25)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--gateway-id", required=True)
    parser.add_argument("--policy-revision", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--wait", type=int, default=0)
    args = parser.parse_args()
    try:
        probe(
            args.url,
            args.gateway_id,
            args.policy_revision,
            token_file=args.token_file,
            ca_file=args.ca_file,
            wait=args.wait,
        )
    except (OSError, ValueError, httpx.InvalidURL) as exc:
        detail = (
            str(exc) if isinstance(exc, InvalidInspection) else "Invalid readiness configuration"
        )
        print(detail, file=sys.stderr)
        raise SystemExit(2) from None

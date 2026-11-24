import httpx
import pytest

from dlplite.probe import probe
from dlplite.protocol import InvalidInspection

URL = "https://inspection.test:8443/health/ready"
TOKEN = "synthetic-deployment-token-for-tests"


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (200, {"gateway_id": "local-dlp", "policy_revision": "english-dlp-v1"}, None),
        (200, {"gateway_id": "local-dlp", "policy_revision": "wrong"}, "unexpected gateway ID"),
        (401, {}, "HTTP 401"),
        (503, {}, "did not become ready"),
    ],
)
def test_probe_requires_authenticated_pinned_readiness(tmp_path, status, body, error):
    token_file = tmp_path / "token.txt"
    token_file.write_text(TOKEN + "\n")

    def respond(request):
        assert request.url == URL
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        return httpx.Response(status, json=body)

    options = {"token_file": token_file, "transport": httpx.MockTransport(respond)}
    if error:
        with pytest.raises(InvalidInspection, match=error):
            probe(URL, "local-dlp", "english-dlp-v1", **options)
    else:
        probe(URL, "local-dlp", "english-dlp-v1", **options)


def test_probe_refuses_plain_http_before_reading_token(tmp_path):
    with pytest.raises(InvalidInspection, match="requires an HTTPS URL"):
        probe(
            "http://inspection.test/health/ready",
            "local-dlp",
            "english-dlp-v1",
            token_file=tmp_path / "absent",
        )

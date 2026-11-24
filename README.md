# DLPLite

DLPLite is a self-hosted HTTPS inspection gateway. It checks approved text and JSON projections with Presidio and Betterleaks and returns `permit`, `hard_deny`, or `indeterminate`. Clients own stream selection, enforcement, and transfer auditing.

The initial `english-dlp-v1` policy detects email addresses, phone numbers, credit card numbers, and US Social Security numbers with English Presidio recognizers at a minimum score of `0.5`. Betterleaks uses its bundled credential rules with live credential validation disabled and inline allow comments ignored. A match denies the inspection. A failed detector or a projection larger than 128 KiB yields `indeterminate` unless another detector already found a match. Each detector has a 1.5-second budget. Gateway logs contain verdict metadata and reason codes. Matched text and credentials stay out of those records.

## Build and run

Build the image for the Docker host's native architecture. On ARM64 hosts configured to default to AMD64, pass `--platform linux/arm64` both when building the DLPLite image and when starting its container.

```sh
docker build -t dlplite:0.1.0 .
```

Put `certificate.pem`, `key.pem`, `ca.pem`, and `token.txt` in an absolute private directory named by `dlplite_secrets`. Issue the certificate for the HTTPS hostname your client uses. The example uses `dlplite`. Create a bearer token with `openssl rand -hex 32` and make the directory readable by the gateway's runtime user.

```sh
docker network create --internal dlplite-backend
docker run -d --name dlplite-presidio --network dlplite-backend \
  ghcr.io/data-privacy-stack/presidio-analyzer:2.2.366@sha256:036d2f9b3c274fb36497383acef8f2d5aea528a014801c2c3040fb067990c79c
docker run -d --name dlplite --network dlplite-backend \
  --read-only --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$dlplite_secrets,target=/run/inspection,readonly" \
  dlplite:0.1.0 --gateway-id local-dlp --policy-revision english-dlp-v1 \
  --presidio-url http://dlplite-presidio:3000 \
  --token-file /run/inspection/token.txt \
  --tls-cert /run/inspection/certificate.pem --tls-key /run/inspection/key.pem
docker exec dlplite dlplite-probe --url https://dlplite:8443/health/ready \
  --gateway-id local-dlp --policy-revision english-dlp-v1 --wait 60 \
  --ca-file /run/inspection/ca.pem --token-file /run/inspection/token.txt
```

If clients run on a separate Docker network, attach just DLPLite to that network with the alias covered by its certificate. Presidio stays on the internal network. LASA can start the pair with `local_dlp.enabled` and select the endpoint through `inspection_profiles`. [LASA integration runbook](https://github.com/yy8402/lasa/blob/main/v0/deployment/LOCAL_DLP.md)

## HTTPS contract

`POST /inspect` accepts bearer-authenticated `application/json` up to 4 MiB. Version 1 requires an inspection ID, binding revision, client policy revision, gateway policy revision, channel, purpose, media type, projection digest, and `content`. The digest is `sha256:` followed by the lowercase hexadecimal SHA-256 of the RFC 8785 canonical `content` JSON. The schema enumerates the approved top-level projection fields by channel. [Request and response schemas](dlplite/inspection.schema.json)

A successful response echoes the version, inspection ID, gateway policy revision, and digest and supplies the gateway ID, verdict, and fixed reason codes. Clients can check all identity and digest fields before using a verdict. The gateway returns `401` for invalid authentication, `400` for invalid envelopes or digests, and `409` for a policy revision mismatch. Detector errors produce a successful HTTP response with verdict `indeterminate` and the applicable reason codes.

Authenticated `GET /health/ready` returns the gateway ID and policy revision when the analyzer is reachable and the Betterleaks executable is available. `dlplite-probe` checks TLS, authentication, and both expected fields.

## Development

```sh
uv sync --locked --all-groups --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
```

The container includes the Betterleaks binary and its license notice. [Betterleaks license](third_party/betterleaks-LICENSE)

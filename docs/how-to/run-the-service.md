# Run the designer service

## In a container

```console
docker compose up -d --build
```

The API is then on <http://localhost:8000>, and its OpenAPI documentation on
<http://localhost:8000/docs>.

```console
docker compose down
```

On an Apple Silicon machine, add `--platform linux/amd64` to the build when the
image is meant for the cluster. The nodes are x86_64, and an arm64 image starts
and immediately dies with `exec format error`.

## Without a container

```console
uv sync --group dev
uv run uvicorn edutap.pass_designer.web.app:app --reload
```

## The editor and the six routes

`/` now serves the React editor itself — the walking skeleton described in
[`docs/superpowers/specs/2026-08-27-pass-designer-editor-design.md`](../superpowers/specs/2026-08-27-pass-designer-editor-design.md).
It calls the same API below; nothing about the routes changes when it is
present. If no frontend build exists (`make build-frontend` was never run),
`/` answers `404` and the API is unaffected — see
[`tests/web/test_static.py`](../../tests/web/test_static.py).

```console
curl -s localhost:8000/designer/v1/families
curl -s localhost:8000/designer/v1/personas
curl -s localhost:8000/designer/v1/catalogue

curl -s localhost:8000/designer/v1/validate \
  -H 'content-type: application/json' \
  -d '{"draft": {"family": "loyalty", "head": {}}}'

curl -s localhost:8000/designer/v1/export \
  -H 'content-type: application/json' \
  -d '{"draft": {"family": "loyalty",
                 "head": {"issuerName": "Example University",
                          "programName": "Library",
                          "programLogo": "https://example.org/logo.png"}},
       "class_id": "ISSUER.library", "object_id": "ISSUER.specimen"}'

curl -s localhost:8000/designer/v1/import \
  -H 'content-type: application/json' \
  -d '{"family": "loyalty", "class_json": {}, "object_json": {}}'
```

`/export` answers `422` with a list of findings when the draft carries errors.
Call `/validate` first if you want warnings as well. The `programLogo` head
field is required on export because Google's own Loyalty REST reference
demands it on class creation, beyond what the class model itself enforces —
omit it and `/export` above answers `422` too, listing that as the finding.

## Using a real field catalogue

The catalogue shipped in `data/catalogue.example.json` is a neutral example.
Point the service at a real one instead:

```console
docker compose run --rm \
  -e PASS_DESIGNER_CATALOGUE_PATH=/app/data/catalogue.json \
  -v "$PWD/catalogue.json:/app/data/catalogue.json:ro" \
  designer
```

A real catalogue is never committed to this repository — it is public, and an
institution's person-data field structure does not belong in it.

## Behind a path prefix

When served under `/portale/edutap-designer`, set `PASS_DESIGNER_ROOT_PATH` to
the same prefix that Traefik strips. Both values must come from one variable in
the deployment, or the OpenAPI document advertises paths that do not answer.

**The prefix is needed at build time as well as at run time.** The frontend's
`vite build` bakes it into every asset path it emits (Vite's `base`), and
that cannot be changed after the fact by an environment variable — only the
Dockerfile's `PASS_DESIGNER_ROOT_PATH` build arg reaches it. Set the same
value for the build arg and the runtime env var:

```console
docker build --build-arg PASS_DESIGNER_ROOT_PATH=/portale/edutap-designer -t pass-designer .
docker run -e PASS_DESIGNER_ROOT_PATH=/portale/edutap-designer pass-designer
```

`compose.yml` reads the build arg from the same `PASS_DESIGNER_ROOT_PATH`
variable, defaulting to `/` (unprefixed) when it is unset.

A mismatch between the two is easy to miss: the API answers under the prefix
either way, so every health check and every `/designer/v1/...` probe stays
green. What breaks is the page itself — it loads at `200`, but its
`<script>` tag references `/assets/index-*.js` instead of
`/portale/edutap-designer/assets/index-*.js`, that request 404s, and the
browser shows a white page. If a deployed instance is unreachable and the
API still answers, check the build arg before anything else.

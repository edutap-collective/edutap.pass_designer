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

## The five routes

```console
curl -s localhost:8000/designer/v1/families
curl -s localhost:8000/designer/v1/personas

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

When served under `/portale/pass-designer`, set `PASS_DESIGNER_ROOT_PATH` to
the same prefix that Traefik strips. Both values must come from one variable in
the deployment, or the OpenAPI document advertises paths that do not answer.

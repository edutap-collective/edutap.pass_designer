// Writes the backend's OpenAPI document to frontend/openapi.json by asking
// the application for it. No server needs to be running: the FastAPI app can
// produce its schema in-process.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const script = `
import json
from edutap.pass_designer.web.app import create_app
print(json.dumps(create_app().openapi(), indent=2, sort_keys=True))
`;

const schema = execFileSync("uv", ["run", "python", "-c", script], {
  cwd: "..",
  encoding: "utf8",
  maxBuffer: 32 * 1024 * 1024,
});

writeFileSync("openapi.json", schema);
console.log(`wrote openapi.json (${schema.length} bytes)`);

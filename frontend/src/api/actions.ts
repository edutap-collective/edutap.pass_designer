import type { Draft, ExportResponse, Finding } from "./types";
import { client } from "./client";

export async function checkDraft(draft: Draft): Promise<Finding[]> {
  const { data, error } = await client.POST("/designer/v1/validate", {
    body: { draft },
  });
  if (error) throw new Error("validate failed");
  return data.findings;
}

export async function exportDraft(
  draft: Draft,
  classId: string,
  objectId: string,
): Promise<ExportResponse> {
  const { data, error, response } = await client.POST("/designer/v1/export", {
    body: { draft, class_id: classId, object_id: objectId },
  });
  if (error) {
    // 422 carries the findings list. Surfacing it as findings rather than as
    // an opaque failure is the whole reason the backend answers in that shape.
    throw Object.assign(new Error("export refused"), {
      status: response.status,
      findings: (error as { detail?: Finding[] }).detail ?? [],
    });
  }
  return data;
}

export async function importFiles(
  family: string,
  classFile: File,
  objectFile: File,
): Promise<Draft> {
  const [classJson, objectJson] = await Promise.all([
    classFile.text().then(JSON.parse),
    objectFile.text().then(JSON.parse),
  ]);
  const { data, error } = await client.POST("/designer/v1/import", {
    body: { family, class_json: classJson, object_json: objectJson },
  });
  if (error) throw new Error("import failed");
  return data;
}

/**
 * Offer one JSON file for download.
 *
 * Three separate links rather than one archive: browsers block several
 * simultaneous downloads, a ZIP costs a dependency, and the pass builder
 * manager takes the files separately anyway.
 */
export function downloadJson(name: string, value: unknown): void {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

// One place that names the schema types the application uses. Components
// import from here, never from schema.d.ts directly, so a regeneration that
// moves a type is one edit rather than many.
import type { components } from "./schema";

export type Draft = components["schemas"]["Draft"];
export type Finding = components["schemas"]["Finding"];
export type FamilyResponse = components["schemas"]["FamilyResponse"];
export type HeadField = components["schemas"]["HeadField"];
export type Persona = components["schemas"]["Persona"];
export type TextModuleDraft = components["schemas"]["TextModuleDraft"];
export type ImageModuleDraft = components["schemas"]["ImageModuleDraft"];
export type LinkModuleDraft = components["schemas"]["LinkModuleDraft"];
export type Row = components["schemas"]["Row"];
export type Cell = components["schemas"]["Cell"];
export type Line = components["schemas"]["Line"];
export type FieldRef = components["schemas"]["FieldRef"];
export type ExportResponse = components["schemas"]["ExportResponse"];
export type CatalogueField = components["schemas"]["CatalogueField"];

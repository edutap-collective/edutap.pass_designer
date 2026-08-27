// The same syntax edutap.pass_builder resolves at issuing time: ${dotted.field}
// binds, $$ is a literal dollar sign, and only values are ever touched. The
// preview walks the same path the real thing will, so what it shows is what a
// cardholder gets — with invented data.
const TOKEN = /\$\$|\$\{([^}]+)\}/g;

export function resolvePlaceholders(
  text: string,
  values: Record<string, string>,
): string {
  return text.replace(TOKEN, (match, fieldKey?: string) => {
    if (match === "$$") return "$";
    return values[fieldKey!] ?? match;
  });
}

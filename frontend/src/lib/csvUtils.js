export function guessType(values) {
  const present = values.filter((v) => v !== "" && v !== null && v !== undefined);
  if (!present.length) return "string";

  const isInt = present.every((v) => /^-?\d+$/.test(String(v).trim()));
  if (isInt) return "int";

  const isFloat = present.every((v) => /^-?\d+(\.\d+)?$/.test(String(v).trim()));
  if (isFloat) return "float";

  return "string";
}

export function countNulls(values) {
  return values.filter((v) => v === "" || v === null || v === undefined).length;
}

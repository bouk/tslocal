declare global {
  interface JSON {
    rawJSON(value: string): unknown;
  }
}

export const jsonReviver = (_key: string, value: unknown, context?: { source?: string }) => {
  if (typeof value === "number" && context?.source && !Number.isSafeInteger(value) && /^-?\d+$/.test(context.source)) {
    return BigInt(context.source);
  }
  return value;
};

export const parseJSON = (str: string) => JSON.parse(str, jsonReviver);

export const jsonReplacer = (_key: string, value: unknown) =>
  typeof value === "bigint" ? JSON.rawJSON(value.toString()) : value;

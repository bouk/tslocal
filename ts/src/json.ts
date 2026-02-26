declare global {
  interface JSON {
    rawJSON(value: string): unknown;
  }
}

/** JSON reviver that converts large integers to BigInt to avoid precision loss. */
export const jsonReviver = (_key: string, value: unknown, context?: { source?: string }) => {
  if (typeof value === "number" && context?.source && !Number.isSafeInteger(value) && /^-?\d+$/.test(context.source)) {
    return BigInt(context.source);
  }
  return value;
};

/** Parse a JSON string using {@link jsonReviver} for BigInt-safe integer handling. */
export const parseJSON = (str: string) => JSON.parse(str, jsonReviver);

/** JSON replacer that serializes BigInt values as raw JSON numbers. */
export const jsonReplacer = (_key: string, value: unknown) =>
  typeof value === "bigint" ? JSON.rawJSON(value.toString()) : value;

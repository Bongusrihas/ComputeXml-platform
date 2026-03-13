import { describe, expect, it } from "vitest";
import { countNulls, guessType } from "../src/lib/csvUtils";

describe("csvUtils", () => {
  it("detects integer type", () => {
    expect(guessType(["1", "2", "3", ""])) .toBe("int");
  });

  it("detects float type", () => {
    expect(guessType(["1.2", "2", "3.7"])) .toBe("float");
  });

  it("detects string type", () => {
    expect(guessType(["a", "1", "b"])) .toBe("string");
  });

  it("counts nullish cells", () => {
    expect(countNulls(["", null, undefined, "x"])) .toBe(3);
  });
});

import {
  EXPORT_PRESETS,
  getExportFields,
  matchingPreset,
  setExportFields,
} from "./export-fields";

describe("export fields", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to the business preset", () => {
    expect(matchingPreset(getExportFields())).toBe("business");
    expect(getExportFields()).not.toContain("seller_attio_id");
  });

  it("keeps columns in list order and reports a custom set", () => {
    setExportFields(["risks_and_gaps", "seller"]);

    expect(getExportFields()).toEqual(["seller", "risks_and_gaps"]);
    expect(matchingPreset(getExportFields())).toBeNull();
  });

  it("recognises a preset however it was ticked", () => {
    setExportFields([...EXPORT_PRESETS.everything.fields].reverse());
    expect(matchingPreset(getExportFields())).toBe("everything");
  });

  it("falls back to business when storage holds junk", () => {
    localStorage.setItem("wusool.export-fields", '["password"]');
    expect(matchingPreset(getExportFields())).toBe("business");
  });

  it("never saves an empty selection", () => {
    setExportFields(["seller"]);
    setExportFields([]);
    expect(getExportFields()).toEqual(["seller"]);
  });
});

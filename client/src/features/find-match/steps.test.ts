import { candidate, run } from "@/test/fixtures";

import { runSteps } from "./steps";

describe("runSteps", () => {
  it("marks matching active while the run is running", () => {
    expect(runSteps(run({ state: "running", completed_at: null })).match).toBe(
      "active",
    );
  });

  it.each(["stale", "failed"] as const)(
    "flags matching on a %s run",
    (state) => {
      const steps = runSteps(run({ state }));
      expect(steps.match).toBe("attention");
      expect(steps.shortlist).toBe("upcoming");
    },
  );

  it("keeps the shortlist active until every candidate is reviewed", () => {
    expect(runSteps(run()).shortlist).toBe("active");
    expect(runSteps(run()).export).toBe("upcoming");
  });

  it("skips discovery and opens export once the shortlist is reviewed", () => {
    const steps = runSteps(
      run({ candidates: [candidate({ status: "APPROVED" })] }),
    );
    expect(steps.shortlist).toBe("done");
    expect(steps.discovery).toBe("skipped");
    expect(steps.export).toBe("active");
  });

  it("holds discovery active while it searches", () => {
    const steps = runSteps(
      run({
        low_match_quality: true,
        discovery: { status: "running", message: null, notes: [] },
      }),
    );
    expect(steps.discovery).toBe("active");
  });

  it("flags discovery that couldn't run", () => {
    const steps = runSteps(
      run({
        candidates: [candidate({ status: "REJECTED" })],
        discovery: {
          status: "unavailable",
          message: "Daily discovery limit reached.",
          notes: [],
        },
      }),
    );
    expect(steps.discovery).toBe("attention");
  });
});

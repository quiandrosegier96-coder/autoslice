import assert from "node:assert/strict";
import test from "node:test";
import {
  acceptsThreeMf,
  autoSliceFilename,
  canAnalyze,
  collectRecommendations,
  fallbackNotice,
  isConversionBlocked,
} from "../src/lib/autoslice-flow.ts";

const analysis = {
  optimization_plan: {
    changes: [{ setting: "layer_height", old_value: 0.3, new_value: 0.2, reason: "quality", rule: "profile", confidence: "high" }],
    support_changes: [], geometry_changes: [], placement_changes: [], blocked: [],
  },
  printability: { status: "good" },
} as never;

test("upload accepts supported 3MF filenames", () => {
  assert.equal(acceptsThreeMf("bambu-project.3MF"), true);
  assert.equal(acceptsThreeMf("model.stl"), false);
});

test("analysis requires an upload job and target selection", () => {
  assert.equal(canAnalyze("job-1", "kobra-s1"), true);
  assert.equal(canAnalyze("job-1", ""), false);
});

test("target selection controls analysis eligibility", () => {
  assert.equal(canAnalyze("", "kobra-s1"), false);
});

test("recommendations retain backend old, new, reason and confidence", () => {
  assert.deepEqual(collectRecommendations(analysis)[0], {
    setting: "layer_height", old_value: 0.3, new_value: 0.2,
    reason: "quality", rule: "profile", confidence: "high",
  });
});

test("conversion is blocked by backend hard diagnostics", () => {
  assert.equal(isConversionBlocked(analysis), false);
  assert.equal(isConversionBlocked({ ...analysis, printability: { status: "blocked" } } as never), true);
});

test("failure fallback is explicit", () => {
  assert.match(fallbackNotice(true), /legacy compatibility route used/);
  assert.equal(fallbackNotice(false), "");
});

test("download uses the AutoSlice output convention", () => {
  assert.equal(autoSliceFilename("dragon.3mf"), "dragon_AutoSlice.3mf");
});

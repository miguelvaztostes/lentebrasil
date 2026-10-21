import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("public disclaimer and empty-data language remain visible", async () => {
  const [footer, dashboard, indicator] = await Promise.all([
    readFile(new URL("../components/Footer.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/Dashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/IndicatorDetail.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(footer, /Observatório cívico independente/);
  assert.match(dashboard, /não há observações validadas/);
  assert.match(dashboard, /municipios\/\$\{encodeURIComponent\(municipalityCode\)\}\/summary/);
  assert.match(indicator, /municipality=\$\{encodeURIComponent\(municipalityCode\)\}/);
  assert.doesNotMatch(dashboard, /mock|fixture/i);
});

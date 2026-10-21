import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("public disclaimer and empty-data language remain visible", async () => {
  const [footer, dashboard, indicator, search, home] = await Promise.all([
    readFile(new URL("../components/Footer.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/Dashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/IndicatorDetail.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/SearchPortal.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(footer, /Observatório cívico independente/);
  assert.match(dashboard, /não há observações validadas/);
  assert.match(dashboard, /municipios\/\$\{encodeURIComponent\(municipalityCode\)\}\/summary/);
  assert.match(indicator, /municipality=\$\{encodeURIComponent\(municipalityCode\)\}/);
  assert.doesNotMatch(dashboard, /mock|fixture/i);
  assert.match(footer, /Lente Brasil/);
  assert.match(home, /165 candidatos, não 165 integrações/);
  assert.match(search, /router\.push\(`\/buscar\?\$\{params\.toString\(\)\}`\)/);
  assert.match(search, /Fonte descoberta, integração técnica e dado publicado/);
});

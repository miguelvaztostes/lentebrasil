import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("institutional identity and empty-data language remain visible", async () => {
  const [footer, dashboard, indicator, search, home, education, school, transparency, sectors, agriculture, openData, municipalitySector, research] = await Promise.all([
    readFile(new URL("../components/Footer.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/Dashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/IndicatorDetail.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/SearchPortal.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/EducationDashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/SchoolDetail.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/TransparencyDashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/SectorDashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/AgricultureDashboard.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/dados-abertos/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/MunicipalitySector.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/ResearchWorkbench.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(footer, /Observatório de dados públicos municipais/);
  assert.match(footer, /https:\/\/vazdeveloper\.com\.br\//);
  assert.match(footer, /Origem, atualização e licença informadas/);
  assert.doesNotMatch(footer, /2030|Não representa oficialmente/);
  assert.match(dashboard, /não há observações validadas/);
  assert.match(dashboard, /municipios\/\$\{encodeURIComponent\(municipalityCode\)\}\/summary/);
  assert.match(indicator, /municipality=\$\{encodeURIComponent\(municipalityCode\)\}/);
  assert.doesNotMatch(dashboard, /mock|fixture/i);
  assert.match(footer, /Lente Brasil/);
  assert.match(home, /165 candidatos, não 165 integrações/);
  assert.match(search, /router\.push\(`\/buscar\?\$\{params\.toString\(\)\}`\)/);
  assert.match(search, /Fonte descoberta, integração técnica e dado publicado/);
  assert.match(education, /nunca são convertidos em zero/);
  assert.match(education, /education\/municipalities/);
  assert.match(education, /Saeb 2023/);
  assert.match(education, /PNAE 2024/);
  assert.match(education, /Não representa pagamento realizado/);
  assert.match(school, /não armazena endereço, telefone, CNPJ nem dados individuais/);
  assert.match(transparency, /Não há classificação automática de irregularidade/);
  assert.match(transparency, /Ausência não é exibida como zero/);
  assert.match(transparency, /exports\/procurements\.csv/);
  assert.match(transparency, /Visão geral da transparência/);
  assert.match(transparency, /Esses eventos não são compensados automaticamente/);
  assert.match(sectors, /PIB municipal anual/);
  assert.match(sectors, /não é estoque/);
  assert.match(sectors, /Ausência de carga não significa zero/);
  assert.match(sectors, /não mede circulação diária/);
  assert.match(agriculture, /Quantidade produzida — PAM 2024/);
  assert.match(agriculture, /ausência continua indisponível/);
  assert.match(openData, /Consultas maiores usam/);
  assert.match(openData, /Matriz 165 fontes/);
  assert.match(municipalitySector, /Matriz de fontes do setor/);
  assert.match(research, /Indisponível não é zero/);
  assert.match(research, /scope_required/);
  assert.match(research, /export\.csv/);
  assert.match(research, /Parquet/);
  assert.match(research, /geo\/boundaries/);
});

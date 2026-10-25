import assert from "node:assert/strict";
import test from "node:test";

const baseUrl = process.env.E2E_BASE_URL;

test("territorial routes render and shared search URL is accepted", { skip: !baseUrl }, async () => {
  const paths = [
    "/",
    "/brasil",
    "/buscar?q=Ribeirao&uf=SP&status=discovered",
    "/pesquisa?indicador=observation%3Apopulation_estimated&municipios=3543402%2C3509502%2C3550308",
    "/comparar?indicador=observation%3Apopulation_estimated&municipios=3543402%2C3509502%2C3550308",
    "/municipios/3543402",
    "/municipios/3509502",
    "/municipios/3550308",
    "/fontes/LNT-0001",
  ];
  for (const path of paths) {
    const response = await fetch(`${baseUrl}${path}`);
    assert.equal(response.status, 200, path);
    const html = await response.text();
    assert.match(html, /Lente Brasil/, path);
  }
});

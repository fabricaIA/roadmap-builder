import assert from "node:assert/strict";
import test from "node:test";
import {
  editableSnapshot,
  formToConfig,
  moveItem,
  templateToForm,
} from "../src/projects/editor.js";

const config = {
  schedule: {
    project_start_date: null,
    project_date_fields: { start: "Início especial", end: "Fim especial" },
    milestone_durations: {
      M1: { value: 2, unit: "days" },
      M2: { value: 1, unit: "months" },
    },
  },
  milestones: [
    { key: "M1", title: "Primeira", description: "Fase inicial" },
    { key: "M2", title: "Segunda", description: "Final" },
  ],
  labels: [{ name: "tipo:a", color: "123456", description: "Etiqueta" }],
  issues: [
    {
      title: "Card A",
      description: "Objetivo",
      milestone: "M1",
      labels: ["tipo:a"],
      entregaveis: ["A", "B"],
      criterios_aceite: ["Validado"],
    },
    {
      title: "Card B",
      description: "Outro",
      milestone: "M2",
      labels: [],
      entregaveis: ["C"],
      criterios_aceite: ["Revisado"],
    },
  ],
};
const form = () => ({
  ...templateToForm(config),
  owner: "original",
  repo: "repo",
  projectTitle: "Título",
  projectNumber: "",
});
const signature = (value, phases = ["M1", "M2"]) =>
  JSON.stringify(editableSnapshot(value, phases));

test("carregar e serializar preserva todos os campos, ordem e data nula", () => {
  assert.deepEqual(formToConfig(form()), config);
});

test("edições de cada categoria alteram a assinatura, sem mutar o snapshot original", () => {
  const changes = [
    (f) => {
      f.owner = "outro";
    },
    (f) => {
      f.repo = "outro";
    },
    (f) => {
      f.projectTitle = "Outro título";
    },
    (f) => {
      f.projectNumber = 9;
    },
    (f) => {
      f.projectStartDate = "2026-10-02";
    },
    (f) => {
      f.dateFieldEnd = "Conclusão";
    },
    (f) => {
      f.milestones[0].title = "Editada";
    },
    (f) => {
      f.milestones[0].value = 20;
    },
    (f) => {
      f.milestones.reverse();
    },
    (f) => {
      f.labels[0].color = "#abcdef";
    },
    (f) => {
      f.issues[0].description = "Editada";
    },
    (f) => {
      f.issues[0].entregaveis.pop();
    },
    (f) => {
      f.issues[0].criterios_aceite.push("Novo");
    },
    (f) => {
      f.issues.reverse();
    },
    (f) => {
      f.issues.pop();
    },
    (f) => {
      f.issues.push({ ...f.issues[0], title: "Adicionado" });
    },
  ];
  const original = structuredClone(config);
  for (const change of changes) {
    const edited = form();
    change(edited);
    assert.notEqual(signature(edited), signature(form()));
    assert.deepEqual(config, original);
  }
  assert.notEqual(signature(form(), ["M1"]), signature(form()));
});

test("reverter a alteração volta à assinatura original", () => {
  const edited = form();
  edited.owner = "novo";
  edited.owner = "original";
  assert.equal(signature(edited), signature(form()));
});

test("reordenar preserva conteúdo e não altera o array original", () => {
  const items = structuredClone(config.issues);
  const moved = moveItem(items, 0, 1);
  assert.equal(moved[0].title, "Card B");
  assert.equal(items[0].title, "Card A");
  assert.deepEqual(moveItem(moved, 1, -1), items);
});

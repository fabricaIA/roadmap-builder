// Conversão compartilhada pelo carregamento, comparação e salvamento do editor.
export function templateToForm(config) {
  const durations = config.schedule?.milestone_durations || {};
  return {
    projectStartDate: config.schedule?.project_start_date || "",
    dateFieldStart:
      config.schedule?.project_date_fields?.start || "Início previsto",
    dateFieldEnd: config.schedule?.project_date_fields?.end || "Fim previsto",
    milestones: (config.milestones || []).map((m) => ({
      ...m,
      description: m.description || "",
      value: durations[m.key]?.value ?? 1,
      unit: durations[m.key]?.unit ?? "months",
    })),
    labels: (config.labels || []).map((label) => ({
      ...label,
      description: label.description || "",
      color: `#${(label.color || "0052CC").replace(/^#/, "")}`,
    })),
    issues: structuredClone(config.issues || []).map((issue) => ({
      ...issue,
      labels: issue.labels || [],
      description:
        issue.description ??
        "Executar esta atividade conforme o processo da Fabrica de IA.",
      entregaveis: issue.entregaveis || [
        "Evidencia principal anexada",
        "Criterios de aceite validados",
      ],
      criterios_aceite: issue.criterios_aceite || [
        "Resultado revisado com stakeholders",
        "Registro no Project atualizado",
      ],
    })),
  };
}

export function formToConfig(form) {
  return {
    schedule: {
      project_start_date: form.projectStartDate || null,
      project_date_fields: {
        start: form.dateFieldStart,
        end: form.dateFieldEnd,
      },
      milestone_durations: Object.fromEntries(
        form.milestones.map((m) => [
          m.key,
          { value: Number(m.value), unit: m.unit },
        ]),
      ),
    },
    milestones: form.milestones.map(({ key, title, description }) => ({
      key,
      title,
      description,
    })),
    labels: form.labels.map((label) => ({
      ...label,
      color: label.color.replace(/^#/, ""),
    })),
    issues: structuredClone(form.issues),
  };
}

export function editableSnapshot(form, selectedPhases) {
  return {
    owner: form.owner.trim(),
    repo: form.repo.trim(),
    title: form.projectTitle,
    project_number:
      form.projectNumber === "" ? null : Number(form.projectNumber),
    phase_keys:
      selectedPhases.length === form.milestones.length ? null : selectedPhases,
    config: formToConfig(form),
  };
}

export function moveItem(items, index, direction) {
  const next = index + direction;
  if (next < 0 || next >= items.length) return items;
  const copy = [...items];
  [copy[index], copy[next]] = [copy[next], copy[index]];
  return copy;
}

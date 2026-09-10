import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../api/client";
import { useAuth } from "../auth/useAuth";
import "../App.css";

function ProjectWizard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState(null);
  const [isTitleCustomized, setIsTitleCustomized] = useState(false);
  // F2: preferência explícita do usuário para "criar painel".
  const [createProjectPref, setCreateProjectPref] = useState(true);
  // F3: carregamento/erro do template.
  const [templateLoading, setTemplateLoading] = useState(true);
  const [templateError, setTemplateError] = useState("");

  const [formData, setFormData] = useState({
    owner: "",
    repo: "",
    apply: true,
    createProject: true,
    projectTitle: "Roadmap",
    projectNumber: "",
    projectStartDate: new Date().toISOString().split("T")[0],
    milestones: [],
    labels: [],
    issues: [],
  });

  const deriveProjectTitle = (owner, repo) => {
    const o = (owner || "").trim();
    const r = (repo || "").trim();
    if (o && r) return `${o}/${r} - Roadmap`;
    if (o || r) return `${o || r} - Roadmap`;
    return "Roadmap";
  };

  const loadTemplate = useCallback(async () => {
    try {
      const data = await apiFetch("/api/backlog-template", {
        allowUnauthorized: true,
      });
      const durations = data.schedule?.milestone_durations || {};

      const normalizedMilestones = (data.milestones || []).map((m) => ({
        key: m.key,
        title: m.title || "",
        description: m.description || "",
        value: durations[m.key]?.value ?? m.value ?? 1,
        unit: durations[m.key]?.unit ?? m.unit ?? "months",
      }));

      const normalizedLabels = (data.labels || []).map((l) => ({
        name: l.name,
        color: l.color?.startsWith("#") ? l.color : `#${l.color || "0052CC"}`,
        description: l.description || "",
      }));

      setTemplateError("");
      setFormData((prev) => ({
        ...prev,
        projectStartDate:
          data.schedule?.project_start_date || prev.projectStartDate,
        milestones: normalizedMilestones,
        labels: normalizedLabels,
        issues: data.issues || [],
      }));
    } catch (error) {
      console.error("Erro ao carregar backlog template:", error);
      setTemplateError(
        "Não foi possível carregar o modelo de backlog do servidor. " +
          "Verifique se o backend está no ar e tente novamente.",
      );
    } finally {
      setTemplateLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTemplate();
  }, [loadTemplate]);

  const retryLoadTemplate = () => {
    setTemplateLoading(true);
    setTemplateError("");
    loadTemplate();
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    const newValue = type === "checkbox" ? checked : value;

    if (name === "createProject") {
      setCreateProjectPref(checked);
    }

    // F9: título é estado derivado; para de derivar enquanto houver texto manual.
    let titleCustomized = isTitleCustomized;
    if (name === "projectTitle") {
      titleCustomized = value.trim() !== "";
      setIsTitleCustomized(titleCustomized);
    }

    setFormData((prev) => {
      const next = { ...prev, [name]: newValue };
      if (
        !titleCustomized &&
        (name === "owner" || name === "repo" || name === "projectTitle")
      ) {
        next.projectTitle = deriveProjectTitle(next.owner, next.repo);
      }
      return next;
    });
  };

  // --- Handlers de Milestones ---
  const handleMilestoneChange = (index, field, value) => {
    const list = [...formData.milestones];
    list[index][field] = value;
    setFormData({ ...formData, milestones: list });
  };

  const addMilestone = () => {
    const nextKey = `M${formData.milestones.length + 1}`;
    setFormData({
      ...formData,
      milestones: [
        ...formData.milestones,
        {
          key: nextKey,
          title: `${nextKey} - Novo Marco`,
          description: "",
          value: 1,
          unit: "months",
        },
      ],
    });
  };

  const removeMilestone = (index) => {
    setFormData({
      ...formData,
      milestones: formData.milestones.filter((_, i) => i !== index),
    });
  };

  // --- Handlers de Labels ---
  const handleLabelChange = (index, field, value) => {
    const list = [...formData.labels];
    list[index][field] = value;
    setFormData({ ...formData, labels: list });
  };

  const addLabel = () => {
    setFormData({
      ...formData,
      labels: [
        ...formData.labels,
        { name: "nova:label", color: "#0052CC", description: "" },
      ],
    });
  };

  const removeLabel = (index) => {
    setFormData({
      ...formData,
      labels: formData.labels.filter((_, i) => i !== index),
    });
  };

  // --- Handlers de Issues ---
  const handleIssueChange = (index, field, value) => {
    const list = [...formData.issues];
    list[index][field] = value;
    setFormData({ ...formData, issues: list });
  };

  const handleIssueArrayChange = (issueIndex, arrayField, itemIndex, value) => {
    const list = [...formData.issues];
    list[issueIndex][arrayField][itemIndex] = value;
    setFormData({ ...formData, issues: list });
  };

  const addIssueItem = (issueIndex, arrayField) => {
    const list = [...formData.issues];
    list[issueIndex][arrayField].push("");
    setFormData({ ...formData, issues: list });
  };

  const removeIssueItem = (issueIndex, arrayField, itemIndex) => {
    const list = [...formData.issues];
    list[issueIndex][arrayField] = list[issueIndex][arrayField].filter(
      (_, i) => i !== itemIndex,
    );
    setFormData({ ...formData, issues: list });
  };

  const handleToggleIssueLabel = (issueIndex, labelName) => {
    const list = [...formData.issues];
    const currentLabels = list[issueIndex].labels || [];
    if (currentLabels.includes(labelName)) {
      list[issueIndex].labels = currentLabels.filter((l) => l !== labelName);
    } else {
      list[issueIndex].labels = [...currentLabels, labelName];
    }
    setFormData({ ...formData, issues: list });
  };

  const addIssue = () => {
    setFormData({
      ...formData,
      issues: [
        ...formData.issues,
        {
          title: "[Atividade] Nova Atividade",
          milestone: formData.milestones[0]?.key || "M1",
          labels: [],
          description: "",
          entregaveis: [""],
          criterios_aceite: [""],
        },
      ],
    });
  };

  const removeIssue = (index) => {
    setFormData({
      ...formData,
      issues: formData.issues.filter((_, i) => i !== index),
    });
  };

  const nextStep = () => setStep((prev) => prev + 1);
  const prevStep = () => setStep((prev) => prev - 1);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    setResult(null);

    const milestone_durations = {};
    formData.milestones.forEach((m) => {
      milestone_durations[m.key] = {
        value: parseInt(m.value, 10) || 1,
        unit: m.unit,
      };
    });

    const formattedLabels = formData.labels.map((l) => ({
      name: l.name,
      color: l.color.replace("#", ""),
      description: l.description,
    }));

    const formattedMilestones = formData.milestones.map((m) => ({
      key: m.key,
      title: m.title,
      description: m.description,
    }));

    const hasProjectNumber = Boolean(
      formData.projectNumber && parseInt(formData.projectNumber, 10) > 0,
    );

    const payload = {
      owner: formData.owner,
      repo: formData.repo,
      apply: formData.apply,
      create_project: hasProjectNumber ? false : formData.createProject,
      project_title: formData.projectTitle,
      project_number: hasProjectNumber
        ? parseInt(formData.projectNumber, 10)
        : null,
      project_start_date: formData.projectStartDate,
      config: {
        schedule: {
          project_start_date: formData.projectStartDate,
          project_date_fields: {
            start: "Início previsto",
            end: "Fim previsto",
          },
          milestone_durations: milestone_durations,
        },
        labels: formattedLabels,
        milestones: formattedMilestones,
        issues: formData.issues,
      },
    };

    try {
      // PR2: cria/registra o projeto (o backend também insere a linha Project).
      const data = await apiFetch("/api/projects", {
        method: "POST",
        body: payload,
      });

      // F1: o backend pode responder sucesso total ou parcial.
      setResult(data);
      const issuesCount = (data.issues_created || []).length;
      if (data.status === "partial") {
        setMessage(
          `Parcial: ${issuesCount} issue(s) criada(s). A etapa do painel de projeto não foi concluída. ` +
            (data.project_error || ""),
        );
      } else {
        setMessage(
          `Sucesso! Roadmap aplicado com ${issuesCount || formData.issues.length} issue(s).`,
        );
      }
      // Vai para o detalhe do projeto recém-registrado.
      if (data.project?.id) {
        setTimeout(() => navigate(`/projects/${data.project.id}`), 900);
      }
    } catch (error) {
      setMessage(`Erro: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-wrapper">
      <div className="form-container-wrapper">
        <button onClick={() => navigate("/")} className="btn-top-welcome">
          ← Voltar
        </button>

        <div className="container">
          <div className="stepper">
            {[
              "Início",
              "Durações",
              "Labels",
              "Marcos",
              "Issues",
              "Revisão",
            ].map((labelName, i) => {
              const num = i + 1;
              return (
                <div
                  key={num}
                  className={`step ${step >= num ? "active" : ""}`}
                >
                  <div className="step-circle">{num}</div>
                  <div className="step-label">{labelName}</div>
                </div>
              );
            })}
          </div>

          <div className="form-content">
            {!user?.has_pat && (
              <div className="message error" style={{ marginBottom: "16px" }}>
                Você ainda não configurou um PAT do GitHub.{" "}
                <Link to="/profile">Configurar no perfil</Link> antes de
                aplicar.
              </div>
            )}

            {/* F3: template não carregou */}
            {templateError && (
              <div className="message error" style={{ marginBottom: "16px" }}>
                {templateError}
                <div style={{ marginTop: "8px" }}>
                  <button
                    type="button"
                    onClick={retryLoadTemplate}
                    className="btn-secondary"
                    disabled={templateLoading}
                  >
                    {templateLoading ? "Carregando..." : "Tentar novamente"}
                  </button>
                </div>
              </div>
            )}
            {templateLoading && !templateError && (
              <div className="message" style={{ marginBottom: "16px" }}>
                Carregando modelo de backlog do servidor...
              </div>
            )}

            {/* PASSO 1 */}
            {step === 1 && (
              <div className="step-panel">
                <h2>Configurações Iniciais</h2>
                <p
                  className="subtitle"
                  style={{
                    color: "#666",
                    fontSize: "0.9rem",
                    marginBottom: 16,
                  }}
                >
                  O acesso ao GitHub usa o PAT configurado no seu{" "}
                  <Link to="/profile">perfil</Link>.
                </p>
                <div className="row">
                  <div className="form-group">
                    <label>Owner *</label>
                    <input
                      type="text"
                      name="owner"
                      value={formData.owner}
                      onChange={handleInputChange}
                      placeholder="Ex: JuanPabloFAC"
                    />
                  </div>
                  <div className="form-group">
                    <label>Repositório *</label>
                    <input
                      type="text"
                      name="repo"
                      value={formData.repo}
                      onChange={handleInputChange}
                      placeholder="Ex: roadmap3"
                    />
                  </div>
                </div>
                <div className="row">
                  <div className="form-group">
                    <label>Título do Projeto</label>
                    <input
                      type="text"
                      name="projectTitle"
                      value={formData.projectTitle}
                      onChange={handleInputChange}
                      placeholder="Ex: owner/repo - Roadmap"
                    />
                  </div>
                  <div className="form-group">
                    <label>Data de Início</label>
                    <input
                      type="date"
                      name="projectStartDate"
                      value={formData.projectStartDate}
                      onChange={handleInputChange}
                    />
                  </div>
                </div>

                <div className="form-group" style={{ marginTop: "10px" }}>
                  <label>Número de um Project existente (Opcional)</label>
                  <input
                    type="number"
                    min="1"
                    name="projectNumber"
                    value={formData.projectNumber}
                    onChange={(e) => {
                      const val = e.target.value;
                      setFormData((prev) => ({
                        ...prev,
                        projectNumber: val,
                        // F2
                        createProject: val ? false : createProjectPref,
                      }));
                    }}
                    placeholder="Ex: 3 (deixe em branco para criar um novo projeto)"
                  />
                  <small
                    style={{
                      color: "#666",
                      fontSize: "0.8rem",
                      marginTop: "4px",
                    }}
                  >
                    Se informado, as issues serão vinculadas a este projeto
                    existente em vez de criar um novo.
                  </small>
                </div>
              </div>
            )}

            {/* PASSO 2 */}
            {step === 2 && (
              <div className="step-panel">
                <h2>Durações dos Marcos (Milestones Durations)</h2>
                <p
                  className="subtitle"
                  style={{
                    color: "#666",
                    fontSize: "0.9rem",
                    marginBottom: "20px",
                  }}
                >
                  Defina o identificador e o tempo de duração de cada marco para
                  o cálculo automático do cronograma.
                </p>
                {formData.milestones.map((m, index) => (
                  <div key={index} className="dynamic-row">
                    <input
                      type="text"
                      value={m.key}
                      onChange={(e) =>
                        handleMilestoneChange(index, "key", e.target.value)
                      }
                      placeholder="Ex: M1"
                      className="short-input"
                    />
                    <input
                      type="number"
                      min="1"
                      value={m.value}
                      onChange={(e) =>
                        handleMilestoneChange(index, "value", e.target.value)
                      }
                      className="short-input"
                    />
                    <select
                      value={m.unit}
                      onChange={(e) =>
                        handleMilestoneChange(index, "unit", e.target.value)
                      }
                    >
                      <option value="days">Dias</option>
                      <option value="months">Meses</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => removeMilestone(index)}
                      className="btn-remove"
                      style={{
                        visibility:
                          formData.milestones.length === 1
                            ? "hidden"
                            : "visible",
                      }}
                    >
                      X
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addMilestone}
                  className="btn-secondary"
                  style={{ marginTop: "10px" }}
                >
                  + Adicionar Duração
                </button>
              </div>
            )}

            {/* PASSO 3 */}
            {step === 3 && (
              <div className="step-panel">
                <h2>Etiquetas (Labels)</h2>
                <p
                  className="subtitle"
                  style={{
                    color: "#666",
                    fontSize: "0.9rem",
                    marginBottom: "20px",
                  }}
                >
                  Configure o nome, a cor de identificação e a descrição de cada
                  label.
                </p>
                {formData.labels.map((l, index) => (
                  <div key={index} className="label-row">
                    <input
                      type="text"
                      value={l.name}
                      onChange={(e) =>
                        handleLabelChange(index, "name", e.target.value)
                      }
                      placeholder="Ex: fase:i"
                      className="label-name-input"
                    />
                    <div className="color-picker-wrapper">
                      <input
                        type="color"
                        value={
                          l.color.startsWith("#") ? l.color : `#${l.color}`
                        }
                        onChange={(e) =>
                          handleLabelChange(index, "color", e.target.value)
                        }
                      />
                      <input
                        type="text"
                        value={l.color}
                        onChange={(e) =>
                          handleLabelChange(index, "color", e.target.value)
                        }
                        placeholder="#1D76DB"
                        className="color-text-input"
                      />
                    </div>
                    <input
                      type="text"
                      value={l.description}
                      onChange={(e) =>
                        handleLabelChange(index, "description", e.target.value)
                      }
                      placeholder="Descrição da label"
                      className="label-desc-input"
                    />
                    <button
                      type="button"
                      onClick={() => removeLabel(index)}
                      className="btn-remove"
                      style={{
                        visibility:
                          formData.labels.length === 1 ? "hidden" : "visible",
                      }}
                    >
                      X
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addLabel}
                  className="btn-secondary"
                  style={{ marginTop: "10px" }}
                >
                  + Adicionar Label
                </button>
              </div>
            )}

            {/* PASSO 4 */}
            {step === 4 && (
              <div className="step-panel">
                <h2>Marcos do Projeto (Milestones)</h2>
                <p
                  className="subtitle"
                  style={{
                    color: "#666",
                    fontSize: "0.9rem",
                    marginBottom: "20px",
                  }}
                >
                  Defina os detalhes de título e descrição de cada marco do
                  roadmap.
                </p>
                {formData.milestones.map((m, index) => (
                  <div key={index} className="milestone-card">
                    <div className="milestone-top-row">
                      <input
                        type="text"
                        value={m.key}
                        onChange={(e) =>
                          handleMilestoneChange(index, "key", e.target.value)
                        }
                        placeholder="Chave"
                        className="milestone-key-input"
                      />
                      <input
                        type="text"
                        value={m.title}
                        onChange={(e) =>
                          handleMilestoneChange(index, "title", e.target.value)
                        }
                        placeholder="Título do Marco (ex: M1 - Exploração)"
                        className="milestone-title-input"
                      />
                      <button
                        type="button"
                        onClick={() => removeMilestone(index)}
                        className="btn-remove"
                        style={{
                          visibility:
                            formData.milestones.length === 1
                              ? "hidden"
                              : "visible",
                        }}
                      >
                        X
                      </button>
                    </div>
                    <div className="milestone-desc-row">
                      <textarea
                        rows="2"
                        value={m.description}
                        onChange={(e) =>
                          handleMilestoneChange(
                            index,
                            "description",
                            e.target.value,
                          )
                        }
                        placeholder="Descrição detalhada do marco..."
                        className="milestone-textarea"
                      />
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addMilestone}
                  className="btn-secondary"
                  style={{ marginTop: "10px" }}
                >
                  + Adicionar Milestone
                </button>
              </div>
            )}

            {/* PASSO 5 */}
            {step === 5 && (
              <div className="step-panel">
                <h2>Issues e Entregáveis</h2>
                <p
                  className="subtitle"
                  style={{
                    color: "#666",
                    fontSize: "0.9rem",
                    marginBottom: "20px",
                  }}
                >
                  Cadastre as atividades, entregáveis e critérios de aceite
                  vinculados aos marcos.
                </p>

                <div className="issues-scroll-container">
                  {formData.issues.map((iss, issIndex) => (
                    <div key={issIndex} className="issue-card-box">
                      <div className="issue-top-row">
                        <input
                          type="text"
                          value={iss.title}
                          onChange={(e) =>
                            handleIssueChange(issIndex, "title", e.target.value)
                          }
                          placeholder="Título da Issue (ex: [Atividade] ...)"
                          className="issue-title-input"
                        />
                        <select
                          value={iss.milestone}
                          onChange={(e) =>
                            handleIssueChange(
                              issIndex,
                              "milestone",
                              e.target.value,
                            )
                          }
                          className="issue-milestone-select"
                        >
                          {formData.milestones.map((m) => (
                            <option key={m.key} value={m.key}>
                              {m.key}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => removeIssue(issIndex)}
                          className="btn-remove"
                        >
                          X
                        </button>
                      </div>

                      <div className="issue-desc-row">
                        <textarea
                          rows="2"
                          value={iss.description}
                          onChange={(e) =>
                            handleIssueChange(
                              issIndex,
                              "description",
                              e.target.value,
                            )
                          }
                          placeholder="Descrição detalhada da issue..."
                          className="issue-textarea"
                        />
                      </div>

                      <div className="sub-section">
                        <label className="sub-section-title">
                          Etiquetas (Labels):
                        </label>
                        <div className="issue-labels-wrapper">
                          {formData.labels.map((lbl) => {
                            const isSelected = (iss.labels || []).includes(
                              lbl.name,
                            );
                            const colorHex = lbl.color.startsWith("#")
                              ? lbl.color
                              : `#${lbl.color}`;
                            return (
                              <button
                                key={lbl.name}
                                type="button"
                                onClick={() =>
                                  handleToggleIssueLabel(issIndex, lbl.name)
                                }
                                className={`chip-label ${isSelected ? "selected" : ""}`}
                                style={{
                                  backgroundColor: isSelected
                                    ? colorHex
                                    : "#f0f2f5",
                                  color: isSelected ? "#ffffff" : "#444444",
                                  borderColor: colorHex,
                                }}
                              >
                                {lbl.name} {isSelected ? "✓" : "+"}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      <div className="sub-section">
                        <label className="sub-section-title">
                          Entregáveis:
                        </label>
                        {iss.entregaveis.map((ent, eIdx) => (
                          <div key={eIdx} className="sub-row">
                            <input
                              type="text"
                              value={ent}
                              onChange={(e) =>
                                handleIssueArrayChange(
                                  issIndex,
                                  "entregaveis",
                                  eIdx,
                                  e.target.value,
                                )
                              }
                              placeholder="Ex: Ata das oficinas..."
                            />
                            <button
                              type="button"
                              onClick={() =>
                                removeIssueItem(issIndex, "entregaveis", eIdx)
                              }
                              className="btn-remove-sm"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() => addIssueItem(issIndex, "entregaveis")}
                          className="btn-text"
                        >
                          + Adicionar Entregável
                        </button>
                      </div>

                      <div className="sub-section">
                        <label className="sub-section-title">
                          Critérios de Aceite:
                        </label>
                        {iss.criterios_aceite.map((crit, cIdx) => (
                          <div key={cIdx} className="sub-row">
                            <input
                              type="text"
                              value={crit}
                              onChange={(e) =>
                                handleIssueArrayChange(
                                  issIndex,
                                  "criterios_aceite",
                                  cIdx,
                                  e.target.value,
                                )
                              }
                              placeholder="Ex: Órgão demandante valida..."
                            />
                            <button
                              type="button"
                              onClick={() =>
                                removeIssueItem(
                                  issIndex,
                                  "criterios_aceite",
                                  cIdx,
                                )
                              }
                              className="btn-remove-sm"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() =>
                            addIssueItem(issIndex, "criterios_aceite")
                          }
                          className="btn-text"
                        >
                          + Adicionar Critério
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={addIssue}
                  className="btn-secondary"
                  style={{ marginTop: "15px" }}
                >
                  + Adicionar Nova Issue
                </button>
              </div>
            )}

            {/* PASSO 6 */}
            {step === 6 && (
              <div className="step-panel">
                <h2>Revisão e Confirmação</h2>
                <div className="summary-box">
                  <p>
                    <strong>Repositório:</strong> {formData.owner}/
                    {formData.repo}
                  </p>
                  <p>
                    <strong>Painel de Projeto:</strong>{" "}
                    {formData.projectNumber
                      ? `Vincular ao Project existente #${formData.projectNumber}`
                      : formData.createProject
                        ? `Criar novo painel "${formData.projectTitle}"`
                        : "Nenhum projeto vinculado"}
                  </p>
                  <p>
                    <strong>Total de Milestones:</strong>{" "}
                    {formData.milestones.length}
                  </p>
                  <p>
                    <strong>Total de Labels:</strong> {formData.labels.length}
                  </p>
                  <p>
                    <strong>Total de Issues:</strong> {formData.issues.length}
                  </p>
                </div>

                <div className="checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      name="apply"
                      checked={formData.apply}
                      onChange={handleInputChange}
                    />{" "}
                    Aplicar no GitHub
                  </label>

                  <label
                    style={{
                      opacity: formData.projectNumber ? 0.5 : 1,
                      cursor: formData.projectNumber
                        ? "not-allowed"
                        : "pointer",
                    }}
                    title={
                      formData.projectNumber
                        ? "Desabilitado: você informou o número de um Project existente no Passo 1."
                        : ""
                    }
                  >
                    <input
                      type="checkbox"
                      name="createProject"
                      disabled={Boolean(formData.projectNumber)}
                      checked={
                        formData.projectNumber ? false : formData.createProject
                      }
                      onChange={handleInputChange}
                    />{" "}
                    Criar Painel de Projeto (Projects V2)
                  </label>
                </div>
              </div>
            )}

            {message && (
              <div
                className={`message ${message.includes("Erro") ? "error" : "success"}`}
              >
                {message}
              </div>
            )}

            {/* F1: detalhamento do que foi criado */}
            {result && (
              <div className="summary-box" style={{ marginTop: "12px" }}>
                <p>
                  <strong>Status:</strong>{" "}
                  {result.status === "partial" ? "Parcial" : "Concluído"}
                </p>
                <p>
                  <strong>Issues criadas:</strong>{" "}
                  {(result.issues_created || []).length}
                </p>
                {result.project_error && (
                  <p style={{ color: "#b00020" }}>
                    <strong>Painel de projeto:</strong> {result.project_error}
                  </p>
                )}
              </div>
            )}

            <div
              className="form-actions"
              style={{
                marginTop: "24px",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              {step > 1 && (
                <button
                  type="button"
                  onClick={prevStep}
                  className="btn-secondary"
                >
                  Voltar
                </button>
              )}
              {step === 1 && <div />}

              {step < 6 && (
                <button
                  type="button"
                  onClick={nextStep}
                  className="btn-primary"
                >
                  Próximo
                </button>
              )}
              {step === 6 && (
                <div style={{ textAlign: "right" }}>
                  <button
                    onClick={handleSubmit}
                    disabled={loading || !user?.has_pat}
                    className="btn-success"
                  >
                    {loading
                      ? "Processando... (pode levar alguns minutos)"
                      : "Finalizar e Enviar"}
                  </button>
                  {formData.apply && (
                    <div
                      style={{
                        color: "#666",
                        fontSize: "0.8rem",
                        marginTop: "6px",
                      }}
                    >
                      As issues são criadas uma a uma na API do GitHub; para
                      backlogs grandes isso leva alguns minutos.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProjectWizard;

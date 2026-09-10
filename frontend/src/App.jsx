import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [started, setStarted] = useState(false);
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [isTitleCustomized, setIsTitleCustomized] = useState(false);

  const [formData, setFormData] = useState({
    githubToken: "",
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

  // Atualiza o projectTitle dinamicamente conforme owner e repo mudam, a menos que o usuário tenha customizado
  useEffect(() => {
    if (!isTitleCustomized) {
      const owner = formData.owner.trim();
      const repo = formData.repo.trim();

      if (owner && repo) {
        setFormData((prev) => ({
          ...prev,
          projectTitle: `${owner}/${repo} - Roadmap`,
        }));
      } else if (owner || repo) {
        setFormData((prev) => ({
          ...prev,
          projectTitle: `${owner || repo} - Roadmap`,
        }));
      } else {
        setFormData((prev) => ({
          ...prev,
          projectTitle: "Roadmap",
        }));
      }
    }
  }, [formData.owner, formData.repo, isTitleCustomized]);

  // Busca o template único diretamente do backend ao montar o componente
  useEffect(() => {
    const loadTemplate = async () => {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/api/backlog-template",
        );
        if (!response.ok)
          throw new Error("Falha ao obter o template do backlog");

        const data = await response.json();
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
      }
    };

    loadTemplate();
  }, []);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;

    if (name === "projectTitle") {
      setIsTitleCustomized(true);
    }

    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
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

  // Submissão formatando para a API
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

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
      const response = await fetch("http://127.0.0.1:8000/api/build-roadmap", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "github-token": formData.githubToken,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Erro ao processar roadmap");
      }

      setMessage(
        `Sucesso! Roadmap aplicado com ${formData.issues.length} issues.`,
      );
    } catch (error) {
      setMessage(`Erro: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  if (!started) {
    return (
      <div className="welcome-screen">
        <div className="welcome-content">
          <img
            src="/roadmap.png"
            alt="Roadmap Builder Logo"
            className="welcome-logo"
          />
          <span className="welcome-tag">RoadMap Builder</span>
          <h1>Construa Roadmaps Inteligentes para o GitHub</h1>
          <p>
            Automatize a criação de marcos, etiquetas, cronogramas e painéis de
            projeto diretamente no seu repositório com uma experiência fluida,
            estruturada e integrada.
          </p>
          <button
            onClick={() => setStarted(true)}
            className="btn-welcome-start"
          >
            Começar a Construir ➔
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app-wrapper">
      <div className="form-container-wrapper">
        <button onClick={() => setStarted(false)} className="btn-top-welcome">
          ← Voltar a Página Apresentação
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
            {/* PASSO 1 */}
            {step === 1 && (
              <div className="step-panel">
                <h2>Configurações Iniciais</h2>
                <div className="form-group">
                  <label>Token do GitHub (Classic) *</label>
                  <input
                    type="password"
                    name="githubToken"
                    value={formData.githubToken}
                    onChange={handleInputChange}
                    placeholder="ghp_..."
                  />
                </div>
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
                        createProject: val ? false : prev.createProject,
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

                      {/* Seção de Labels */}
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

            {/* Mensagem de Feedback */}
            {message && (
              <div
                className={`message ${
                  message.includes("Erro") ? "error" : "success"
                }`}
              >
                {message}
              </div>
            )}

            {/* Ações */}
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
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="btn-success"
                >
                  {loading ? "Processando..." : "Finalizar e Enviar"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

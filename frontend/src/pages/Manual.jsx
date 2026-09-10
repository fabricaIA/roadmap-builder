import { Link } from "react-router-dom";

export default function Manual() {
  return (
    <div className="page manual">
      <h1>Manual de uso</h1>
      <p className="subtitle" style={{ color: "#666" }}>
        Como usar o RoadMap Builder para provisionar e acompanhar roadmaps no
        GitHub.
      </p>

      <h2>1. Entrar e configurar o token</h2>
      <ul>
        <li>
          O login é feito com sua conta do <strong>GitHub (OAuth)</strong> — só
          para identificar você.
        </li>
        <li>
          As operações no GitHub (criar milestones, labels, issues e painéis)
          usam um <strong>Personal Access Token (PAT)</strong> que você guarda
          em <Link to="/profile">Perfil</Link>. Ele é cifrado e nunca é exibido
          de volta.
        </li>
        <li>
          Escopos do PAT: <code>repo</code> sempre; <code>project</code> para
          criar/vincular painéis Projects V2 e ler o campo <em>Status</em> no
          Board; <code>read:org</code> para os dashboards por organização.
        </li>
        <li>
          Em Perfil você também define padrões (título do painel, data de
          início, nomes dos campos de data) e pode <strong>sincronizar</strong>{" "}
          suas organizações e papéis.
        </li>
      </ul>

      <h2>2. Projeto no app × Project do GitHub</h2>
      <p>
        No app, <strong>Projeto</strong> é um <em>roadmap registrado</em> = um
        repositório-alvo (<code>owner/repo</code>), que opcionalmente tem um
        painel Projects V2 vinculado. Não é o "Project" do GitHub em si.
      </p>
      <ul>
        <li>
          <strong>Novo projeto</strong> — o repositório ainda não tem o roadmap.
          O wizard cria milestones, labels e issues do template. A caixa "Criar
          Painel de Projeto" decide se também cria o board no GitHub.
        </li>
        <li>
          <strong>Importar existente</strong> — o repositório já tem o roadmap
          (feito pela CLI, por um colega ou num run anterior). Só registra no
          app para aparecer na lista e nos dashboards, sem recriar nada.
        </li>
      </ul>

      <h2>3. Wizard (Novo projeto)</h2>
      <ol>
        <li>
          <strong>Início</strong> — owner, repositório, título e data. Em "Fases
          a criar agora" você marca quais marcos provisionar neste momento; as
          demais ficam guardadas e podem ser aplicadas depois.
        </li>
        <li>
          <strong>Durações</strong> — tempo de cada marco (o cronograma das
          datas é calculado em sequência).
        </li>
        <li>
          <strong>Labels</strong> — etiquetas. Aparecem só as usadas pelas fases
          marcadas (+ as que você adicionar). O badge mostra em que fases cada
          uma é usada.
        </li>
        <li>
          <strong>Marcos</strong> — título e descrição de cada marco das fases
          marcadas.
        </li>
        <li>
          <strong>Issues</strong> — uma aba por fase. Cada issue tem título,
          descrição, etiquetas (chips), entregáveis e critérios de aceite.
        </li>
        <li>
          <strong>Revisão</strong> — confira o resumo. "Aplicar no GitHub"
          desmarcado = simulação (dry-run). Clique em "Finalizar e Enviar".
        </li>
      </ol>
      <p>
        A criação de issues é idempotente: reexecutar não duplica (as existentes
        são atualizadas). Só as fases marcadas são criadas agora; o config
        completo fica salvo no projeto para aplicar as demais depois.
      </p>

      <h2>4. Tela do projeto</h2>
      <ul>
        <li>
          <strong>Fases</strong> — estado de cada fase (
          <em>não criada / parcial / criada</em>). "Aplicar Fase" cria as issues
          daquela fase (e só as dela). Reaplicar uma fase completa: por padrão é
          no-op; marque "Alertar se a fase já foi criada" para receber um aviso.
          O histórico registra cada aplicação.
        </li>
        <li>
          <strong>Board</strong> (aba) — as issues daquele repositório em
          colunas (ver seção 6).
        </li>
      </ul>

      <h2>5. Organização, tenant e papéis</h2>
      <ul>
        <li>
          O <strong>tenant</strong> é a organização do GitHub. No login (ou
          sincronizando pelo Perfil) o app lê suas orgs e o papel:{" "}
          <code>admin</code> → <strong>coordenador</strong>, <code>member</code>{" "}
          → <strong>dev</strong>.
        </li>
        <li>
          Há também um <strong>tenant pessoal</strong> (sua conta), sempre no
          topo do seletor — consolida os projetos de repositórios pessoais, sem
          depender de uma organização. Você é coordenador do seu tenant pessoal.
        </li>
        <li>Escolha o tenant no seletor do cabeçalho.</li>
        <li>
          Um projeto pertence ao tenant <code>X</code> quando seu owner é{" "}
          <code>X</code> — assim o coordenador vê os projetos registrados por
          qualquer dev daquele tenant.
        </li>
      </ul>

      <h2>6. Dashboards e Board</h2>
      <ul>
        <li>
          <strong>Minhas issues</strong> — issues em que você é autor ou
          responsável, nos projetos do tenant.
        </li>
        <li>
          <strong>Issues da organização</strong> — todas as issues dos projetos
          do tenant. Coordenador vê também o recorte por desenvolvedor.
        </li>
        <li>
          <strong>Board</strong> — colunas com as issues que existem no GitHub.
          Agrupa por <strong>Status</strong> (o campo Status do Project V2,
          mesma representação do GitHub; sem Project vinculado, cai em
          aberta/fechada), Fase/Milestone, Responsável ou Aberta/Fechada.
          Filtros: repositório, milestone, responsável (assign to), label e
          estado. Cada card abre a issue no GitHub. Existe o Board do tenant
          (menu) e o Board de um projeto (aba "Board" na tela do projeto).
        </li>
        <li>
          <strong>Devs</strong> (coordenador) — matriz de progresso por
          desenvolvedor e por fase.
        </li>
        <li>
          Os dados vêm ao vivo do GitHub (cache de ~60s; botão "Atualizar" no
          Board). Repositórios sem acesso aparecem numa lista de avisos, sem
          quebrar a página.
        </li>
      </ul>

      <h2>7. Como testar a visão consolidada por organização</h2>
      <p>
        A visão consolidada é o <strong>Board do tenant</strong> +{" "}
        <strong>Issues da organização</strong>: agregam as issues de{" "}
        <em>todos</em> os projetos daquele tenant, registrados por qualquer
        usuário.
      </p>
      <p>
        <strong>
          Sem uma organização real (recomendado para demonstração):
        </strong>
      </p>
      <ol>
        <li>
          PAT no perfil com <code>repo</code> (e <code>project</code> se quiser
          o agrupamento por Status).
        </li>
        <li>
          Registre 2 ou mais projetos sob a sua conta (pela wizard ou
          "Importar"), aplicando ao menos a Fase M1 em cada.
        </li>
        <li>
          No seletor do cabeçalho, escolha o tenant <strong>(pessoal)</strong> →{" "}
          <strong>Board</strong> e <strong>Issues da organização</strong>{" "}
          consolidam os dois repositórios. Alterne o agrupamento e os filtros.
        </li>
      </ol>
      <p>
        <strong>
          Com uma organização do GitHub (teste completo, com papéis):
        </strong>
      </p>
      <ol>
        <li>
          Org com 2+ repositórios; PAT com <code>repo</code> +{" "}
          <code>project</code> + <code>read:org</code>.
        </li>
        <li>
          Faça login (a org aparece no seletor; se não, sincronize no Perfil).
          Owner da org → coordenador; member → dev.
        </li>
        <li>
          Crie 2 projetos pela wizard para repos da org, aplicando M1 em cada.
          Opcional: crie o Project V2 e defina o Status de algumas issues.
        </li>
        <li>
          Selecione a org → Board / Issues da organização consolidam os repos;
          "Devs" mostra a matriz por desenvolvedor.
        </li>
        <li>
          Papéis: uma segunda conta que é <code>member</code> (não owner) da org
          faz login → vê Board e Issues da org, mas "Devs" some do menu e
          retorna 403.
        </li>
      </ol>
      <p>
        Verificação rápida por API (com o cookie de sessão):{" "}
        <code>GET /api/orgs</code> (o 1º item é o tenant pessoal),{" "}
        <code>GET /api/dashboards/org-issues?org=&lt;login&gt;</code>,{" "}
        <code>GET /api/dashboards/devs?org=&lt;login&gt;</code> (200 para
        coordenador, 403 para member).
      </p>

      <h2>8. Linha de comando</h2>
      <p>
        O mesmo motor está em <code>scripts/roadmap_builder.py</code>. Ex.:{" "}
        <code>
          python scripts/roadmap_builder.py --owner ORG --repo REPO --apply
          --phase M1
        </code>
        . Veja o <code>README.md</code> para todas as opções.
      </p>
    </div>
  );
}

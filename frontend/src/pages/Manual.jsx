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
          criar/vincular painéis Projects V2; <code>read:org</code> para os
          dashboards por organização.
        </li>
        <li>
          Em Perfil você também define padrões (título do painel, data de
          início, nomes dos campos de data).
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
        são atualizadas).
      </p>

      <h2>4. Tela do projeto e aplicação por fase</h2>
      <ul>
        <li>
          A tela do projeto mostra contagens de issues e o estado de cada fase (
          <em>não criada / parcial / criada</em>).
        </li>
        <li>
          <strong>Aplicar Fase</strong> cria as issues daquela fase (e só as
          dela). Reaplicar uma fase completa: por padrão é no-op; marque
          "Alertar se a fase já foi criada" para receber um aviso em vez disso.
        </li>
        <li>O histórico registra cada aplicação de fase.</li>
      </ul>

      <h2>5. Organização e papéis</h2>
      <ul>
        <li>
          O <strong>tenant</strong> é a organização do GitHub. No login (ou
          sincronizando pelo Perfil) o app lê suas orgs e o papel:
          <code> admin</code> → <strong>coordenador</strong>,{" "}
          <code>member</code> → <strong>dev</strong>.
        </li>
        <li>Escolha a organização no seletor do cabeçalho.</li>
      </ul>

      <h2>6. Dashboards</h2>
      <ul>
        <li>
          <strong>Minhas issues</strong> — issues em que você é autor ou
          responsável, nos projetos de roadmap da organização.
        </li>
        <li>
          <strong>Issues da organização</strong> — todas as issues dos projetos
          da org. Coordenador vê também o recorte por desenvolvedor.
        </li>
        <li>
          <strong>Board</strong> — colunas com as issues que existem no GitHub
          (a visão de gestão de um board), agrupáveis por fase, estado ou
          responsável, com filtro por repositório/responsável. Cada card abre a
          issue no GitHub.
        </li>
        <li>
          <strong>Devs</strong> (coordenador) — matriz de progresso por
          desenvolvedor e por fase.
        </li>
        <li>
          Os números vêm ao vivo do GitHub (cache de ~60s). Repositórios sem
          acesso aparecem numa lista de avisos, sem quebrar a página.
        </li>
      </ul>

      <h2>7. Linha de comando</h2>
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

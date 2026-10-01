(() => {
  const CORES_CLASSES = [
    "#1f7a4d",
    "#66a96b",
    "#e8b849",
    "#d96b43",
    "#52796f",
    "#2f80b7",
    "#8b6bb8",
    "#ca6680",
    "#76a5af",
    "#a98467",
  ];

  const OPCOES_RESPONSIVAS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: "bottom" } },
  };

  function lerDadosJson(idElemento) {
    const elemento = document.getElementById(idElemento);

    return elemento ? JSON.parse(elemento.textContent) : [];
  }

  function traduzirNomeClasse(nome) {
    return nome.replace("Tomato___", "").replaceAll("_", " ");
  }

  function formatarData(dataIso) {
    return new Date(dataIso).toLocaleDateString("pt-BR");
  }

  function criarGraficoDistribuicao() {
    const distribuicao = lerDadosJson("dados-distribuicao");

    const tela = document.getElementById("graficoClasses");

    if (!tela || !distribuicao.length) return;

    new Chart(tela, {
      type: "doughnut",
      data: {
        labels: distribuicao.map((item) =>
          traduzirNomeClasse(item.classe_prevista),
        ),
        datasets: [
          {
            data: distribuicao.map((item) => item.total),
            backgroundColor: CORES_CLASSES,
          },
        ],
      },
      options: { plugins: { legend: { position: "bottom" } } },
    });
  }

  function criarGraficoAmbiental() {
    const leituras = lerDadosJson("dados-leituras");

    const tela = document.getElementById("graficoAmbiente");

    if (!tela || !leituras.length) return;

    new Chart(tela, {
      type: "line",
      data: {
        labels: leituras.map((item) => formatarData(item.medida_em)),
        datasets: [
          {
            label: "Temperatura °C",
            data: leituras.map((item) => item.temperatura),
            borderColor: "#d96b43",
            tension: 0.35,
          },
          {
            label: "Umidade %",
            data: leituras.map((item) => item.umidade),
            borderColor: "#2f80b7",
            tension: 0.35,
          },
        ],
      },
      options: { plugins: { legend: { position: "bottom" } } },
    });
  }

  function criarGraficoConfianca() {
    const estatisticas = lerDadosJson("dados-estatisticas-classes");

    const tela = document.getElementById("graficoConfianca");

    if (!tela || !estatisticas.length) return;

    new Chart(tela, {
      type: "bar",
      data: {
        labels: estatisticas.map((item) =>
          traduzirNomeClasse(item.classe_prevista),
        ),
        datasets: [
          {
            label: "Confiança média (%)",
            data: estatisticas.map((item) => item.confianca_media),
            backgroundColor: "#2d8056",
          },
        ],
      },
      options: {
        ...OPCOES_RESPONSIVAS,
        indexAxis: "y",
        scales: {
          x: {
            beginAtZero: true,
            max: 100,
            title: { display: true, text: "Confiança média (%)" },
          },
        },
      },
    });
  }

  function criarGraficoAlertas() {
    const alertas = lerDadosJson("dados-linha-tempo-alertas");

    const tela = document.getElementById("graficoLinhaTempoAlertas");

    if (!tela || !alertas.length) return;

    const severidades = [
      { rotulo: "Baixa", campo: "baixa", cor: "#708078" },
      { rotulo: "Média", campo: "media", cor: "#e0a72d" },
      { rotulo: "Alta", campo: "alta", cor: "#e17a36" },
      { rotulo: "Crítica", campo: "critica", cor: "#c83d3d" },
    ];

    new Chart(tela, {
      type: "line",
      data: {
        labels: alertas.map((item) => formatarData(`${item.data}T12:00:00`)),
        datasets: severidades.map((severidade) => ({
          label: severidade.rotulo,
          data: alertas.map((item) => item[severidade.campo]),
          borderColor: severidade.cor,
          backgroundColor: severidade.cor,
          tension: 0.3,
        })),
      },
      options: {
        ...OPCOES_RESPONSIVAS,
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });
  }

  // O Chart.js vem do CDN no template. Sem ele, a página continua utilizável.
  if (!window.Chart) return;

  criarGraficoDistribuicao();

  criarGraficoAmbiental();

  criarGraficoConfianca();

  criarGraficoAlertas();
})();

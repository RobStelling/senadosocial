var des = {};
des.clique = false;

function desenha(arquivo) {
  /*
   * Desenha o grafo expandido de despesas de senadores
   */
  // Grupos de nós do grafo para colorização: gastos e partidos
  var grupos = ["gasto", "MDB", "PSDB", "PT", "PP",
                "PODE", "PSD", "PSB", "DEM", "PR",
                "PDT", "PTB", "S/Partido", "PCdoB", "REDE",
                "PTC", "PROS", "PRB", "PPS",
                "PRTB", "PSC", "PV", "PPL"];

  // Objeto SVG onde será exibida a simulação
  var svg = d3.select("svg");

  // Cores para partidos: Category10 e Set3 do colorbrewer
  // Algumas cores são visualmente próximas mas a quantidade de
  // partidos não acomoda uma solução definitiva
  var color = d3.schemeCategory10.concat(d3.schemeSet3);

  /* Simulação do diagrama de força
   * Forças:
   * arestas:
   *   - entre senadores: comprimento proporcional ao peso
   *   - entre senador e gasto: inversamente proporcional ao log2 do gasto
   * carga: repulsão entre os nós
   * colisão: evitar sobreposição
   * centro: todos os nós convergem para o centro da imagem
   */
  const fatorPesoSenadorSimulacao = 4,
        fatorPesoGastosSimulacao = 25,
        caimentoVelocidadeSimulacao = 0.4,
        fatorColisao = 1.25,
        forcaAresta = 2.5,
        forcaCarga = -5;
  var simulacao = d3.forceSimulation()
      .velocityDecay(caimentoVelocidadeSimulacao)
      .force("arestas", d3.forceLink()
        .id(function(d) { return d.id; })
        .distance(function(d){
          if (d.target.tipo == d.source.tipo)
            return d.weight*fatorPesoSenadorSimulacao;
          return Math.log2(d.target.uso/d.weight)*fatorPesoGastosSimulacao;})
        .strength(forcaAresta))
      .force("carga", d3.forceManyBody().strength(forcaCarga))
      .force("colisao", d3.forceCollide(function(d){ return d.raio*fatorColisao; }).strength(1))
      .force("centro", d3.forceCenter(0, 0));

  // Lê arquivo JSON do grafo de dados do Senado e projeta
  // a simjulação do campo de força
  d3.json(arquivo, function(erro, grafoSenado) {
    if (erro)
      throw erro;

    var k, arestas, vertices;
    const fatorAjusteAresta = 1/100000,
          fatorAjusteRaioSenador = 1/150,
          fatorAjusteRaioGastos = 2,
          raioMinimo = 3,
        opacidadeAresta = 0.6,
        opacidadeVertice = 1,
        verticeAtenuado = 0.1;

    /*
     * Ajusta o tamanho dos círculos de acordo com o tipo:
     * senadores: Área proporcional à utilização de recursos
     * gastos: Área proporcional ao log2 dos gastos
     */
    for (k=0; k<grafoSenado.nodes.length; k++) {
      if (grafoSenado.nodes[k].tipo == "senador")
        proporcaoRaio = Math.sqrt(grafoSenado.nodes[k].uso/Math.PI)*fatorAjusteRaioSenador;
      else
        proporcaoRaio = Math.log2(Math.sqrt(grafoSenado.nodes[k].uso/Math.PI))*fatorAjusteRaioGastos;
      grafoSenado.nodes[k].raio = Math.max(raioMinimo, proporcaoRaio);
    }

    // Primeiro desenha as arestas, para que fiquem ao fundo
    // do objeto SVG
    arestas = svg.append("g")
          .attr("class", "arestas")
        .selectAll("line")
        .data(grafoSenado.links)
        .enter().append("line")
          .attr("class", function(d){return "S"+d.source+" "+"T"+d.target;})
          .attr("stroke-width", function(d){return Math.max(1, Math.log10(+d.weight*fatorAjusteAresta));});
    // Desenha os vértices, que são despesas e senadores
    vertices = svg.append("g")
          .attr("class", "vertices")
        .selectAll("circle")
        .data(grafoSenado.nodes)
        .enter().append("circle")
          .attr("r", function(d){return d.raio;})
          .attr("fill",
            function(d){return d.tipo == 'gasto' ? 'black' : color[grupos.findIndex(function(g){return d.tipo == 'senador' ? g == d.partido : g == d.tipo;})-1];})
          .attr("id", function(d){return "V"+d.id;})
          .attr("class", function(d){return d.tipo;});
          // Sem arrastar depois de terminada a simulação...
        // .call(d3.drag()
        //    .on("start", comecaArrastar)
        //    .on("drag", arrastando)
        //    .on("end", terminaArrastared));
    // Acrescenta os dados de senadores e despesas para mouseover (efetuado pelo navegador)
    vertices
      .append("title")
        .text(function(d){
          exercicio = {"ForaExercicio": "Fora de exercício", "Exercicio": "Em exercício"};
          return d.nome+(d.tipo == 'senador' ? ('\nExcentricidade: '+d.excentricidade+'\n'+d.partido+ ' - '+d.estado+'\n'+exercicio[d.status]) : "")
                       +"\nTotal: R$ "+d.uso.toLocaleString()});

    simulacao
      .nodes(grafoSenado.nodes)
      .on("tick", ticked);

    simulacao
      .force("arestas")
      .links(grafoSenado.links);
    // Associa os hoods de mouseover/mousemove/mouseout/clique nos vértices
    d3.selectAll('circle')
      .on("mouseover", mouseover)
      .on("mousemove", mousemove)
      .on("mouseout", mouseout)
      .on("click", clique);

    // Tick da simulação
    function ticked() {
      arestas
        .attr("x1", function(d){return d.source.x;})
        .attr("y1", function(d){return d.source.y;})
        .attr("x2", function(d){return d.target.x;})
        .attr("y2", function(d){return d.target.y;});
      vertices
        .attr("cx", function(d){return d.x = d.x > 490 ? 490 : d.x < -490 ? -490 : d.x;})
        .attr("cy", function(d){return d.y = d.y > 490 ? 490 : d.y < -490 ? -490 : d.y;});
    }

   /*
    * Destaca o vértice atual e suas conexões
    */
    function mouseover(d) {
      if (!des.clique) {
      // Marca todas os vértices, excetuando o atual
        d3.selectAll("circle")
          .filter(function(c){return c.id != d.id;})
          .classed("atenua", true);
        d3.select("#V"+d.id)
          .classed("normal", true);

        // Percorre todas as arestas.
        // Apaga a marcação de atenuar dos vertices que tem origem
        // ou destino no vértice atual.
        // Atenua as arestas que não estão conectadas ao vértice atual.
        d3.selectAll("line")
          .filter(function(l){
            // Se o atual é a origem
            if (d.id == l.source.id)
              // não atenua o destino
              d3.select("#V"+l.target.id)
                .classed('atenua', false)
                .classed("normal", true)
            // Se o atual é o destino
            else if (d.id == l.target.id)
              // Não apaga a origem
              d3.select("#V"+l.source.id)
                .classed("atenua", false)
                .classed("normal", true)
            // Se não é origem nem destino, suprime a aresta
            return d.id != l.source.id && d.id != l.target.id;
          })
          .style("opacity", 0);
        // Atenua todos os vértices que não estão conectados
        // ao vértice atual.
        d3.selectAll(".atenua")
          .style("opacity", verticeAtenuado);
        return;
      }
    }

    /*
     * Sem ações quando o mouse mover sobre uma aresta
     */
    function mousemove(d) {
      return;
    }

    /*
     * Restaura as arestas e linhas para o estado original
     */
    function mouseout(d) {
      if (!des.clique) {
        d3.selectAll("line")
          .style("opacity", opacidadeAresta);
        d3.selectAll("circle")
          .classed("atenua", false)
          .classed("normal", false)
          .style("opacity", opacidadeVertice);
        return;
      }
    }


    /*
     * Expande o componente conectado do vértice atual após um
     * clique. Vértices e arestas são exibidos
     */
    function clique(d) {
      if (des.clique) {
        limpa();
        des.clique = false;
      } else {
        des.clique = true;
        if (d.tipo == "senador") {
          var conectados = new Set([]);
          d3.selectAll(".normal")
            .filter(function(a){
              if (a.tipo == "senador") {
                conectados.add(a.id);
                return false;
              }
              return true;
            })
            .classed("atenua", true)
            .classed("normal", false)
            .style("opacity", verticeAtenuado);
          d3.selectAll("line")
            .filter(function(l){return l.source.tipo == "gasto" || l.target.tipo == "gasto";})
            .style("opacity", 0);
          marcar = percorre(conectados, new Set([d.id]));
          for (vertice of marcar.entries())
            d3.select("#V"+vertice[0])
              .classed("normal", true)
              .classed("atenua", false)
              .style("opacity", opacidadeVertice);
        }
      }
    }

    function limpa() {
      d3.selectAll("circle")
        .classed("normal", true)
        .classed("atenua", false)
        .style("opacity", opacidadeVertice);
      d3.selectAll("line")
        .style("opacity", opacidadeAresta);
    }

    /*
     * Percorre o componente conectado e "acende" as arestas
     * do componente conectado. Retorna o conjunto de vértices
     * do componente conectado.
     * recebe uma lista de vértices conectados e outra de
     * já visitados. Termina a execução quando os dois conjuntos
     * forem idênticos
     */
    function percorre(conectados, visitados) {
      var vertice;

      while (conectados.size != visitados.size ) {
        for (vertice of conectados.entries()) {
          if (!visitados.has(vertice[0])) {
            visitados.add(vertice[0])
            d3.selectAll("line")
              .filter(function(l){
                if (l.source.id == vertice[0] && senador(l.target.id)) {
                  conectados.add(l.target.id);
                  return true;
                }
                if (l.target.id == vertice[0] && senador(l.source.id)) {
                  conectados.add(l.source.id);
                  return true;
                }
                return false;
              })
              .style("opacity", opacidadeAresta);
          }
        }
      }
      return conectados;
    }
  });

  // Retorna true se o id corresponde a um senador
  function senador(id) {
    return d3.select("#V"+id).classed("senador");
  }

  // Funções de drag, não usadas
  function comecaArrastar(d) {
    const alfaRetomada = 0.3;
    if (!d3.event.active) simulacao.alphaTarget(alfaRetomada).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  function arrastando(d) {
    d.fx = d3.event.x;
    d.fy = d3.event.y;
  }

  function terminaArrastared(d) {
    const alfaFinal = 0;
    if (!d3.event.active) simulacao.alphaTarget(alfaFinal);
    d.fx = null;
    d.fy = null;
  }
}
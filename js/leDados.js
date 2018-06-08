// Função de callback da seleção de arquivo
function leArquivoDados(event) {
  var file = event.target.files[0];

  if (!file)
    return;

  var reader = new FileReader();
  // desenha é chamada após a leitura do arquivo
  reader.onload = function(event) {
    desenha(event.target.result);
  };
  // Altera o texto do botão de seleção
  // para o nome do arquivo selecionado
  d3.select(".leArquivo")
    .text(file.name);

  reader.readAsDataURL(file);
}
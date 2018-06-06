function leArquivoDados(event) {
  var file = event.target.files[0];

  if (!file)
    return;

  var reader = new FileReader();

  reader.onload = function(event) {
    desenha(event.target.result);
  };

  d3.select(".leArquivo")
    .text(file.name);

  reader.readAsDataURL(file);
}
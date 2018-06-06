# coding='utf-8'
# Imports
from bs4 import BeautifulSoup
from datetime import datetime
from math import log
from matplotlib.ticker import FuncFormatter
from scipy import spatial
from scipy.interpolate import interp1d
import argparse
import csv
import errno
import json
import locale
import matplotlib.pyplot as plt
import numpy as np
import operator
import os
import pandas as pd
import re

import rotinas as rtn

"""Lê dados de parlamentares de arquivos CSV e
gera gráficos, texto e páginas com o conteúdo
"""

locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

parser = argparse.ArgumentParser(
    description='Gera grafo de gastos de Senadores brasileiros.', add_help=False, usage='uso')

parser._optionals.title = "argumentos opcionais"

parser.add_argument('-h', '--help', default='argparse.SUPPRESS', action='help',
                    help='Mostra esta mensagem e sai')

parser.add_argument('-G', '--geraGraficos', dest='graficos', action='store_true',
                    help='Gera gráficos')

parser.add_argument('-J', '--semJSON', dest='semJSON', action='store_true',
                    help='Não gera arquivo JSON do grafo')

parser.add_argument('-a', '--ajusteGabinete', dest='ajusteGabinete', action='store',
                    type=float, default=1.0,
                    help='Coeficiente de ajuste para despesas de gabinete')
# Custo médio estimado de um funcionário de gabinete
parser.add_argument('-c', '--custoGabinete', dest='custoGabinete', action='store',
                    type=int, default=10000,
                    help='Estimativa de custo médio de um acessor de gabinete ou escritório de apoio')

parser.add_argument('-d', '--direcionado', dest='direcionado', action='store_true',
                    help='Grafo GML direcionado')

parser.add_argument('-g', '--nomeArquivoGML', dest='arquivoGML', action='store',
                    type=argparse.FileType('w'), default='gml/senado.gml',
                    help='Path do arquivo GLM do grafo')

# Custo médio estimado de um funcionário de gabinete
parser.add_argument('-m', '--custoAuxilioMoradia', dest='custoMoradia', action='store',
                    type=int, default=5500,
                    help='Estimativa de custo médio de auxílio moradia e imóvel funcional')

parser.add_argument('-n', '--nomeArquivoGrafo', dest='arquivoGrafo', action='store',
                    type=argparse.FileType('w'), default='json/grafoSenado.json',
                    help='Path do arquivo JSON do grafo')

parser.add_argument('-s', '--similaridade', dest='similaridade', action='store',
                    type=float, default=0.95,
                    help='Valor de corte da similaridade entre nós')


parser.add_argument('-v', '--valorDeCorte', dest='valorCorte', action='store',
                    type=int, default=1000,
                    help='Valor de corte para despesas de senador')

args = parser.parse_args()

# Lê legislatura e Lista de anos de mandato para contabilização
with open('csv/anos.csv', newline='') as arquivoAnos:
    anosReader = csv.reader(arquivoAnos)
    for row in anosReader:
        # Ignora o header (se houver)
        if rtn.maiorQue(row[0]) and rtn.maiorQue(row[1]) and rtn.maiorQue(row[2]):
            legislaturaAtual = int(row[0])
            anos = list(range(int(row[1]), int(row[2]) + 1))
            # Quarto campo está no formato aaaa-mm-dd hh:mm:ss.dcmm
            # Primeiro separa data de hora
            dataColeta, horaColeta = row[3].split(' ')
            # Muda data coleta de aaaa-mm-dd para dd/mm/aaaa
            dataColeta = dataColeta.split('-')
            dataColeta = dataColeta[2] + '/' + \
                dataColeta[1] + '/' + dataColeta[0]
            # Descarta os décimos de segundo
            horaColeta = horaColeta.split('.')[0]
            break

# Lê créditos das fotos
# Ao fim, listaCredito[codigo] = credito para senador[codigo]
with open('csv/creditos.csv', newline='') as creditos:
    creditosReader = csv.reader(creditos)
    header = next(creditosReader)
    listaCredito = {}
    for row in creditosReader:
        listaCredito[int(row[0].split('.')[0].replace('senador', ''))] = row[1]

# Lê DataFrames
dadosSenado = pd.read_csv('csv/senado.csv', encoding='utf-8', index_col=0)
top = pd.read_csv('csv/top.csv', encoding='utf-8')
gastoPartidos = pd.read_csv('csv/gastoPartidos.csv',
                            encoding='utf-8', index_col=0)
gastoEstados = pd.read_csv('csv/gastoEstados.csv',
                           encoding='utf-8', index_col=0)
#sexo = pd.read_csv('csv/sexo.csv', encoding='utf-8')
sexo = dadosSenado.rename(columns={'Participacao': '(Sexo, Situação)'}).groupby(
    ['sexo', 'status'])['(Sexo, Situação)'].count()
sexoT = pd.read_csv('csv/sexoT.csv', encoding='utf-8', index_col=0)

# Lê arquivo json de gastos de senadores
with open('json/gastosSenadores.json', 'r', encoding='utf-8') as entrada:
    gastosSenadores = json.load(entrada)
entrada.close()

# Lê arquivo json de gastos do senado
with open('json/gastosSenado.json', 'r', encoding='utf-8') as entrada:
    gastosSenado = json.load(entrada)
entrada.close()

# Calcula dados importantes
totalSenadores = len(dadosSenado)
totalHomens = len(dadosSenado[dadosSenado.sexo == 'Masculino'])
totalMulheres = len(dadosSenado[dadosSenado.sexo == 'Feminino'])
totalExercicio = len(dadosSenado[dadosSenado.status == 'Exercicio'])
totalMulheresExercicio = dadosSenado.query(
    'sexo == "Feminino" and status == "Exercicio"').count()[0]
totalForaExercicio = len(dadosSenado[dadosSenado.status == 'ForaExercicio'])
totalGasto = dadosSenado['gastos'].sum()

# Não contabiliza parlamentares que ainda não efetuaram gastos no cálculo de médias
gastoMedioSenadores = dadosSenado.query('gastos != 0')['gastos'].mean()
mediaGastosHomensExercicio = dadosSenado.query(
    'gastos != 0 and sexo == "Masculino" and status == "Exercicio"')['gastos'].mean()
mediaGastosMulheresExercicio = dadosSenado.query(
    'gastos !=0 and sexo == "Feminino" and status == "Exercicio"')['gastos'].mean()


# Imprime algumas informações do senado, pelos dados coletados
print('Há no senado {:d} senadores, distribuidos entre {:d} homens e {:d} mulheres'.format(
    totalSenadores, totalHomens, totalMulheres))
print('As mulheres representam ' + locale.format('%.2f',
                                                 totalMulheres / totalSenadores * 100) + '% do total')
print('Há {:d} senadores em exercício, destes {:d} são mulheres'.format(
    totalExercicio, totalMulheresExercicio))
print('As mulheres representam ' + locale.format('%.2f',
                                                 totalMulheresExercicio / totalExercicio * 100) + '% deste total')
print('O gasto médio de senadores homens em exercício foi de ' +
      rtn.reais(mediaGastosHomensExercicio))
print('O gasto médio de senadores mulheres em exercício foi de ' +
      rtn.reais(mediaGastosMulheresExercicio))
print('O gasto médio dos senadores, em exercício e fora de exercício, foi de ' +
      rtn.reais(gastoMedioSenadores))
print('O montante de despesas parlamentares em {:d} anos foi de {}, com media anual de {}\n'.format(
    len(anos), rtn.reais(totalGasto), rtn.reais(totalGasto / len(anos))))

print('Gastos do senado por tema:')
totalizacaoGastosSenado = 0.0
for caput in gastosSenado:
    totalizacaoGastosSenado += gastosSenado[caput]
    print('{}: {}'.format(caput, rtn.reais(round(gastosSenado[caput], 2))))

print('Total de gastos: {}'.format(rtn.reais(round(totalizacaoGastosSenado, 2))))

def meses(anos):
    """Retorna o total de meses desde o início da legislatura até a data da coleta
    """
    #hoje = datetime.today()
    mesColeta = int(dataColeta.split('/')[1])
    #diaAtual = hoje.day                # 1 <= day <= número de dias do mês
    pesos = np.full(len(anos), 12, dtype=int)
    pesos[0] = 11                       # Desconta 1 do primeiro ano, porque a legislatura começa em fevereiro
    pesos[len(anos)-1] = mesColeta      # Contabiliza o último ano pelo mês atual
    return np.sum(pesos), pesos         # retorna o total de meses e os meses em cada ano


numMeses, pesosMeses = meses(anos)      # Usado para ponderar os gastos totais e gastos com gabinete

# Cria grafo de senadores
grafo = {'nodes': [], 'links': []}

links = 0
reverso = {}
gabinete = 'Uso de Gabinete'
moradia = 'Uso de benefícios de moradia'

# Cria os nós dos gastos
for gasto in gastosSenado:
    grafo['nodes'].append({
        'id': links,
        'tipo': 'gasto',
        'nome': gasto,
        'uso': round(gastosSenado[gasto], 2)
        })
    reverso[gasto] = links
    links += 1

# Cria os nós de uso de Gabinete e Moradia
grafo['nodes'].append({
    'id': links,
    'tipo': 'gasto',
    'nome': gabinete,
    'uso': 0.0
    })
reverso[gabinete] = links
links += 1
grafo['nodes'].append({
    'id': links,
    'tipo': 'gasto',
    'nome': moradia,
    'uso': 0.0
    })
reverso[moradia] = links
links += 1

vetores = []

totalMoradia = 0.0
totalGabinete = 0.0

# Custos de utilização de gabinete serão convertidos para
# a escala de custos da categoria Correios, isto evita que
# esta dimensão domine a direção dos vetores no espaço vetorial
# dos gastos do senado

maxCorreios = 0.0
maxGabinete = 0.0
correios = 'Correios'

for i in range(len(gastosSenadores)):
    # senador -> índice para o senador no df dadosSenado
    # infoSenador -> dados do senador no df dadosSenado
    senador = gastosSenadores[i]['senador']
    infoSenador = dadosSenado.loc[senador]
    gastos = 0.0
    tipoGastos = {}

    # Computa o total de gastos (gastos) e o parcial em cada etiqueta (tipoGastos)
    # de um senador
    for g in range(len(gastosSenadores[i]['gastos'])):
        gastos += gastosSenadores[i]['gastos'][g]['total']
        for tipo in gastosSenadores[i]['gastos'][g]['lista']:
            if tipo in tipoGastos:
                tipoGastos[tipo] += round(gastosSenadores[i]['gastos'][g]['lista'][tipo], 2)
            else:
                tipoGastos[tipo] = round(gastosSenadores[i]['gastos'][g]['lista'][tipo], 2)

    if correios in tipoGastos:
        maxCorreios = max(maxCorreios, tipoGastos[correios])

    senadorGabinete = 0.0
    senadorMoradia = 0.0

    for ano in anos:
        senadorGabinete += infoSenador[f'TotalGabinete-{ano}'] * pesosMeses[ano-anos[0]]
        senadorMoradia += (infoSenador[f'Imóvel Funcional-{ano}'] + infoSenador[f'Auxílio-Moradia-{ano}']) # * pesosMeses[ano-anos[0]]

    # Converte utilização de gabinete e moradia para uma estimativa de custo
    senadorGabinete *= args.custoGabinete
    senadorMoradia *= args.custoMoradia

    if (senadorGabinete > 0.0):
        tipoGastos[gabinete] = senadorGabinete
    if (senadorMoradia > 0.0):
        tipoGastos[moradia] = senadorMoradia
    # Acumula os totais de gabinete e moradia
    totalGabinete += senadorGabinete
    totalMoradia += senadorMoradia
    # Soma gastos, gabinete e moradia e
    # pondera pelo número de meses da legislatura
    recursos = round(gastos + senadorGabinete + senadorMoradia, 2)

    if (recursos > args.valorCorte):
        # Cria vetor de utilização de recursos
        vetor = []
        for gastos in gastosSenado:
            if gastos in tipoGastos:
                vetor.append(round(tipoGastos[gastos],2))
            else:
                vetor.append(0.0)
        maxGabinete = max(maxGabinete, senadorGabinete)
        vetor.append(senadorGabinete)
        vetor.append(senadorMoradia)

        vetores.append({'id': i + links, 'vetor': list(vetor)})
        reverso[i + links] = len(grafo['nodes'])

        # Cria o nó do senador
        grafo['nodes'].append({
            'id': i + links,
            'tipo': 'senador',
            'uso': recursos,
            'nome': infoSenador.nome,
            'partido': infoSenador.partido,
            'estado': infoSenador.UF,
            'sexo': infoSenador.sexo,
            'status': infoSenador.status,
            'participacao': infoSenador.Participacao
            # 'vetor': vetor
            })

        # Cria os links do senador para o nós dos gastos
        for tipo in tipoGastos:
            grafo['links'].append({
                'source': i + links,
                'target': reverso[tipo],
                'weight': round(tipoGastos[tipo], 2)
                })

# Preenche o gasto estimado de auxílio moradia e gabinete
grafo['nodes'][reverso[gabinete]]['uso'] = totalGabinete
grafo['nodes'][reverso[moradia]]['uso'] = totalMoradia


# Muda a escala dos gastos com gabinete para a mesma escala dos gastos com
# correios, que é aproximadamente similar à média dos gastos.
conversao = interp1d([0, maxGabinete], [0, maxCorreios*args.ajusteGabinete])
for i in vetores:
    i['vetor'][-2] = float(conversao(i['vetor'][-2]))

# Cria links entre os senadores que possuem similaridades de utilização
# de recursos (similaridade de cosseno > args.similaridade [defaul > 0.95])
interpolacao = interp1d([1, args.similaridade], [10, 5])

for i in vetores:
    excentricidade = []
    for j in vetores:
        dist = 1 - spatial.distance.cosine(i['vetor'], j['vetor'])
        if i != j:
            excentricidade.append(dist);
        if (j['id'] > i['id']):
            # dist = 1 - spatial.distance.cosine(i['vetor'], j['vetor'])
            if dist > args.similaridade:
                grafo['links'].append({
                    'source': i['id'],
                    'target': j['id'],
                    'weight': round(float(interpolacao(dist)), 2)
                    })
    grafo['nodes'][reverso[i['id']]]['excentricidade'] = round(1 - np.mean(excentricidade), 5)

# Salva grafo em formato JSON
json.dump(grafo, args.arquivoGrafo, ensure_ascii=False,
              indent=2, separators=(',', ':'))
args.arquivoGrafo.close()

def json2gml(dados, gml, directed=0, id='id', label='label', numero=[], exclui=[]):
    """Gera arquivo em formato GML, como no exemplo abaixo:
    graph [
        directed 1
        node [
            id 0
            label "Bleak House"
        ]
        node [
            id 1
            label "Oliver Twist"
        ]
        edge [
            source 0
            target 1
            weight 2
        ]
    ]
    """
    # Starts with GDF header
    gml.write(f'graph [\n    directed {directed}\n')
    # Loops through nodes
    for no in dados['nodes']:
        gml.write('    node [\n')
        for campo in no:
            if campo == id:
                gml.write(f'        id {no["id"]}\n')
            elif campo in numero:
                gml.write(f'        {campo} {no[campo]}\n')
            elif campo == label:
                gml.write(f'        label "{no[campo]}"\n')
            elif not campo in exclui:
                gml.write(f'        {campo} "{no[campo]}"\n')
        gml.write(f'        graphics [\n')
        if no['tipo'] == 'gasto':
            gml.write(f'            type "rectangle"\n')
            gml.write(f'            fill #FF0000\n')
        else:
            gml.write(f'            type "circle"\n')
            gml.write(f'            fill #0000FF\n')
        gml.write(f'        ]\n')
        gml.write('    ]\n')
    for vertice in dados['links']:
        gml.write('    edge [\n')
        for campo in vertice:
            gml.write(f'        {campo} {vertice[campo]}\n')
        gml.write('    ]\n')
    gml.write(']\n')
    gml.close()

# Salva grafo em formato GML
json2gml(grafo, args.arquivoGML, directed=(1 if args.direcionado else 0), label='nome', numero=['uso', 'excentricidade'], exclui=['vetor'])

def tickReais(x, pos=None):
    """Retorna uma string no formato <numero>M para ser usada
    em gráficos
    """
    if x == int(x):
        formato = '%d'
    else:
        formato = '%.1f'
    return locale.format(formato, x, grouping=True) + 'M'


if args.graficos:
    # Gera gráficos
    imagens = 'imagens'
    if not os.path.exists(imagens):
        os.makedirs(imagens)

    # Ordena os tipos de gasto pelo montante e cria os vetores
    # de título (caput), dados
    gS = sorted(gastosSenado.items(), key=operator.itemgetter(1))
    caput = []
    y = []
    x = []
    i = 0
    for item in gS:
        caput.append(item[0])
        x.append(item[1] / 1000000)
        y.append(i)
        i += 1

    plt.style.use('seaborn-whitegrid')

    fig, ax = plt.subplots()
    ax.barh(y, x, tick_label=caput)
    ax.set(xlabel='Valores em milhões de reais',
           title='Gastos de Senadores por tipo de despesa')
    ax.xaxis.set_major_formatter(FuncFormatter(tickReais))
    fig.savefig(f'{imagens}/gastosSenado.png',
                transparent=False, bbox_inches='tight')
    plt.close()
    gSexo = sexo.plot(kind='pie', figsize=(13, 13), fontsize=12,
                      subplots=True, legend=False, colormap='Paired')
    gSexo[0].get_figure().savefig(f'{imagens}/distSexo.png')
    plt.close()
    gSexoT = sexoT[['Participacao']].plot(kind='pie', figsize=(
        5, 5), subplots=True, legend=False, fontsize=12, colormap='Paired')
    gSexoT[0].get_figure().savefig(f'{imagens}/distSexoT.png')
    plt.close()

    listaGastos = [
        x for x in gastoEstados.columns if re.match(r'gastos[0-9]*$', x)]

    gEstados = gastoEstados[listaGastos].plot(
        kind='bar', rot=0, title='Gastos por unidade da federação', figsize=(15, 5), legend=True, fontsize=12, colormap='Paired')
    gEstados.yaxis.set_major_formatter(FuncFormatter(rtn.reais))
    gEstados.get_figure().savefig(f'{imagens}/gastoEstados.png')
    plt.close()
    gabineteEstados = gastoEstados.sort_values(by=[f'TotalGabinete-{anos[-1]}'], ascending=False)[['TotalGabinete-{}'.format(anos[-1])]].plot(
        kind='bar', title=f'Tamanho do gabinete em {anos[-1]} por unidade da federação', figsize=(10, 10), fontsize=12, legend=False)
    gabineteEstados.get_figure().savefig(
        f'{imagens}/gastoGabineteEstados{anos[-1]}.png')
    plt.close()
    gPartidos = gastoPartidos[listaGastos].plot(
        kind='bar', rot=0, title='Gastos por Partido', figsize=(15, 5), legend=True, fontsize=10, colormap='Paired')
    gPartidos.yaxis.set_major_formatter(FuncFormatter(rtn.reais))
    gPartidos.get_figure().savefig(f'{imagens}/gastoPartidos.png')
    plt.close()
    gabinetePartidos = gastoPartidos.sort_values(by=[f'TotalGabinete-{anos[-1]}'], ascending=False)[[f'TotalGabinete-{anos[-1]}']].plot(
        kind='bar', title=f'Tamanho do gabinete em {anos[-1]} por partido', figsize=(10, 10), fontsize=12, legend=False)
    gabinetePartidos.get_figure().savefig(
        f'{imagens}/gastoGabinetePartidos{anos[-1]}.png')
    plt.close()
    gTop = top[listaGastos].plot(
        kind='bar', rot=20, title='Senadores com maiores gastos na legislatura atual', x=top['nome'], figsize=(18, 8), legend=True, fontsize=12, colormap='Paired')
    gTop.yaxis.set_major_formatter(FuncFormatter(rtn.reais))
    gTop.get_figure().savefig(f'{imagens}/maiores.png')
    plt.close()

    listaBeneficioMoradia = [x for x in gastoEstados.columns if re.match(
        r'(Auxílio-Moradia|Imóvel Funcional)-[0-9]+$', x)]
    beneficioMoradia = 0
    for beneficio in listaBeneficioMoradia:
        beneficioMoradia += gastoEstados[beneficio]
    beneficioMoradia /= len(anos)

    gBeneficio = beneficioMoradia.sort_values(ascending=False).plot(
        kind='bar', title='Média de meses anuais de uso de benefícios de moradia por unidade da federação', figsize=(10, 10), fontsize=(12), legend=False)
    gBeneficio.get_figure().savefig(f'{imagens}/moradiaEstado.png')
    plt.close()

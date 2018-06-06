import locale

"""Rotinas de uso comum entre os módulos da aplicação
"""


def reais(x, pos=None):
    """Retorna o valor formatado em reais, o parâmetro pos é necessário
    apenas quando a função é chamada pelo FuncFormatter do matplotlib.ticker
    """
    return 'R$ ' + locale.format('%.2f', x, grouping=True)


def maiorQue(numero, menor=0):
    """Retorna True se numero é um inteiro maior que 0
    False caso contrário. O valor mínimo de referência 
    pode ser alterado passando menor=<novoValor>
    numero pode ser string ou qualquer outro tipo aceito
    por int() 
    """
    try:
        valor = int(str(numero))
        return valor > menor
    except ValueError:
        return False


def s2float(dado):
    """ Converte uma string numérica no formato brasileiro para float """
    # Retira '.' e substitui ',' por '.' e converte para float
    try:
        valor = float(dado.replace('.', '').replace(',', '.'))
        return valor
    except ValueError:
        return float('nan')

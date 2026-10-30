"""Seletores do portal Infox (Oracle APEX, aplicação 380).

Os marcados com MAPEAR são XPaths absolutos herdados da versão Selenium:
funcionam, mas quebram com qualquer mudança de layout. Troque-os por IDs ou
textos estáveis usando o Playwright Inspector (coloque page.pause() no fluxo).

Seletores das telas ainda não migradas estão listados em MIGRACAO_PLAYWRIGHT.md.
"""

# Login (página 100)
LOGIN_USUARIO = "#P100_USERNAME"
LOGIN_SENHA = "#P100_PASSWORD"
LOGIN_BOTAO = "#LOGIN"
LOGIN_CAPTCHA = 'xpath=//*[@id="uLogin"]/div[5]/div/div/div[1]'  # MAPEAR
# Mensagens de erro padrão do APEX (ex.: credenciais inválidas). Confirmar qual o portal usa.
MENSAGEM_ERRO = (
    "#t_Alert_Notification:visible, "
    "#APEX_ERROR_MESSAGE .a-Notification-item:visible, "
    ".t-Alert--danger:visible"
)
LOGIN_ERRO = MENSAGEM_ERRO

# Menu lateral
MENU_RAIZ = "#t_MenuNav_11i"  # visível = login concluído
MENU_PESQUISA_CREDENCIADO = (
    "#t_MenuNav_11i",
    "#t_MenuNav_11_1i",
    "#t_MenuNav_11_1_2i",
    "#t_MenuNav_11_1_2_1i",
)

# Pesquisa de credenciado (página 2100)
PESQ_CODIGO = "#P2100_ID_CREDENCIADO"
PESQ_CNPJ = "#P2100_CNPJ"
PESQ_BOTAO = "#PESQUISAR"
PESQ_LINKS_RESULTADO = 'xpath=//*[@id="LISTA"]//tr[td//a]//td[1]//a'  # quando a pesquisa devolve uma lista
PESQ_SEM_DADOS = "#LISTA .a-IRR-noDataMsg-text"

# Detalhe do credenciado (página 2101)
DET_CODIGO = "#P2101_CODIGO"
DET_CNPJ = "#P2101_CNPJ"
DETALHE_CREDENCIADO = f"{DET_CODIGO}, {DET_CNPJ}"  # presente = a tela do credenciado abriu
DET_BTN_CONTRATOS = "#VISUALIZAR_CONTRATOS"
DET_FANTASIA = "#P2101_FANTASIA"
DET_RAZAO = "#P2101_RAZAO"
DET_EMAIL = "#P2101_EMAIL"
DET_CONCILIACAO = "#P2101_EDIFNC_CONC_VENDA"
DET_CELULAR = "#P2101_CELULAR"
DET_TELEFONE = "#P2101_TELEFONE"
DET_DATA_CADASTRO = "#P2101_DATA_CADASTRO"
DET_CPF_PROPRIETARIO = "#P2101_CPF_PROPRIETARIO"
# Tabela "Endereços": cada célula aponta para o id da coluna no atributo `headers`. Assim lê a
# automação de criação de acesso, que já roda no portal real. Com mais de um endereço, use .first.
DET_END_LOGRADOURO = '[headers="ENDERECO"]'      # "RUA X, 123": logradouro e número separados pela 1ª vírgula
DET_END_BAIRRO = '[headers="BAIRRO"]'
DET_END_CEP = '[headers="CEP_FORMATADO"]'
DET_END_CIDADE = '[headers="CIDADE_ESTADO"]'     # "CIDADE/UF"
# Menu "Opções" do credenciado: Opções > Cadastro > Código Estabelecimento (este último achado pelo texto)
DET_MENU_OPCOES = "#CREDENCIADO"
DET_MENU_LISTA = "#CREDENCIADO_MENU"
DET_MENU_CADASTRO = "#CREDENCIADO_MENU_menu_1i"

# Código estabelecimento (página 2118): uma linha por origem de transação
CODEST_TABELA = "#report_CODIGO_ESTABELECIMENTO"
CODEST_VOLTAR = "#P2118_VOLTAR"

# Configuração EDI (página 2310), aberta pelo botão "Alterar configuração EDI" do credenciado
DET_BTN_ALTERAR_EDI = "#ALTERAR_CFG_EDI"
EDI_CONCILIACAO = "#P2310_ID_EDIFNC_CONC_VENDA"
EDI_SAIR_SEM_SALVAR = "#CANCELAR, #VOLTAR, #CANCEL"  # nomes comuns no APEX; o Selenium nunca saía sem salvar

# Menu "Produção > Consulta > Transação". Para cada nível, o rótulo (id com "i" no fim, como no
# caminho da pesquisa de credenciado) e, se ele não existir, o próprio item, que a versão Selenium clicava.
MENU_CONSULTA_TRANSACOES = (
    ("#t_MenuNav_11i",),
    ("#t_MenuNav_11_2i", "#t_MenuNav_11_2"),
    ("#t_MenuNav_11_2_1i", "#t_MenuNav_11_2_1"),
)
PAGINA_CONSULTA_TRANSACOES = 5320

# Consulta de transações (página 5320)
TRANS_DATA_INICIAL = "#P5320_DATA_INICIAL_input"
TRANS_DATA_FINAL = "#P5320_DATA_FINAL_input"
TRANS_CREDENCIADO = "#P5320_CREDENCIADO_PESQ"
TRANS_PESQUISAR = "#PESQUISAR"
TRANS_TOTAL_QTD = "#P5320_TOTAL_TRANSACAO"
TRANS_TOTAL_VALOR = "#P5320_VALOR_TOTAL_TRANSACAO"
TRANS_CAB_DATA = "#DATA_LANCTO a"
TRANS_ORDEM_DESC = "#LISTA_sort_widget_action_down button"
# Células da coluna "Data lançamento". No Interactive Report, cada célula aponta para o id do cabeçalho.
TRANS_CELULA_DATA = 'td[headers="DATA_LANCTO"]'
TRANS_CELULA_DATA_ALTERNATIVA = 'xpath=//*[@id="5853054184045474152"]/tbody/tr[2]/td[7]'  # MAPEAR: id numérico
TRANS_SEM_DADOS = "#LISTA .nodatafound, .nodatafound, .a-IRR-noDataMsg"

# Lista de contratos do credenciado
CONTRATOS_LINHAS = (
    "xpath=/html/body/div[2]/div/form/div/div[1]/section/div[2]/section[2]/div[2]"
    "/table/tbody[2]/tr/td/table/tbody/tr[td[2]/a]"
)  # MAPEAR
CONTRATO_LINK_NUMERO = "xpath=./td[2]/a"
CONTRATO_LINK_PRODUTO = "xpath=./td[3]/a"
CONTRATOS_CAB_NUMERO = 'xpath=//*[@id="NRO_CONTRATO"]/div/span[1]/a'
CONTRATOS_VOLTAR = "xpath=/html/body/div[2]/div/form/div/div[1]/section/div[1]/span/button"  # MAPEAR

# Detalhe do contrato (página 2111)
CONTRATO_ESTADO = "#P2111_ESTADO"
# Campo lido pela versão Selenium da habilitação; provavelmente o mesmo P2111_ESTADO exibido como texto.
CONTRATO_ESTADO_ALTERNATIVO = (
    "xpath=/html/body/div[2]/div/form/div/div[1]/section/div[2]/section[1]/div[2]"
    "/table/tbody/tr[1]/td[3]/span/span"
)  # MAPEAR
CONTRATO_REDE_CAPTURA = "#report_REDE_DE_CAPTURA"
CONTRATO_MENU_OPCOES = "#CONTRATOS"
CONTRATO_MENU_APROVAR = "#CONTRATOS_MENU_menu_1i"
CONTRATO_OBS = "#P2111_OBS1"
CONTRATO_PLANOS = "#report_PLANOS_DE_COMPRA"
CONTRATO_PLANO_LINKS = 'xpath=//*[@id="report_PLANOS_DE_COMPRA"]/tbody[2]/tr/td/table/tbody/tr/td[2]/a'
BOTAO_OK = "#OK"
BOTAO_VOLTAR = "#VOLTAR"
BOTAO_NOVO = "#NOVO"

# Plano de compra (página 2114). Dia 1, Dia 2 e os dias da semana aparecem conforme a periodicidade.
PLANO_TIPO = "#P2114_PLANO_COMPRA"   # só no plano novo; a versão Selenium escolhia a 2ª opção ("A VISTA")
PLANO_PAGTO_APOS = "#P2114_PAGTO_APOS"
PLANO_PERIODICIDADE = "#P2114_PERIODICIDADE"
PLANO_DIA_1 = "#P2114_DIA_1"
PLANO_DIA_2 = "#P2114_DIA_2"
PLANO_DIA_SEMANA = "#P2114_DIA_SEMANA{n}"   # 1 a 7
PLANO_TIPO_DIA = "#P2114_TIPO_DIA"
PLANO_BANCARIZACAO = "#P2114_BANCARIZACAO"
PLANO_TAXA = "#P2114_TAXA_REEMBOLSO"
# Salvar um plano existente: 1º botão do cabeçalho da região. O plano novo salva com #OK.
PLANO_SALVAR_EXISTENTE = "xpath=/html/body/div[1]/div/form/div/div[1]/section/div[1]/span/button[1]"  # MAPEAR

# Tabela "Rede de captura" (HTML real em MIGRACAO_RESPOSTAS.md): uma linha por rede
# (CARDSE, CIELO, REDECARD), com as células identificadas pelo atributo `headers`.
REDE_LINHAS = "#report_REDE_DE_CAPTURA table.fwReport > tbody > tr"
REDE_COL_ORIGEM = 'td[headers="ID_ORIGEM_TRANSACAO"]'
REDE_COL_SITUACAO = 'td[headers="ID_ESTADO_ENVARQ"]'
REDE_COL_HABILITADO = 'td[headers="HABILITADO"]'
REDE_LINK_ACAO = 'td[headers="DISPLAY"] a'  # texto "Habilitar", "Desabilitar" ou "Desfazer" (situação ENVIADO)

# Popups ExtJS (confirmação "Sim" ao desabilitar, aviso "OK" ao habilitar CIELO)
MESSAGEBOX = 'div[id*="messagebox"]:visible'

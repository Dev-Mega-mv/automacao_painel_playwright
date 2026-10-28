# Painel de Automações: especificação para a versão Playwright

Este documento descreve o que o painel faz hoje, como o portal Infox está organizado e como cada automação funciona passo a passo, já pensando na reescrita com Playwright. A ideia é que quem for migrar consiga trabalhar só com este arquivo e o portal aberto, sem precisar decifrar as 4.400 linhas de Selenium em `automacao_painel/automacoes/`.

Escrito a partir da leitura do código da branch `main` de `automacao_painel` em 27/10/2026. Onde o comportamento não pôde ser confirmado só pelo código, o texto diz **(confirmar)**.

## Situação da migração

O Playwright é um projeto próprio (`automacao_painel_playwright`, porta **8082**), que só mostra as telas já migradas. O painel Selenium (`automacao_painel`, porta **8081**) continua como estava, com todas as telas.

| Tela | Onde roda | Código |
| --- | --- | --- |
| `/ativador` (habilitação CIELO/CARDSE e modo verificação, com um credenciado ou planilha; junta `/individual` e `/lote`) | **8082 (Playwright)** | `automacoes/habilitacao/` |
| `/extrator` (cadastro e consulta de transações, com um credenciado ou planilha). Falta testar no portal real | **8082 (Playwright)** | `automacoes/extrator/` |
| `/acessos` (criação de acesso no painel administrativo da Megavale). Veio de `automacao_criacao_acesso`, fora do painel Selenium. Falta testar no real | **8082 (Playwright)** | `automacoes/acesso/` |
| `/coleta` (código de estabelecimento de uma origem e situação dos contratos, com um credenciado ou planilha; `/coleta-codigo-estabelecimento` redireciona para ela). Falta testar no portal real | **8082 (Playwright)** | `automacoes/coleta/` |
| `/conciliacao` (conciliação de vendas EDI, com um credenciado ou planilha; `/alt-conciliacao` redireciona para ela). Falta testar no portal real | **8082 (Playwright)** | `automacoes/conciliacao/` |
| `/taxas` (plano de compra de todos os contratos, com um credenciado ou planilha; `/alt-taxa` redireciona para ela). Falta testar no portal real | **8082 (Playwright)** | `automacoes/taxa/` |

Todas as telas do painel Selenium já têm versão Playwright. Falta validar no portal real as que ainda não foram (extrator, coleta, conciliação, taxas e criação de acesso) antes de aposentar a 8081.

Testes no portal real (27/10/2026):

- O login com Playwright passou sozinho, inclusive o captcha, em cerca de 10 s.
- Pesquisa por código, lista de contratos (134 no credenciado 106941), abertura do contrato e leitura da rede de captura funcionaram com os seletores herdados.
- ATIVAR CARDSE funcionou de ponta a ponta: 17 contratos do credenciado 235733, com o SIM confirmado em cada um.
- **Em aberto:** em DESATIVAR CIELO com situação `ENVIADO` (credenciado 106941), o popup "Sim" foi confirmado, mas a coluna Habilitado continuou `SIM` nos 134 contratos. Conferir no portal se a CIELO ficou desativada. Se ficou, a tela só demora a atualizar e basta aumentar `RedeCaptura.TEMPO_CONFIRMACAO_MS` (hoje 8 s). Se não ficou, rodar um contrato só (campo "Produto") com `SALVAR_TRACE=sempre` e abrir o trace para ver o popup. A versão Selenium não confere o resultado depois do clique, então teria o mesmo comportamento sem avisar.

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Decisões para a versão Playwright](#2-decisões-para-a-versão-playwright)
3. [Primeiro risco: o captcha do login](#3-primeiro-risco-o-captcha-do-login)
4. [Mapa do portal Infox](#4-mapa-do-portal-infox)
5. [Fluxos de cada automação](#5-fluxos-de-cada-automação)
6. [O painel Flask: o que precisa continuar igual](#6-o-painel-flask-o-que-precisa-continuar-igual)
7. [Arquitetura proposta](#7-arquitetura-proposta)
8. [Esqueleto de código](#8-esqueleto-de-código)
9. [Problemas atuais que não devem ser copiados](#9-problemas-atuais-que-não-devem-ser-copiados)
10. [Plano de migração e checklist de paridade](#10-plano-de-migração-e-checklist-de-paridade)
11. [Setup e depuração](#11-setup-e-depuração)
12. [Glossário](#12-glossário)

---

## 1. Visão geral

O painel é uma aplicação Flask (`app.py`, porta 8081) usada pela equipe para executar tarefas repetitivas no portal **Infox** (`https://online.fwcard.com.br/fwcard/`), que é uma aplicação **Oracle APEX** (aplicação 380).

Fluxo de uma execução:

1. O usuário abre uma tela do painel, informa login e senha do Infox e envia um código/CNPJ ou uma planilha `.xlsx` com a coluna `COD`.
2. O `app.py` valida o formulário, lê a planilha com pandas e inicia uma **thread** com a automação.
3. A automação abre um Chrome com perfil próprio, entra no portal, faz login e percorre os credenciados da lista.
4. O progresso fica em um dicionário de status em memória. A tela `/status` consulta `/api/status` periodicamente e mostra barra de progresso, item atual e logs.
5. No fim, um relatório `.xlsx` fica disponível em `/download_relatorio`.

Só uma automação roda por vez. O botão de parar (`/stop`) marca `request_stop`, e a automação confere essa marca entre um item e outro.

### As automações

| Automação | Arquivo atual | Tela(s) | Altera dados no portal? |
| --- | --- | --- | --- |
| Ativar/desativar CIELO e CARDSE | `automacoes/cielo_cardse.py` | `/individual`, `/lote` | **Sim** |
| Verificação de CIELO/CARDSE | `automacoes/cielo_cardse.py` (modo verificação) | `/individual`, `/lote` | Não |
| Coleta de código de estabelecimento | `automacoes/cielo_cardse.py` (modo coleta) | `/coleta-codigo-estabelecimento`, `/lote` | Não |
| Alterar taxa / plano de compra | `automacoes/alt_taxa.py` | `/alt-taxa` | **Sim** |
| Alterar conciliação EDI | `automacoes/alt_conciliacao.py` | `/alt-conciliacao` | **Sim** |
| Extrator de cadastro | `automacoes/extrator.py` | `/extrator` | Não |
| Extrator de transações | `automacoes/extrator.py` (modo transações) | `/extrator` | Não |

A distinção "altera dados ou não" importa para a ordem da migração (seção 10): os fluxos só de leitura podem ser comparados lado a lado com a versão Selenium sem risco.

---

## 2. Decisões para a versão Playwright

**Linguagem: Python, com a API síncrona do Playwright.** O painel é Flask e os relatórios usam pandas e openpyxl. Com Playwright em Python, só a camada de navegador muda. Em TypeScript seria preciso reescrever também o servidor e os relatórios.

**Um Playwright por execução, criado dentro da thread.** Objetos do Playwright (browser, context, page) não podem ser compartilhados entre threads. Cada execução faz `with sync_playwright() as pw:` dentro da própria thread e fecha tudo no fim. O Flask não usa asyncio nas threads, então a API síncrona funciona sem conflito.

**Chrome instalado na máquina, com perfil persistente.** `chromium.launch_persistent_context(..., channel="chrome")` usa o Google Chrome do usuário (o mesmo objetivo dos commits recentes sobre "abrir no navegador instalado") e guarda cookies entre execuções, como as pastas `selenium-profile*` fazem hoje. Somem `chromedriver`, `webdriver-manager`, `pyautogui` e `keyboard`.

**Navegação com `page.goto()`.** Hoje a URL é digitada na barra de endereço com `pyautogui` (inclusive com um truque `shift+/` para digitar `?` em teclado ABNT2). O próprio extrator já usa `driver.get()` para abrir links `f?p=...` depois do login, então a navegação programática funciona dentro da sessão. A única dúvida é a tela de login (próxima seção).

**Janela visível por padrão.** Por causa do captcha e porque a equipe acompanha a execução. `HEADLESS=1` fica como opção para depois.

**Esperas automáticas no lugar de `time.sleep`.** O código atual tem 155 chamadas a `time.sleep`. No Playwright, `click()`, `fill()` e `expect()` já esperam o elemento ficar visível, habilitado e estável. A única espera própria necessária é a do processamento do APEX (seção 4.4).

**Seletores: começar pelos atuais e melhorar depois.** O Playwright aceita XPath com o prefixo `xpath=`. Dá para migrar com os mesmos seletores de hoje e trocar os XPaths absolutos (`/html/body/div[2]/...`) por IDs e textos aos poucos, com o portal validando cada troca.

---

## 3. Primeiro risco: o captcha do login

Na tela de login existe um elemento que o código chama de captcha (`//*[@id="uLogin"]/div[5]/div/div/div[1]`), clicado antes de enviar o formulário. Somado à digitação com atraso aleatório, ao `--disable-blink-features=AutomationControlled` e à URL digitada pelo pyautogui, tudo indica que o portal tem alguma proteção contra robôs. Não sei qual é o tipo de proteção (este documento foi escrito sem acesso ao portal).

O Playwright marca o navegador como automatizado de forma parecida com o Selenium. **Antes de migrar qualquer automação, valide o login** com um script isolado:

```python
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        "perfis/teste-login",
        channel="chrome",
        headless=False,
        no_viewport=True,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://online.fwcard.com.br/fwcard/f?p=380:100:")
    page.locator("#P100_USERNAME").press_sequentially("USUARIO", delay=60)
    page.locator("#P100_PASSWORD").press_sequentially("SENHA", delay=60)
    page.pause()  # abre o Inspector: observe o captcha, clique nele, inspecione o HTML
    page.locator("#LOGIN").click()
    expect(page.locator("#t_MenuNav_11i")).to_be_visible(timeout=20_000)
    print("Login OK")
    ctx.close()
```

Resultados possíveis:

- **Login passa sozinho:** segue o plano normal.
- **Captcha exige ação humana às vezes:** implementar o "login assistido" do esqueleto (seção 8.3). O robô preenche usuário e senha, tenta o captcha e, se o menu não aparecer, avisa na tela de status "Resolva o captcha na janela do Chrome" e espera até 2 minutos.
- **Captcha bloqueia o Playwright sempre:** última alternativa, conectar o Playwright a um Chrome aberto pelo usuário com `pw.chromium.connect_over_cdp("http://localhost:9222")` (Chrome iniciado com `--remote-debugging-port=9222`).

---

## 4. Mapa do portal Infox

### 4.1 URLs

- Login: `https://online.fwcard.com.br/fwcard/f?p=380:100:` (aplicação 380, página 100).
- Depois do login, as URLs seguem o padrão APEX `f?p=380:<página>:<sessão>:...`. O extrator já abre links `f?p=...` diretamente.
- **(confirmar)** Talvez dê para pular os cliques no menu abrindo `f?p=380:2100:<sessão>` direto. A sessão pode ser lida em `page.evaluate("() => apex.env.APP_SESSION")` ou na URL atual. Se funcionar, a navegação fica mais rápida e estável. Se o APEX exigir checksum, continue pelo menu.

### 4.2 Páginas e itens conhecidos

O prefixo dos IDs de item (`P2100_...`) indica o número da página APEX. Esses IDs são definidos pelo desenvolvedor do portal e costumam ser estáveis. Prefira-os a qualquer XPath.

| Página | Tela | Elementos usados |
| --- | --- | --- |
| 100 | Login | `#P100_USERNAME`, `#P100_PASSWORD`, botão `#LOGIN`, captcha dentro de `#uLogin` |
| (home) | Menu lateral | Pesquisa de credenciado: `#t_MenuNav_11i` → `#t_MenuNav_11_1i` → `#t_MenuNav_11_1_2i` → `#t_MenuNav_11_1_2_1i`. Consulta de transações ("Produção > Consulta > Transação"): `#t_MenuNav_11i` → `#t_MenuNav_11_2` → `#t_MenuNav_11_2_1` |
| 2100 | Pesquisa de credenciado | `#P2100_ID_CREDENCIADO` (código), `#P2100_CNPJ`, `#P2100_NOME_FANTASIA`, `#P2100_RAZAO_SOCIAL`, `#P2100_CIDADE`, `#P2100_ID_ESTADO_CREDENCIADO`, `#P2100_ID_PRODUTO`, `#P2100_UF`, botão `#PESQUISAR`, relatório `#LISTA` (Interactive Report), seletor de linhas `#LISTA_row_select` |
| 2101 | Detalhe do credenciado | `#P2101_CODIGO`, `#P2101_CNPJ`, `#P2101_FANTASIA`, `#P2101_RAZAO`, `#P2101_EMAIL`, `#P2101_EDIFNC_CONC_VENDA`, `#P2101_CELULAR`, `#P2101_TELEFONE`, `#P2101_DATA_CADASTRO`, tabela `#report_ENDERECOS` (col. 3 endereço, 4 bairro, 5 CEP, 6 cidade). Botões `#VISUALIZAR_CONTRATOS` e `#ALTERAR_CFG_EDI`. Menu "Opções" `#CREDENCIADO` → "Cadastro" `#CREDENCIADO_MENU_menu_1i` → item com texto "Código Estabelecimento" |
| (lista) | Contratos/produtos do credenciado | Tabela sem ID conhecido (hoje XPath absoluto). Coluna 2 = número do contrato (link), coluna 3 = nome do produto (link). Cabeçalho "Número" `#NRO_CONTRATO` (ordena). Botão voltar no cabeçalho da região |
| 2111 | Detalhe do contrato ("Aprovação contrato") | `#P2111_ESTADO` (APROVADO / DEFINIÇÃO / BLOQUEADO), `#report_REDE_DE_CAPTURA`, `#report_PLANOS_DE_COMPRA`, menu "Opções" `#CONTRATOS` → "Aprovar" `#CONTRATOS_MENU_menu_1i`, observação `#P2111_OBS1`, `#OK`, `#VOLTAR`, `#NOVO` (novo plano) |
| 2114 | Plano de compra | `#P2114_PLANO_COMPRA` (2ª opção = "A VISTA"), `#P2114_PAGTO_APOS`, `#P2114_PERIODICIDADE`, `#P2114_DIA_1`, `#P2114_DIA_2`, `#P2114_DIA_SEMANA1` a `7`, `#P2114_TIPO_DIA`, `#P2114_BANCARIZACAO`, `#P2114_TAXA_REEMBOLSO`, `#OK` (novo) ou 1º botão do cabeçalho (salvar existente) |
| 2118 | Código estabelecimento | Tabela `#report_CODIGO_ESTABELECIMENTO`, botão `#P2118_VOLTAR` |
| 2310 | Configuração EDI | Combo `#P2310_ID_EDIFNC_CONC_VENDA`, `#OK` |
| 5320 | Consulta de transações | `#P5320_DATA_INICIAL_input`, `#P5320_DATA_FINAL_input`, `#P5320_CREDENCIADO_PESQ`, `#PESQUISAR`, totais `#P5320_TOTAL_TRANSACAO` e `#P5320_VALOR_TOTAL_TRANSACAO`, cabeçalho de coluna `#DATA_LANCTO`, ordenação decrescente `#LISTA_sort_widget_action_down`, tabela de resultado `#5853054184045474152` (ID numérico, frágil) |

Observações:

- Em `cielo_cardse.py` e `alt_taxa.py`, os campos de pesquisa são localizados por XPath absoluto. Pela posição (`td[1]` e `td[2]` da primeira linha do formulário), devem ser os mesmos `#P2100_ID_CREDENCIADO` e `#P2100_CNPJ` usados pela conciliação e pelo extrator. **(confirmar)**
- O "estado do contrato" é lido de duas formas: `alt_taxa.py` usa `#P2111_ESTADO`, e `cielo_cardse.py` usa um XPath absoluto (`.../section[1]/.../tr[1]/td[3]/span/span`). Provavelmente é o mesmo campo, exibido como texto. **(confirmar)** Se for, use `#P2111_ESTADO` nos dois.
- O código atual nunca troca de iframe (`switch_to.frame`). Então todas as telas, inclusive os popups, estão no documento principal, e não é preciso `frame_locator`.

### 4.3 Tabela "Rede de captura" (página 2111)

É aqui que CIELO e CARDSE são habilitados. A posição das linhas é fixa no código atual:

| Linha | Rede | Coluna 2 | Coluna 3 | Coluna 4 |
| --- | --- | --- | --- | --- |
| 1 | CARDSE | Situação do arquivo (APROVADO, ENVIADO, ATIVADO, CANCELADO NA ADM, CANCELADO NA REDE ou vazio) | Habilitado (`SIM` / outro valor) | Link que alterna habilitar/desabilitar |
| 2 | CIELO | idem | idem | idem |

XPath base: `//*[@id="report_REDE_DE_CAPTURA"]/tbody[2]/tr/td/table/tbody/tr[N]/td[C]`.

Melhoria sugerida: localizar a linha pelo texto da rede (`page.locator("#report_REDE_DE_CAPTURA tr").filter(has_text="CIELO")`), se a primeira coluna trouxer o nome da rede. **(confirmar)**

### 4.4 Comportamentos do APEX que afetam a automação

**Indicadores de carregamento.** Depois de pesquisar, salvar ou trocar um combo com ação dinâmica, o APEX mostra um spinner e faz requisições AJAX. Seletores usados hoje: `.u-Processing`, `.t-Processing`, `.a-Spinner`, `.apex_loading_indicator`, `#apex_wait_overlay`, além de `apex.jQuery.active > 0`. Uma função `aguardar_apex(page)` (seção 8.4) cobre todos.

**Campos em cascata.** Na página 2114, `Dia 1`/`Dia 2`/`Dia da semana` aparecem ou são recarregados depois que a periodicidade muda. O código atual tem cerca de 300 linhas tentando acertar esses campos (`apex.item().setValue`, eventos `change`, "forçar elementos relacionados"). No Playwright, o caminho recomendado é:
1. `select_option` na periodicidade;
2. `aguardar_apex(page)`;
3. `expect(page.locator("#P2114_DIA_1")).to_be_visible()`;
4. `select_option` ou `fill` no campo;
5. `expect(locator).to_have_value(...)` para confirmar.

Só se isso falhar, usar `page.evaluate("([id, v]) => apex.item(id).setValue(v)", [item_id, valor])`.

**Menus "Opções".** Os botões `#CONTRATOS` e `#CREDENCIADO` abrem menus APEX que, segundo comentário no código, "só abrem com clique físico". O `click()` do Playwright é um clique real de mouse, então deve funcionar sem truques. O item "Código Estabelecimento" abre por hover dentro de "Cadastro": use `hover()` no item pai e depois `get_by_role("menuitem", name=...)` ou `get_by_text`.

**Popups ExtJS.** Alguns botões abrem uma caixa de mensagem ExtJS (`div` com `id` contendo `messagebox`, botões com classe `x-btn`):
- ao **desabilitar** CIELO ou CARDSE: confirmação com botão **"Sim"**;
- às vezes ao **habilitar** CIELO: aviso com botão **"OK"** (id visto: `button-1006`, gerado dinamicamente, não confiar nele).

No Playwright: `page.locator('div[id*="messagebox"]:visible').get_by_text("Sim", exact=True).click(timeout=2000)`, tratando o timeout como "não apareceu popup".

**Paginação.** Nem o código atual nem este documento tratam paginação da lista de contratos. Se um credenciado tiver mais contratos do que cabem numa página, os excedentes são ignorados hoje. **(confirmar)**

---

## 5. Fluxos de cada automação

### 5.1 Peças comuns

Todas as automações usam a mesma sequência de entrada, que vai para o núcleo comum:

1. **Abrir portal e logar** (seção 3).
2. **Ir para a pesquisa de credenciado:** quatro cliques no menu; pronto quando `#P2100_ID_CREDENCIADO` aparece.
3. **Pesquisar:** limpar os dois campos, preencher código ou CNPJ, clicar em `#PESQUISAR`. Três resultados possíveis:
   - abre direto o detalhe (página 2101);
   - mostra uma lista em `#LISTA`, e é preciso abrir o primeiro link;
   - mostra "nenhum dado" (`#LISTA .a-IRR-noDataMsg-text`).

   Hoje só o extrator trata os três casos. As outras automações supõem que o detalhe abre direto.
4. **Voltar** para a pesquisa e repetir para o próximo item.

**Normalização do código/CNPJ** (vem da planilha como texto, às vezes com `.0` do Excel):

| Tipo de pesquisa | Regra |
| --- | --- |
| Código | `valor.split(".")[0]` |
| CNPJ/CPF (`normalizar_cpf_cnpj`) | manter só dígitos; até 11 dígitos → `zfill(11)` (CPF); 12 ou 13 → `zfill(14)`; 14 ou mais → como está |
| CNPJ no lote de taxa | `split(".")[0].zfill(14)` (regra diferente, unificar) |
| Extrator | decide o campo pelo valor: 14 dígitos → CNPJ, senão código |

### 5.2 Ativar/desativar CIELO e CARDSE

**Entradas por item:** `cod`, `tecnologia` (1 = CIELO, 2 = CARDSE, 3 = AMBOS), `acao_cielo` e `acao_cardse` (`ATIVAR`/`DESATIVAR`), `produto_unico` (nome de produto opcional).

**Entradas gerais:** `tipo_pesquisa`, `produto_inicio` (pular contratos com número menor), `cardse_statuses` (situações do CARDSE que podem ser desativadas: `APROVADO`, `ENVIADO`, `ATIVADO`, `CANCELADO NA REDE`).

**Por credenciado:**

1. Pesquisa de credenciado → pesquisar → `#VISUALIZAR_CONTRATOS`.
2. **Garantir ordem crescente:** se o primeiro número da lista não for 1, clicar no cabeçalho `#NRO_CONTRATO` e conferir de novo (até 4 tentativas).
3. Para cada linha da lista de contratos:
   1. Ler número (coluna 2) e nome do produto (coluna 3).
   2. Pular se `número < produto_inicio`.
   3. Pular se `produto_unico` foi informado e o nome for diferente (sem diferenciar maiúsculas).
   4. Clicar no número → esperar a tabela de rede de captura.
   5. **Aprovar se necessário:** se o estado do contrato for `DEFINIÇÃO`, abrir "Opções" (`#CONTRATOS`) → "Aprovar" (`#CONTRATOS_MENU_menu_1i`) → preencher `#P2111_OBS1` com `Ativação realizada por bot` → `#OK`.
   6. Aplicar as regras abaixo.
   7. `#VOLTAR` → esperar a lista de novo.
4. Voltar à tela do credenciado.

**Regras por rede** ("habilitado" significa coluna 3 = `SIM`):

| Rede | Ação | Já está no estado pedido | Caso contrário |
| --- | --- | --- | --- |
| CIELO | ATIVAR | habilitado → nada | clicar no link → confirmar popup "OK" se aparecer (até 2 s) → esperar `SIM` (4 s; se não vier, só aviso) |
| CIELO | DESATIVAR | não habilitado → nada | clicar → confirmar "Sim" → esperar valor diferente de `SIM` |
| CARDSE | ATIVAR | habilitado → nada | clicar → esperar `SIM` |
| CARDSE | DESATIVAR | não habilitado → nada | se a situação (coluna 2) **não contém** nenhum valor de `cardse_statuses` → pular. Senão: clicar → confirmar "Sim". Se continuar `SIM` (a situação pode ter mudado, ex.: ENVIADO → ATIVADO) e a nova situação também estiver permitida → clicar de novo e confirmar. Esperar valor diferente de `SIM` |

Com `AMBOS`, aplica CIELO e depois CARDSE na mesma tela de contrato, antes de voltar.

No Playwright, as esperas de status viram asserções:

```python
expect(celula_rede(page, "CIELO", 3)).to_have_text("SIM", timeout=4000)
expect(celula_rede(page, "CARDSE", 3)).not_to_have_text("SIM", timeout=4000)
```

**Saída:** só log. Não gera relatório no modo ativação.

### 5.3 Verificação (modo de 5.2 sem alterar nada)

Mesmo caminho até a lista de contratos. Para cada contrato, abre o detalhe e lê as quatro células da rede de captura: situação e habilitado de CIELO e de CARDSE. Volta para a lista.

**Saída:** `verificacao_AAAAMMDD_HHMMSS.xlsx`, aba "Verificação": título geral; para cada credenciado, uma faixa "Credenciado: X" e uma tabela com `#`, `Produto`, `CIELO — Situação Arquivo`, `CIELO — Habilitado`, `CARDSE — Situação Arquivo`, `CARDSE — Habilitado`, `Observação`. `SIM` em verde, `NÃO` em vermelho. O código de formatação está em `_gerar_relatorio_xlsx` (`cielo_cardse.py:182`) e pode ser reaproveitado sem mudanças.

### 5.4 Coleta de código de estabelecimento

**Entrada:** planilha `COD` e `origem_transacao` (texto livre, ex.: `CARDSE`).

**Por credenciado:**

1. Pesquisa → pesquisar.
2. "Opções" (`#CREDENCIADO`) → "Cadastro" (`#CREDENCIADO_MENU_menu_1i`) → "Código Estabelecimento" (busca por texto, sem acento e sem diferenciar maiúsculas).
3. Na tabela `#report_CODIGO_ESTABELECIMENTO`, achar a linha em que alguma célula contém a origem procurada. As 4 células seguintes são: código do estabelecimento, data de cadastro, data de alteração, situação. Se não achar, observação "Origem 'X' não encontrada".
4. `#P2118_VOLTAR`.
5. Se a situação for `INATIVO`, não abre contratos ("Contratos não coletados - código inativo").
6. Senão: `#VISUALIZAR_CONTRATOS` → para cada contrato, abrir e ler a **situação do CARDSE** (coluna 2 da linha 1 da rede de captura; vazio = `DESATIVADO`) → agrupar números de contrato por situação → voltar.
7. Resumo: `"ATIVADO: 3 | CANCELADO NA REDE: 1"`. Detalhes: `"ATIVADO (3): 1, 2, 4"` por linha, ou `"Todos os N contratos estão em X."` quando só há uma situação.

**Saída:** `coleta_codigo_estabelecimento_*.xlsx` com aba "Resumo" (gerado em, origem alvo, tipo de pesquisa, processados, total, último credenciado, ponto de parada, lista de erros) e aba "Coleta" (Código Infox/CNPJ, Origem de Transação, Código Estabelecimento, Data Cadastro, Data Alteração, Situação, Contratos Totais, Resumo Contratos, Detalhes Contratos, Observação). **Salva parcialmente depois de cada credenciado**, para não perder o trabalho se o portal cair. Esse comportamento deve ser mantido e estendido às outras automações.

### 5.5 Alterar taxa / plano de compra

**Entradas (individual):** `cod_cnpj`, `taxa` (ex.: `1,50`), `periodicidade` (`DIÁRIA`, `SEMANAL`, `MENSAL`, `QUINZENAL`), `pag_dias`, `dia1`, `dia2`, `bancarizar` (`SIM`/`NÃO`), `tipo_dia` (`INDIFERENTE`, `PAR`, `ÍMPAR`), `dias_semana[]`.

**Colunas da planilha (lote) e apelidos aceitos:**

| Campo | Colunas aceitas |
| --- | --- |
| código | `COD`, `CODIGO`, `COD_CNPJ`, `CNPJ`, `CPF_CNPJ` |
| taxa | `TAXA`, `TAXA_REEMBOLSO`, `TAXA (%)` |
| periodicidade | `PERIODICIDADE` |
| dias para pagamento | `PAG`, `PAG_DIAS`, `DIAS_PAGAMENTO`, `PAGAMENTO_DIAS` |
| dia 1 / dia 2 | `DIA1`/`DIA_1`, `DIA2`/`DIA_2` |
| bancarizar | `BANCARIZAR` (padrão `NÃO`) |
| tipo de dia | `TIPO_DIA`, `TIPO DIA` (padrão `INDIFERENTE`) |
| dias da semana | `DIA_SEM1` a `DIA_SEM7`, ou `DIAS_SEMANA` com valores separados por `;`, `,` ou `/` |
| nome fantasia | `FANTASIA` (só vai para o relatório) |

Dias da semana válidos: `DOMINGO`, `SEGUNDA`, `TERCA`, `QUARTA`, `QUINTA`, `SEXTA`, `SABADO` (sem acento).

A taxa é normalizada como número com vírgula: `"1.5"` ou `"1,50"` viram `"1,5"`. Taxa em branco mantém a taxa atual.

**Por credenciado:**

1. Pesquisa → pesquisar → (individual: ler `#P2101_FANTASIA`) → `#VISUALIZAR_CONTRATOS`.
2. Para cada contrato da lista:
   1. Abrir o contrato e ler `#P2111_ESTADO`.
   2. Se `BLOQUEADO` → voltar, próximo.
   3. Se existe plano em `#report_PLANOS_DE_COMPRA` (link na coluna 2 da primeira linha, espera até 5 s) → **atualizar plano**. Senão → **criar plano**.
   4. Ler o estado de novo. Se `DEFINIÇÃO` → aprovar ("Opções" `#CONTRATOS` → "Aprovar" `#CONTRATOS_MENU_menu_1i` → `#OK`). Se já `APROVADO`, o plano não mudou e não precisa aprovar.
   5. `#VOLTAR`.
3. Voltar à tela do credenciado.

**Atualizar plano existente:** `#P2114_PAGTO_APOS` = dias para pagamento → periodicidade → se `SEMANAL`, preencher `#P2114_DIA_SEMANA{i}` e `#P2114_TIPO_DIA`; senão `#P2114_DIA_1` e `#P2114_DIA_2` (ignorar `0` ou vazio) → `#P2114_TAXA_REEMBOLSO` (se informada) → `#P2114_BANCARIZACAO` → salvar (primeiro botão do cabeçalho da região; mapear o ID).

**Criar plano:** `#NOVO` → `#P2114_PLANO_COMPRA` = 2ª opção ("A VISTA") → aguardar APEX → mesmos campos acima, **exceto dias para pagamento** (ver seção 9) → `#OK`.

**Saída:** `resultados_taxa/resultado_slot0_*.xlsx` com as colunas de entrada e uma coluna `RESULTADO` ("Alterado com sucesso!" ou "Erro! ...").

### 5.6 Alterar conciliação EDI

**Entradas:** planilha `COD`, `tipo_pesquisa` (padrão CNPJ) e `nome_conciliacao`, uma destas opções da tela:

- `CONCILIACAO DE VENDAS - SPANI ATACADISTA`
- `CONCILIACAO DE VENDAS - SHIBATA SUPERMERCADOS`
- `CONCILIACAO DE VENDAS - SEMAR SUPERMERCADOS`
- `CONCILIACAO DE VENDAS - PADRÃO`

**Por credenciado:** pesquisa → pesquisar → `#ALTERAR_CFG_EDI` → selecionar `nome_conciliacao` em `#P2310_ID_EDIFNC_CONC_VENDA` → `#OK`.

**Saída:** `uploads/resultado_conciliacao_*.xlsx` com `CNPJ`, `Status`, `Mensagem`.

É a automação mais simples e a melhor candidata a piloto (seção 8.6 tem ela completa em Playwright).

### 5.7 Extrator de cadastro

**Entrada:** planilha `COD` (código ou CNPJ, misturados).

**Por item:**

1. Na tela de pesquisa, limpar código e CNPJ, preencher o campo certo (14 dígitos = CNPJ), `#PESQUISAR`.
2. Tratar os três resultados possíveis (5.1). Na lista, abrir o `href` do primeiro link com `goto` (o link é relativo, `f?p=...`, prefixar com a URL base).
3. Ler 13 campos: `CODIGO`, `CNPJ`, `NOME_FANTASIA`, `RAZAO_SOCIAL`, `CIDADE`, `ENDERECO`, `BAIRRO`, `CEP`, `EMAIL`, `CONCILIACAO`, `CELULAR`, `TELEFONE`, `DATA_CADASTRO` (seletores na seção 8.2). Para cada um, usar o primeiro valor não vazio entre `value` e o texto do elemento.
4. Considerar "vazio" se nenhum entre código, CNPJ, razão social, fantasia, e-mail, telefone e celular veio preenchido.
5. Salvar parcial e voltar à pesquisa pelo menu (se falhar, abrir a página inicial e tentar o menu de novo).

**Saída:** `outputs_planilha/credenciados_*.xlsx` (CSV como alternativa se o Excel falhar) e `credenciados_temp.xlsx` durante a execução.

**Modo por filtros (inalcançável hoje):** o código também filtra por situação, produto, UF etc., aumenta a lista para 1000 linhas e percorre os resultados. Nenhuma tela do painel chega nesse modo, porque `app.py` sempre envia a planilha. Decidir se esse modo vale a pena antes de migrar.

### 5.8 Extrator de transações

**Entradas:** planilha `COD`, `data_inicial` e `data_final` (`DD/MM/AAAA`) e a funcionalidade escolhida: `valor_venda_total` ou `data_ultima_transacao`.

**Por código:**

1. Menu: `#t_MenuNav_11i` → `#t_MenuNav_11_2` → `#t_MenuNav_11_2_1`. Pronto quando os três campos e `#PESQUISAR` estão presentes. Esse caminho é refeito a cada código.
2. Preencher `#P5320_DATA_INICIAL_input`, `#P5320_DATA_FINAL_input` e `#P5320_CREDENCIADO_PESQ`, conferindo se o valor ficou (até 3 tentativas). No Playwright: `fill()` seguido de `expect(locator).to_have_value(valor)`.
3. `#PESQUISAR`.
4. **Valor total:** esperar `#P5320_TOTAL_TRANSACAO` e `#P5320_VALOR_TOTAL_TRANSACAO` ficarem preenchidos, sem spinner, e com o mesmo valor em 3 leituras seguidas, 1 s entre elas (até 90 s). Gravar `QTD_TRANSACOES` e `VALOR_TOTAL_TRANSACOES`.
5. **Data da última transação:** esperar o fim do processamento. Se não houver dados (`.nodatafound` ou `.a-IRR-noDataMsg` com "nenhum"/"no data"), gravar "Nao houve transacoes no periodo". Senão, clicar no cabeçalho `#DATA_LANCTO`, depois em ordenar decrescente (`#LISTA_sort_widget_action_down`), e ler a coluna 7 da 2ª linha da tabela de resultado. Mapear um seletor melhor que o ID numérico da região.

**Saída:** mesma pasta do extrator de cadastro, com colunas `CODIGO`, `DATA_INICIAL`, `DATA_FINAL` e `QTD_TRANSACOES` + `VALOR_TOTAL_TRANSACOES` ou `DATA_ULTIMA_TRANSACAO`.

---

## 6. O painel Flask: o que precisa continuar igual

As telas (`templates/`) e a tela de status não precisam mudar se o contrato abaixo for mantido.

### 6.1 Rotas e parâmetros

| Rota | Campos do formulário | Automação |
| --- | --- | --- |
| `/individual` | `login_infox`, `senha_infox`, `tipo_pesquisa` (`COD`/`CNPJ`), `cod_cnpj`, `tecnologia` (`CIELO`/`CARDSE`/`AMBOS`), `acao_cielo`, `acao_cardse`, `modo_verificacao` (`0`/`1`), `produto_inicio`, `produto_unico`, `cardse_statuses[]` | 5.2 / 5.3 |
| `/lote` | os mesmos + `file`, `modo_coleta`, `origem_transacao_alvo`. Planilha: `COD` obrigatória; `TECNOLOGIA`, `ACAO_CIELO`, `ACAO_CARDSE`, `PRODUTO` opcionais por linha (vazio = valor da tela) | 5.2 / 5.3 / 5.4 |
| `/coleta-codigo-estabelecimento` | `login_infox`, `senha_infox`, `tipo_pesquisa`, `origem_transacao`, `file` | 5.4 |
| `/alt-taxa` | `mode` (`individual`/`lote`) + campos de 5.5 ou `file` | 5.5 |
| `/alt-conciliacao` | `login_infox`, `senha_infox`, `tipo_pesquisa`, `nome_conciliacao`, `file` | 5.6 |
| `/extrator` | `login_infox`, `senha_infox`, `tipo_pesquisa`, `consultas_transacoes` (checkbox), `funcionalidade_transacao`, `data_inicial`, `data_final`, `file` | 5.7 / 5.8 |
| `/status`, `/api/status`, `/stop`, `/download_relatorio` | | acompanhamento |

No painel Playwright, `/individual` e `/lote` viraram uma tela só, `/ativador`. Ela recebe os campos de `/individual` mais `entrada` (`unico` ou `planilha`) e `file`. As colunas da planilha são as mesmas do `/lote`, mas um valor inválido recusa a planilha em vez de cair no padrão da tela. `modo_coleta` e `origem_transacao_alvo` ficaram de fora: a coleta terá tela própria (5.4). Os endereços antigos redirecionam para `/ativador`. `/ativador/modelo-planilha` baixa uma planilha modelo em branco. Detalhes no `README.md`, seção "Planilha do ativador".

A `/coleta` do painel Playwright recebe `entrada` (`unico` ou `planilha`), `tipo_pesquisa` (`COD`, `CPF` ou `CNPJ`), `origem_transacao` (padrão `CARDSE`) e `cod_cnpj` ou `file`. `/coleta/modelo-planilha` baixa a planilha modelo. Diferenças em relação ao Selenium no `README.md`, seção "Coleta".

A `/conciliacao` do painel Playwright recebe `entrada`, `tipo_pesquisa` (`COD`, `CPF` ou `CNPJ`; começa em `COD`), `nome_conciliacao` (uma das quatro opções) e `cod_cnpj` ou `file`. `/conciliacao/modelo-planilha` baixa a planilha modelo. Diferenças no `README.md`, seção "Conciliação".

A `/taxas` do painel Playwright recebe `entrada`, `tipo_pesquisa`, `cod_cnpj` ou `file` e o plano: `taxa`, `pag_dias`, `periodicidade`, `dia1`, `dia2`, `dias_semana[]`, `tipo_dia` e `bancarizar`. O `mode` (`individual`/`lote`) virou `entrada`. Com planilha, o plano da tela vale para as células vazias. `/taxas/modelo-planilha` baixa a planilha modelo. Diferenças no `README.md`, seção "Taxas".

O `/extrator` do painel Playwright recebe `entrada` (`unico` ou `planilha`), `modo` (`cadastro` ou `transacoes`), `tipo_pesquisa`, `cod_cnpj` ou `file`, e, nas transações, `funcionalidade_transacao` e `data_inicial`/`data_final` (campo de data do navegador, convertido para DD/MM/AAAA). O checkbox `consultas_transacoes` virou o `modo`. `/extrator/modelo-planilha` baixa a planilha modelo. Diferenças em relação ao Selenium no `README.md`, seção "Extrator".

### 6.2 Contrato do `/api/status`

`templates/status.html` consulta esta rota e espera exatamente estes campos:

```json
{
  "running": true,
  "total": 120,
  "processed": 37,
  "current_item": "04149637010753",
  "logs": ["[10:02:11] Iniciando navegador...", "[10:02:15] SUCESSO: ..."],
  "progress": 30,
  "tem_relatorio": false,
  "automacao": "conciliacao"
}
```

Formato de cada log: `[HH:MM:SS] PREFIXO: mensagem`, com prefixo `ERRO`, `AVISO`, `SUCESSO` ou nenhum.

---

## 7. Arquitetura

A branch `refatorando-codigo` do `automacao_painel` já tem um `automacoes/base.py` com uma `AutomacaoBase` em Selenium. A versão Playwright segue a mesma ideia. Estrutura atual deste projeto (o que está marcado "a criar" vem nas próximas migrações):

```text
automacao_painel_playwright/
  app.py                        # painel Flask (porta 8082)
  config.py                     # porta, URL do portal, timeouts, HEADLESS, pastas
  rotas/                        # uma blueprint por funcionalidade
    inicio.py                   # /
    habilitacao.py              # /ativador (um credenciado ou planilha)
    extrator.py                 # /extrator (cadastro ou transações)
    coleta.py                   # /coleta (código de estabelecimento e situação dos contratos)
    conciliacao.py              # /conciliacao (conciliação de vendas EDI)
    taxa.py                     # /taxas (plano de compra dos contratos)
    acesso.py                   # /acessos (criação de acesso no painel Megavale)
    upload.py                   # confere a planilha enviada pelo formulário
    execucao.py                 # /status, /api/status, /stop, /download_relatorio
  automacoes/
    core/                       # peças comuns, sem regra de negócio
      seletores.py              # seletores do portal (MAPEAR = XPath absoluto a melhorar)
      texto.py                  # normalização de código/CNPJ e textos
      planilha.py               # planilhas de entrada: ler_linhas(), ler_codigos(), montar_modelo()
      relatorio.py              # planilhas de saída: salvar_tabela(), salvar_xlsx()
      erros.py                  # ErroAutomacao, LoginFalhou, CredenciadoNaoEncontrado...
      apex.py                   # aguardar_apex(), apex_ocioso(), ler_valor(), confirmar_messagebox()
      status_execucao.py        # class StatusExecucao (thread-safe, formato do /api/status)
      execucao.py               # uma execução por vez: iniciar(), atual(), em_execucao()
      navegador.py              # class Navegador (Chrome persistente, screenshot, trace)
      portal_infox.py           # class PortalInfox (login, menu, pesquisa, contratos, consulta de transações)
      automacao_base.py         # AutomacaoBase (ciclo de vida, erro por item) e AutomacaoPorItem (relatório a cada item)
    habilitacao/                # 5.2 e 5.3
      item_habilitacao.py       # class ItemHabilitacao (credenciado + ações)
      rede_captura.py           # class RedeCaptura (lê e alterna CIELO/CARDSE)
      habilitacao.py            # class Habilitacao(AutomacaoBase): regras e modo verificação
      planilha_habilitacao.py   # ler_itens() (planilha -> ItemHabilitacao) e gerar_modelo()
      relatorios.py             # planilhas de verificação e de habilitação
    coleta/                     # 5.4
      coleta.py                 # class ColetaEstabelecimento(AutomacaoPorItem) e resumir_contratos()
      relatorio_coleta.py       # abas Resumo e Coleta, com o layout da versão Selenium
      planilha_coleta.py        # gerar_modelo()
    taxa/                       # 5.5
      item_taxa.py              # class ItemTaxa e a validação dos valores
      plano_compra.py           # class PlanoCompra (página 2114: preencher, conferir, salvar)
      taxa.py                   # class AlteracaoTaxa(AutomacaoPorItem)
      planilha_taxa.py          # ler_itens() e gerar_modelo()
    conciliacao/                # 5.6
      conciliacao.py            # class Conciliacao(AutomacaoPorItem) e CONCILIACOES
      planilha_conciliacao.py   # gerar_modelo()
    extrator/                   # 5.7 e 5.8
      extrator_base.py          # class ExtratorBase(AutomacaoPorItem)
      cadastro.py               # class ExtratorCadastro (5.7)
      transacoes.py             # class ExtratorTransacoes (5.8)
      planilha_extrator.py      # gerar_modelo()
    acesso/                     # criação de acesso (fora do painel Selenium; ver README)
      dados_infox.py            # DadosCredenciado lidos da tela do credenciado
      painel_megavale.py        # class PainelMegavale (login, busca e cadastro no painel administrativo)
      criacao_acesso.py         # class CriacaoAcesso(AutomacaoPorItem)
      planilha_acesso.py        # gerar_modelo()
  templates/                    # telas copiadas do painel Selenium, só as migradas; _menu.html é a barra superior
  static/css/                   # styles.css (original) + tema.css (tema visual, removível)
  perfis/                       # perfis do Chrome (fora do git)
  logs/                         # log por execução, capturas de erro e traces (fora do git)
  relatorios/                   # planilhas geradas (fora do git)
```

A seção 8 é o esboço original, escrito antes do código. O código real em `automacoes/` e `rotas/` é a referência quando os dois divergirem. O roteiro para migrar a próxima tela está no `README.md`.

Princípios:

- **`core/` não conhece regra de negócio.** Sabe logar, navegar, pesquisar e esperar o APEX.
- **Cada fluxo implementa só `processar_item()`.** A base cuida de abrir o navegador, logar, percorrer os itens, respeitar o botão parar, registrar sucesso ou erro por item, salvar relatório parcial e fechar.
- **Erro em um item não para o lote.** O item vai para o relatório com a mensagem, e um screenshot é salvo em `logs/`. Só um navegador fechado ou o login falhando encerram a execução.
- **Selenium e Playwright convivem durante a migração em projetos separados.** Cada tela migrada passa a existir na 8082 e ganha lugar no menu e na tela inicial. Telas não migradas não aparecem no painel novo. Quando todas estiverem migradas, o `automacao_painel` pode ser aposentado.

---

## 8. Esqueleto de código

Código de partida, não testado contra o portal. Os seletores vêm do código atual.

### 8.1 `config.py`

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PASTA_PERFIS = BASE_DIR / "perfis"
PASTA_LOGS = BASE_DIR / "logs"
PASTA_RELATORIOS = BASE_DIR / "relatorios"
PASTA_UPLOADS = BASE_DIR / "uploads"

URL_PORTAL = "https://online.fwcard.com.br/fwcard/"
URL_LOGIN = URL_PORTAL + "f?p=380:100:"

HEADLESS = os.getenv("HEADLESS", "0") == "1"
TIMEOUT_PADRAO_MS = int(os.getenv("TIMEOUT_PADRAO_MS", "15000"))
ESPERA_CAPTCHA_S = int(os.getenv("ESPERA_CAPTCHA_S", "120"))
SALVAR_TRACE = os.getenv("SALVAR_TRACE", "erro")  # "sempre" | "erro" | "nunca"

for pasta in (PASTA_PERFIS, PASTA_LOGS, PASTA_RELATORIOS, PASTA_UPLOADS):
    pasta.mkdir(exist_ok=True)
```

### 8.2 `core/seletores.py`

Os XPaths absolutos estão marcados com `# MAPEAR`: funcionam hoje, mas devem ser trocados por algo estável assim que alguém olhar a tela no Inspector.

```python
# Login (página 100)
LOGIN_USUARIO = "#P100_USERNAME"
LOGIN_SENHA = "#P100_PASSWORD"
LOGIN_BOTAO = "#LOGIN"
LOGIN_CAPTCHA = 'xpath=//*[@id="uLogin"]/div[5]/div/div/div[1]'  # MAPEAR

# Menu lateral
MENU_RAIZ = "#t_MenuNav_11i"  # visível = login concluído
MENU_PESQUISA_CREDENCIADO = ["#t_MenuNav_11i", "#t_MenuNav_11_1i", "#t_MenuNav_11_1_2i", "#t_MenuNav_11_1_2_1i"]
MENU_CONSULTA_TRANSACOES = ["#t_MenuNav_11i", "#t_MenuNav_11_2", "#t_MenuNav_11_2_1"]

# Pesquisa de credenciado (2100)
PESQ_CODIGO = "#P2100_ID_CREDENCIADO"
PESQ_CNPJ = "#P2100_CNPJ"
PESQ_BOTAO = "#PESQUISAR"
PESQ_PRIMEIRO_RESULTADO = 'xpath=(//*[@id="LISTA"]//tr[td//a]//td[1]//a)[1]'
PESQ_SEM_DADOS = "#LISTA .a-IRR-noDataMsg-text"

# Detalhe do credenciado (2101)
DET_CODIGO = "#P2101_CODIGO"
DET_CNPJ = "#P2101_CNPJ"
DET_FANTASIA = "#P2101_FANTASIA"
DET_RAZAO = "#P2101_RAZAO"
DET_EMAIL = "#P2101_EMAIL"
DET_CONCILIACAO = "#P2101_EDIFNC_CONC_VENDA"
DET_CELULAR = "#P2101_CELULAR"
DET_TELEFONE = "#P2101_TELEFONE"
DET_DATA_CADASTRO = "#P2101_DATA_CADASTRO"
DET_ENDERECO = 'xpath=//*[@id="report_ENDERECOS"]/tbody[2]/tr/td/table/tbody/tr/td[3]/a'
DET_BAIRRO = 'xpath=//*[@id="report_ENDERECOS"]/tbody[2]/tr/td/table/tbody/tr/td[4]/a'
DET_CEP = 'xpath=//*[@id="report_ENDERECOS"]/tbody[2]/tr/td/table/tbody/tr/td[5]/a'
DET_CIDADE = 'xpath=//*[@id="report_ENDERECOS"]/tbody[2]/tr/td/table/tbody/tr/td[6]/a'
DET_BTN_CONTRATOS = "#VISUALIZAR_CONTRATOS"
DET_BTN_ALTERAR_EDI = "#ALTERAR_CFG_EDI"
DET_MENU_OPCOES = "#CREDENCIADO"
DET_MENU_CADASTRO = "#CREDENCIADO_MENU_menu_1i"

# Lista de contratos
CONTRATOS_LINHAS = 'xpath=/html/body/div[2]/div/form/div/div[1]/section/div[2]/section[2]/div[2]/table/tbody[2]/tr/td/table/tbody/tr[td[2]/a]'  # MAPEAR
CONTRATOS_CAB_NUMERO = 'xpath=//*[@id="NRO_CONTRATO"]/div/span[1]/a'
CONTRATOS_VOLTAR = 'xpath=/html/body/div[2]/div/form/div/div[1]/section/div[1]/span/button'  # MAPEAR

# Detalhe do contrato (2111)
CONTRATO_ESTADO = "#P2111_ESTADO"
CONTRATO_PLANO_EXISTENTE = 'xpath=//*[@id="report_PLANOS_DE_COMPRA"]/tbody[2]/tr/td/table/tbody/tr/td[2]/a'
CONTRATO_MENU_OPCOES = "#CONTRATOS"
CONTRATO_MENU_APROVAR = "#CONTRATOS_MENU_menu_1i"
CONTRATO_OBS = "#P2111_OBS1"
BOTAO_OK = "#OK"
BOTAO_VOLTAR = "#VOLTAR"
BOTAO_NOVO = "#NOVO"
LINHA_REDE = {"CARDSE": 1, "CIELO": 2}
COL_SITUACAO, COL_HABILITADO, COL_BOTAO = 2, 3, 4

# Plano de compra (2114)
PLANO_TIPO = "#P2114_PLANO_COMPRA"
PLANO_PAGTO_APOS = "#P2114_PAGTO_APOS"
PLANO_PERIODICIDADE = "#P2114_PERIODICIDADE"
PLANO_DIA_1 = "#P2114_DIA_1"
PLANO_DIA_2 = "#P2114_DIA_2"
PLANO_DIA_SEMANA = "#P2114_DIA_SEMANA{n}"
PLANO_TIPO_DIA = "#P2114_TIPO_DIA"
PLANO_BANCARIZACAO = "#P2114_BANCARIZACAO"
PLANO_TAXA = "#P2114_TAXA_REEMBOLSO"
PLANO_SALVAR_EXISTENTE = 'xpath=/html/body/div[1]/div/form/div/div[1]/section/div[1]/span/button[1]'  # MAPEAR

# Código estabelecimento (2118)
CODEST_TABELA = "#report_CODIGO_ESTABELECIMENTO"
CODEST_VOLTAR = "#P2118_VOLTAR"

# Configuração EDI (2310)
EDI_CONCILIACAO = "#P2310_ID_EDIFNC_CONC_VENDA"

# Consulta de transações (5320)
TRANS_DATA_INICIAL = "#P5320_DATA_INICIAL_input"
TRANS_DATA_FINAL = "#P5320_DATA_FINAL_input"
TRANS_CREDENCIADO = "#P5320_CREDENCIADO_PESQ"
TRANS_TOTAL_QTD = "#P5320_TOTAL_TRANSACAO"
TRANS_TOTAL_VALOR = "#P5320_VALOR_TOTAL_TRANSACAO"
TRANS_COL_DATA_LANCTO = "#DATA_LANCTO a"
TRANS_ORDENAR_DESC = "#LISTA_sort_widget_action_down button"
TRANS_DATA_ULTIMA = 'xpath=//*[@id="5853054184045474152"]/tbody/tr[2]/td[7]'  # MAPEAR (ID numérico)

# Popups ExtJS
MESSAGEBOX = 'div[id*="messagebox"]:visible'


def celula_rede(rede: str, coluna: int) -> str:
    n = LINHA_REDE[rede]
    return f'xpath=//*[@id="report_REDE_DE_CAPTURA"]/tbody[2]/tr/td/table/tbody/tr[{n}]/td[{coluna}]'
```

### 8.3 `core/navegador.py` e `core/portal.py`

```python
# core/navegador.py
from playwright.sync_api import Playwright, BrowserContext
import config


def abrir_contexto(pw: Playwright, perfil: str) -> BrowserContext:
    contexto = pw.chromium.launch_persistent_context(
        str(config.PASTA_PERFIS / perfil),
        channel="chrome",
        headless=config.HEADLESS,
        no_viewport=True,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    contexto.set_default_timeout(config.TIMEOUT_PADRAO_MS)
    if config.SALVAR_TRACE != "nunca":
        contexto.tracing.start(screenshots=True, snapshots=True)
    return contexto
```

```python
# core/portal.py
from enum import Enum
from playwright.sync_api import Page, expect
import config
from . import seletores as S
from .apex import aguardar_apex


class LoginFalhou(Exception):
    pass


class ResultadoPesquisa(Enum):
    ABERTO = "aberto"
    NAO_ENCONTRADO = "nao_encontrado"


class Portal:
    def __init__(self, page: Page, log):
        self.page = page
        self.log = log

    def abrir_e_logar(self, usuario: str, senha: str):
        page = self.page
        self.log("Abrindo portal...")
        page.goto(config.URL_LOGIN)
        page.locator(S.LOGIN_USUARIO).fill("")
        page.locator(S.LOGIN_USUARIO).press_sequentially(usuario, delay=60)
        page.locator(S.LOGIN_SENHA).fill("")
        page.locator(S.LOGIN_SENHA).press_sequentially(senha, delay=60)

        captcha = page.locator(S.LOGIN_CAPTCHA)
        if captcha.is_visible():
            captcha.click()
        page.locator(S.LOGIN_BOTAO).click()

        menu = page.locator(S.MENU_RAIZ)
        try:
            expect(menu).to_be_visible(timeout=15_000)
        except AssertionError:
            # Login assistido: dá tempo para alguém resolver o captcha na janela aberta.
            self.log("Login não concluiu sozinho. Resolva o captcha na janela do Chrome.", "WARNING")
            try:
                expect(menu).to_be_visible(timeout=config.ESPERA_CAPTCHA_S * 1000)
            except AssertionError:
                raise LoginFalhou("Login não concluído. Confira usuário, senha e captcha.")
        self.log("Login realizado.")

    def clicar_menu(self, caminho: list[str]):
        for seletor in caminho:
            self.page.locator(seletor).click()

    def ir_para_pesquisa_credenciado(self):
        self.clicar_menu(S.MENU_PESQUISA_CREDENCIADO)
        expect(self.page.locator(S.PESQ_CODIGO)).to_be_visible()

    def pesquisar(self, valor: str, tipo: str) -> ResultadoPesquisa:
        page = self.page
        page.locator(S.PESQ_CODIGO).fill("")
        page.locator(S.PESQ_CNPJ).fill("")
        page.locator(S.PESQ_CNPJ if tipo == "CNPJ" else S.PESQ_CODIGO).fill(valor)
        page.locator(S.PESQ_BOTAO).click()
        aguardar_apex(page)

        detalhe = page.locator(S.DET_CODIGO)
        lista = page.locator(S.PESQ_PRIMEIRO_RESULTADO)
        vazio = page.locator(S.PESQ_SEM_DADOS)
        expect(detalhe.or_(lista).or_(vazio).first).to_be_visible()

        if vazio.is_visible():
            return ResultadoPesquisa.NAO_ENCONTRADO
        if not detalhe.is_visible():
            href = lista.get_attribute("href") or ""
            page.goto(href if href.startswith("http") else config.URL_PORTAL + href)
            expect(detalhe).to_be_visible()
        return ResultadoPesquisa.ABERTO

    def abrir_contratos(self):
        self.page.locator(S.DET_BTN_CONTRATOS).click()
        expect(self.page.locator(S.CONTRATOS_LINHAS).first).to_be_visible()
```

### 8.4 `core/apex.py`

```python
from playwright.sync_api import Page, TimeoutError as PwTimeout
from . import seletores as S

_JS_APEX_OCIOSO = """
() => {
  const visivel = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const spinners = ['.u-Processing', '.t-Processing', '.a-Spinner', '.apex_loading_indicator', '#apex_wait_overlay'];
  if (spinners.some(s => [...document.querySelectorAll(s)].some(visivel))) return false;
  const jq = window.apex && apex.jQuery;
  return !(jq && jq.active > 0);
}
"""


def aguardar_apex(page: Page, timeout_ms: int = 30_000):
    """Espera o APEX terminar spinners e requisições AJAX."""
    page.wait_for_function(_JS_APEX_OCIOSO, timeout=timeout_ms)


def set_item(page: Page, item_id: str, valor: str):
    """Plano B para campos em cascata que não aceitam select_option/fill."""
    page.evaluate("([id, v]) => apex.item(id).setValue(v)", [item_id, str(valor)])
    aguardar_apex(page)


def confirmar_messagebox(page: Page, texto: str, timeout_ms: int = 2000) -> bool:
    """Clica em 'Sim'/'OK' no popup ExtJS. Retorna False se o popup não apareceu."""
    # O ExtJS cria vários divs com "messagebox" no id; .first evita violar o strict mode.
    botao = page.locator(S.MESSAGEBOX).get_by_text(texto, exact=True).first
    try:
        botao.click(timeout=timeout_ms)
        return True
    except PwTimeout:
        return False
```

### 8.5 `core/status.py` e `core/base.py`

```python
# core/status.py
import threading
from datetime import datetime

_PREFIXOS = {"ERROR": "ERRO", "WARNING": "AVISO", "SUCCESS": "SUCESSO"}


class StatusExecucao:
    def __init__(self, nome: str, arquivo_log=None):
        self.nome = nome
        self.arquivo_log = arquivo_log
        self._lock = threading.Lock()
        self.running = False
        self.total = 0
        self.processed = 0
        self.current_item = None
        self.logs: list[str] = []
        self.relatorio_path = None
        self.parada_solicitada = False
        self.inicio = self.fim = None

    def log(self, mensagem: str, nivel: str = "INFO"):
        prefixo = _PREFIXOS.get(nivel, "")
        linha = f"[{datetime.now():%H:%M:%S}] {prefixo + ': ' if prefixo else ''}{mensagem}"
        with self._lock:
            self.logs.append(linha)
        if self.arquivo_log:
            with open(self.arquivo_log, "a", encoding="utf-8") as f:
                f.write(linha + "\n")

    def iniciar(self, total: int):
        with self._lock:
            self.running, self.total, self.processed = True, total, 0
            self.inicio = datetime.now()

    def avancar(self, item):
        with self._lock:
            self.processed += 1
            self.current_item = item

    def finalizar(self):
        with self._lock:
            self.running = False
            self.fim = datetime.now()

    def para_api(self) -> dict:
        """Mesmo formato que status.html já consome (seção 6.2)."""
        with self._lock:
            total = max(1, self.total)
            return {
                "running": self.running,
                "total": self.total,
                "processed": self.processed,
                "current_item": self.current_item,
                "logs": list(self.logs),
                "progress": int(min(self.processed, total) / total * 100),
                "tem_relatorio": bool(self.relatorio_path) and self.relatorio_path.exists(),
                "automacao": self.nome,
            }
```

```python
# core/base.py
from datetime import datetime
from playwright.sync_api import sync_playwright
import config
from .navegador import abrir_contexto
from .portal import Portal


class AutomacaoBase:
    nome = "base"

    def __init__(self, credenciais: dict, itens: list, status, tipo_pesquisa="COD", **opcoes):
        self.credenciais = credenciais
        self.itens = itens
        self.status = status
        self.tipo_pesquisa = tipo_pesquisa
        self.opcoes = opcoes
        self.resultados: list[dict] = []
        self.carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- pontos de extensão --------------------------------------------
    def processar_item(self, page, item) -> str:
        """Faz o trabalho de um item e devolve a mensagem de sucesso. Levanta exceção em caso de erro."""
        raise NotImplementedError

    def gerar_relatorio(self):
        """Padrão: uma linha por item. Fluxos com layout próprio sobrescrevem."""
        import pandas as pd
        if not self.resultados:
            return
        caminho = config.PASTA_RELATORIOS / f"{self.nome}_{self.carimbo}.xlsx"
        pd.DataFrame(self.resultados).to_excel(caminho, index=False)
        self.status.relatorio_path = caminho

    # --- ciclo de vida -------------------------------------------------
    def executar(self):
        self.status.iniciar(len(self.itens))
        teve_erro = False
        try:
            with sync_playwright() as pw:
                contexto = abrir_contexto(pw, perfil=self.nome)
                page = contexto.pages[0] if contexto.pages else contexto.new_page()
                try:
                    self.portal = Portal(page, self.status.log)
                    self.portal.abrir_e_logar(self.credenciais["login_infox"], self.credenciais["senha_infox"])
                    for item in self.itens:
                        if self.status.parada_solicitada:
                            self.status.log("Interrupção solicitada.")
                            break
                        if not self._executar_item(page, item):
                            teve_erro = True
                        if page.is_closed():
                            self.status.log("Navegador fechado. Encerrando.", "ERROR")
                            break
                finally:
                    self._salvar_trace(contexto, teve_erro)
                    contexto.close()
        except Exception as e:
            self.status.log(f"Erro crítico: {e}", "ERROR")
        finally:
            self.gerar_relatorio()
            self.status.finalizar()
            self.status.log(f"Concluído. Processados: {self.status.processed}/{self.status.total}")

    def _executar_item(self, page, item) -> bool:
        cod = item["cod"] if isinstance(item, dict) else item
        self.status.current_item = cod
        self.status.log("-" * 40)
        self.status.log(f"Processando {cod}")
        try:
            mensagem = self.processar_item(page, item)
            self.resultados.append({"ITEM": cod, "STATUS": "SUCESSO", "MENSAGEM": mensagem})
            self.status.log(f"{cod}: {mensagem}", "SUCCESS")
            return True
        except Exception as e:
            msg = str(e).splitlines()[0][:200]
            self.resultados.append({"ITEM": cod, "STATUS": "ERRO", "MENSAGEM": msg})
            self.status.log(f"{cod}: {msg}", "ERROR")
            if not page.is_closed():
                page.screenshot(path=config.PASTA_LOGS / f"{self.nome}_{self.carimbo}_{cod}.png", full_page=True)
            return False
        finally:
            self.status.avancar(cod)

    def _salvar_trace(self, contexto, teve_erro):
        if config.SALVAR_TRACE == "sempre" or (config.SALVAR_TRACE == "erro" and teve_erro):
            contexto.tracing.stop(path=config.PASTA_LOGS / f"{self.nome}_{self.carimbo}_trace.zip")
        elif config.SALVAR_TRACE != "nunca":
            contexto.tracing.stop()
```

### 8.6 Piloto completo: `conciliacao/conciliacao.py`

Com o núcleo pronto, o fluxo inteiro da conciliação fica assim (hoje são 313 linhas):

```python
from playwright.sync_api import expect
from automacoes.core.base import AutomacaoBase
from automacoes.core.portal import ResultadoPesquisa
from automacoes.core.apex import aguardar_apex
from automacoes.core import seletores as S


class Conciliacao(AutomacaoBase):
    nome = "conciliacao"

    def processar_item(self, page, item):
        alvo = self.opcoes["nome_conciliacao"]
        self.portal.ir_para_pesquisa_credenciado()
        if self.portal.pesquisar(item["cod"], self.tipo_pesquisa) is ResultadoPesquisa.NAO_ENCONTRADO:
            raise ValueError("Credenciado não encontrado na pesquisa")

        page.locator(S.DET_BTN_ALTERAR_EDI).click()
        combo = page.locator(S.EDI_CONCILIACAO)
        atual = combo.locator("option:checked").inner_text().strip()
        if atual == alvo:
            return "Já estava com a conciliação pedida"

        combo.select_option(label=alvo)
        page.locator(S.BOTAO_OK).click()
        aguardar_apex(page)
        return f"Alterada de '{atual}' para '{alvo}'"
```

### 8.7 Trecho do ativador: percorrer contratos

Mostra o padrão que substitui os índices de XPath e os `StaleElementReference`. Depois de voltar para a lista, a página é recarregada; por isso a linha é localizada de novo pelo índice a cada volta.

```python
def percorrer_contratos(self, page, item):
    linhas = page.locator(S.CONTRATOS_LINHAS)
    expect(linhas.first).to_be_visible()
    total = linhas.count()
    alterados = 0
    for i in range(total):
        if self.status.parada_solicitada:
            break
        linha = linhas.nth(i)
        numero = int(linha.locator("xpath=./td[2]/a").inner_text().strip())
        produto = linha.locator("xpath=./td[3]/a").inner_text().strip()
        if numero < self.opcoes["produto_inicio"]:
            continue
        if item.get("produto_unico") and produto.upper() != item["produto_unico"].upper():
            continue

        linha.locator("xpath=./td[2]/a").click()
        expect(page.locator(S.celula_rede("CARDSE", S.COL_HABILITADO))).to_be_attached()
        self.aprovar_se_necessario(page)
        if self.aplicar_regras(page, item):  # tabela da seção 5.2
            alterados += 1
        page.locator(S.BOTAO_VOLTAR).click()
        expect(linhas.first).to_be_visible()
    return f"{alterados} de {total} contratos alterados"
```

### 8.8 Integração com o `app.py`

```python
import threading
from datetime import datetime
import config
from automacoes.core.status import StatusExecucao

_trava = threading.Lock()
_execucao: StatusExecucao | None = None


def iniciar_execucao(nome: str, criar_automacao) -> bool:
    """Marca a execução como ativa ANTES de criar a thread, para impedir início duplo."""
    global _execucao
    with _trava:
        if _execucao and _execucao.running:
            return False
        status = StatusExecucao(nome, arquivo_log=config.PASTA_LOGS / f"{nome}_{datetime.now():%Y%m%d_%H%M%S}.txt")
        status.running = True
        _execucao = status
    threading.Thread(target=lambda: criar_automacao(status).executar(), daemon=True).start()
    return True


# Na rota:
#   ok = iniciar_execucao("conciliacao", lambda st: Conciliacao(
#            credenciais, itens, st, tipo_pesquisa=tipo, nome_conciliacao=nome))
#   if not ok: flash("Já existe uma automação em execução.")
#
# /api/status  -> jsonify(_execucao.para_api() if _execucao else {...valores vazios...})
# /stop        -> _execucao.parada_solicitada = True
```

---

## 9. Problemas atuais que não devem ser copiados

Alguns são bugs; outros são comportamentos que alguém do negócio precisa confirmar antes de mudar.

| # | Onde | O que acontece hoje | Na versão nova |
| --- | --- | --- | --- |
| 1 | `alt_taxa.py:414` | Um erro em um credenciado **interrompe o lote inteiro** | Registrar o erro e seguir. **Confirmar com o negócio** se houve motivo para parar. *Feito no passo 16:* o erro encerra o credenciado e a execução segue; para sozinha depois de 3 credenciados seguidos com erro |
| 2 | `alt_taxa.py:1055` | Ao **criar** plano, `PAGTO_APOS` (dias para pagamento) não é preenchido; ao atualizar, é | **Confirmar** se é intencional. *Passo 16:* mantido como no Selenium, com aviso no relatório em cada plano criado |
| 3 | `alt_taxa.py:831` | Compara `item_id == 'P2114_DIA1'`, mas a função recebe `'P2114_DIA_1'`: o caminho "achar o select pelo rótulo Dia 1" nunca roda | Usar o fluxo da seção 4.4 |
| 4 | `alt_taxa.py:484, 1080, 1097` | `_obter_estado_produto` existe 3 vezes; vale a última, que em erro devolve `DEFINIÇÃO` (e então tenta aprovar) | Uma função só. Em erro de leitura, falhar o item em vez de aprovar no escuro |
| 5 | `cielo_cardse.py:1516–1622` | Métodos duplicados (`_ativar_cielo_rapido`, popup CIELO, desabilitar CARDSE); vale a última definição | Implementar só a regra da tabela 5.2 |
| 6 | `cielo_cardse.py:603` | Falha no login é registrada mas não interrompe; a automação segue e falha depois | `LoginFalhou` encerra a execução com mensagem clara |
| 7 | `cielo_cardse.py:868` | Erro em um credenciado não conta no progresso nem aparece em relatório | Toda execução tem relatório com status por item |
| 8 | `alt_conciliacao.py:224, 272` | Não confere se a pesquisa achou o credenciado; nome da conciliação montado dentro do XPath | `pesquisar()` com os 3 resultados; `select_option(label=...)` |
| 9 | Login (4 arquivos) | Dispara `apex.submit`, ENTER e clique; pode enviar duas vezes; não verifica sucesso | Um clique em `#LOGIN` e `expect` do menu |
| 10 | `extrator.py:497, 502` | Em erro, salva um arquivo "final" novo a cada falha (vários arquivos por execução) | Um arquivo temporário atualizado por item e um final |
| 11 | `app.py` (extrator) | Checkbox de transações marcado sem datas: nenhuma consulta é feita e não há aviso | Validar no formulário |
| 12 | `app.py` (coleta) | Não converte nomes de coluna para maiúsculas; `cod` minúsculo falha só nessa tela | `ler_codigos()` único para todas as rotas |
| 13 | `app.py:63` | Duas automações podem iniciar ao mesmo tempo (status vira `running` só dentro da thread) | `iniciar_execucao()` com trava (8.8) |
| 14 | `app.py:711` | `debug=True` com `host=0.0.0.0` expõe o console do Werkzeug na rede | `debug` só por variável de ambiente; nunca com `0.0.0.0` |
| 15 | `alt_taxa.py:1245` | `iniciar_duplo` (dois navegadores em paralelo) e `taxa_status2` sem rota | Não migrar. Se precisar de paralelismo, fazer depois na base |

---

## 10. Plano de migração e checklist de paridade

A ordem vai dos fluxos que só leem para os que alteram dados. Os de leitura podem rodar lado a lado com a versão Selenium, com a mesma planilha, e os relatórios comparados linha a linha.

| Etapa | Entrega | Como validar |
| --- | --- | --- |
| 0. Login | Script da seção 3 funcionando | Login completo 5 vezes seguidas, com e sem perfil novo |
| 1. Núcleo + conciliação | `automacoes/conciliacao/` + `rotas/conciliacao.py` | Rodar uma lista pequena; conferir no portal; testar credenciado inexistente e conciliação já correta |
| 2. Extrator de cadastro | `extrator_cadastro.py` | Mesma planilha nas duas versões; comparar os 13 campos |
| 3. Extrator de transações | `extrator_transacoes.py` | Comparar totais e datas para os mesmos códigos e período |
| 4. Verificação e coleta | `verificacao.py`, `coleta_estab.py` | Comparar os dois xlsx |
| 5. Taxa | `taxa.py` | Começar com um credenciado de teste; conferir plano, taxa, dias e aprovação |
| 6. Ativação CIELO/CARDSE | `ativacao.py` | Verificação antes e depois em um credenciado de teste, para cada combinação da tabela 5.2 |
| 7. Limpeza | Apagar `automacoes/`, `selenium-profile*`, dependências Selenium/pyautogui/keyboard | Painel inteiro funcionando só com Playwright |

Checklist de paridade, para cada automação:

- [ ] Mesmo resultado no portal (ou no relatório) para a mesma entrada.
- [ ] Mesmas colunas e o mesmo formato de relatório, ou mudança combinada com quem usa.
- [ ] Botão parar interrompe entre itens.
- [ ] Credenciado inexistente vira linha de erro, sem parar o lote.
- [ ] Senha errada encerra com mensagem clara na tela de status.
- [ ] Fechar o Chrome no meio encerra a execução e gera relatório parcial.
- [ ] `/api/status` no mesmo formato (6.2); a tela de status funciona sem alteração.
- [ ] Erro gera screenshot e trace em `logs/`.

---

## 11. Setup e depuração

**Dependências (`requirements.txt`):**

```text
flask
playwright
pandas
openpyxl
werkzeug
```

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Com channel="chrome" usa o Chrome já instalado; este comando só é necessário para usar o Chromium do Playwright:
python -m playwright install chromium
```

**Ferramentas úteis para mapear e depurar:**

- `page.pause()` em qualquer ponto abre o **Playwright Inspector**: dá para clicar nos elementos da tela e copiar um seletor sugerido. É a forma mais rápida de substituir os seletores `# MAPEAR`, já que o login exige captcha.
- `python -m playwright codegen --channel=chrome "https://online.fwcard.com.br/fwcard/f?p=380:100:"` grava cliques e gera código. Útil para descobrir os textos e papéis (`get_by_role`) dos menus.
- Com `SALVAR_TRACE=sempre`, cada execução gera um `trace.zip` em `logs/`. Abra com `python -m playwright show-trace logs/<arquivo>.zip` para ver cada passo com screenshot, DOM e rede.
- `PWDEBUG=1 python app.py` faz o Playwright abrir o Inspector e executar passo a passo.

**Cuidados:**

- Não use o perfil normal do Chrome do usuário em `launch_persistent_context`: ele fica travado enquanto o Chrome estiver aberto. Use `perfis/<automação>`.
- Um perfil não pode ser aberto por dois Chromes ao mesmo tempo. Com uma automação por vez, isso não acontece.
- Rode o Flask sem `debug=True`. O recarregador cria um segundo processo, e o Playwright não deve ser criado fora da thread da execução.
- Coloque `perfis/`, `logs/`, `relatorios/` e `uploads/` no `.gitignore`.

---

## 12. Glossário

| Termo | Significado |
| --- | --- |
| Infox | Portal operacional (Oracle APEX) em `online.fwcard.com.br/fwcard` |
| Credenciado | Estabelecimento cadastrado; identificado por código Infox ou CNPJ/CPF |
| Contrato / produto | Cada produto que o credenciado aceita (ex.: "ALIMENTACAO PRIVADO"); listado em "Visualizar contratos", com número sequencial |
| Estado do contrato | `DEFINIÇÃO` (alterado, precisa aprovar), `APROVADO`, `BLOQUEADO` |
| Rede de captura | Adquirente pela qual o produto transaciona: CIELO ou CARDSE |
| Situação do arquivo | Estado do envio para a rede: APROVADO, ENVIADO, ATIVADO, CANCELADO NA ADM, CANCELADO NA REDE, ou vazio |
| Habilitado | Se a rede está ligada para o contrato (`SIM`/`NÃO`) |
| Plano de compra | Condições de pagamento do contrato: periodicidade, dias, taxa de reembolso, bancarização |
| Conciliação EDI | Layout de arquivo de conciliação de vendas enviado ao cliente |
| Código estabelecimento | Código do credenciado em cada origem de transação (ex.: o código CARDSE) |
| Origem de transação | Sistema de onde vêm as transações (ex.: CARDSE) |

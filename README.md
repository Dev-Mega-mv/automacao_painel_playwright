# Painel de Automações (Playwright)

Versão Playwright do painel de automações do portal Infox. Roda na **porta 8082**, separada do painel Selenium (`automacao_painel`, porta 8081). As telas são migradas uma por vez, e este painel só mostra as que já foram migradas.

| Tela | Situação |
| --- | --- |
| Ativador (habilitação CIELO/CARDSE e modo verificação), com um credenciado ou uma planilha. Junta as telas Individual e Lote do painel Selenium | Migrada |
| Extrator de dados: cadastro dos credenciados ou consulta de transações (valor total ou última transação), com um credenciado ou uma planilha | Migrada (falta testar no portal real) |
| Coleta de código de estabelecimento de uma origem de transação (ex.: CARDSE) e da situação dos contratos, com um credenciado ou uma planilha | Migrada (falta testar no portal real) |
| Criação de acesso dos credenciados no painel administrativo da Megavale (vinda de `automacao_criacao_acesso`, que não fazia parte do painel Selenium) | Migrada (falta testar no portal e no painel reais) |
| Alteração da conciliação de vendas EDI, com um credenciado ou uma planilha | Migrada (falta testar no portal real) |
| Alteração de taxas: plano de compra (taxa de reembolso, periodicidade, dias, bancarização) de todos os contratos, com um credenciado ou uma planilha | Migrada (falta testar no portal real) |

Com isso, todas as telas do painel Selenium estão neste painel. Ele só pode ser aposentado depois dos testes no portal real (ver `modificacoes/README.md`, pendências).

A especificação completa da migração (mapa do portal, fluxos, regras e plano) está em `MIGRACAO_PLAYWRIGHT.md`.

## Como rodar

```powershell
py -3.11 -m venv .venv          # ou use o Python já instalado
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abra `http://localhost:8082`. Todas as telas do painel Selenium já estão aqui; ele continua disponível (`python app.py` dentro de `automacao_painel`, porta 8081) até as versões novas serem testadas no portal real.

O Playwright usa o Google Chrome instalado na máquina (`channel="chrome"`), então não precisa de `playwright install`.

## Configuração

Tudo em `config.py`, com a opção de trocar por variável de ambiente:

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `PORTA` | `8082` | Porta deste painel |
| `HEADLESS` | `0` | `1` roda o Chrome sem janela (é o caso do Docker) |
| `TAMANHO_JANELA` | vazio (maximizada); `1600,1000` com `HEADLESS=1` | Largura e altura da janela do Chrome |
| `ESPERA_CAPTCHA_S` | `120` | Tempo para resolver o captcha à mão se o login não passar sozinho. Com `HEADLESS=1` não há espera |
| `SALVAR_TRACE` | `erro` | `sempre`, `erro` ou `nunca`. O trace abre com `python -m playwright show-trace logs/<arquivo>.zip` |
| `EXECUCOES_SIMULTANEAS` | `3` | Quantas automações podem rodar ao mesmo tempo (cada Chrome usa de 300 a 500 MB) |
| `FLASK_DEBUG` | `0` | `1` liga o modo debug. Com ele, salvar um `.py` reinicia o Flask e derruba a automação em andamento |
| `URL_PORTAL` | portal Infox | Útil para apontar para um ambiente de teste |
| `URL_MEGAVALE` | painel Megavale (`https://app.megavalecard.com.br/`) | Painel administrativo usado pela criação de acesso |

Exemplo: `$env:SALVAR_TRACE = "sempre"; python app.py`

## No servidor (Docker)

Para os funcionários usarem só pelo navegador, sem Python na máquina. O container traz o Python, o Google Chrome (sem janela) e o painel servido pelo waitress.

**Subir pela primeira vez** (no servidor, com Docker e acesso à internet):

```bash
git clone https://github.com/Dev-Mega-mv/automacao_painel_playwright.git   # repositório privado: pede usuário e token do GitHub
cd automacao_painel_playwright
docker compose up -d --build        # a primeira vez demora (a imagem tem uns 2 GB)
```

Abra `http://<ip-do-servidor>:8082`. Para usar outra porta, crie um `.env` ao lado do `docker-compose.yml` com `PORTA_HOST=8090`. Também dá para trocar `EXECUCOES_SIMULTANEAS`, `SALVAR_TRACE` e `LIMITE_MEMORIA` (padrão `3g`) por ali.

**Atualizar** depois de um `git push` feito aqui:

```bash
cd automacao_painel_playwright
git pull
docker compose up -d --build
```

Reiniciar o container derruba as automações que estiverem rodando: confira o `/status` antes.

**No dia a dia:**

- `docker compose logs -f` mostra a saída do painel. Os logs de cada execução, as capturas e os relatórios ficam em `dados/logs` e `dados/relatorios`, e os perfis do Chrome em `dados/perfis`. Eles ficam fora do container e sobrevivem às atualizações.
- `dados/` guarda dados de credenciados e cresce a cada execução. Apague o que for antigo de tempos em tempos (ex.: `find dados/logs dados/relatorios -type f -mtime +30 -delete`).
- O Chrome roda sem janela, então ninguém consegue resolver o captcha à mão. Se o login não passar sozinho, a execução para com `ERRO` em 15 segundos, sem a espera de 2 minutos.

**Bloqueio atual: o captcha da Infox.** A tela de login da Infox usa o Cloudflare Turnstile. No container, sem janela, ele não se resolve sozinho: pede o clique em "Verify you are human" (teste de 29/10/2026, passo 23 em `modificacoes/`). Então, hoje, **as automações da Infox não conseguem logar no container**. A criação de acesso também depende da Infox. Saídas possíveis: a Infox dispensar o captcha para o servidor (ou oferecer uma API), ou o Chrome com janela numa tela virtual, com uma pessoa vendo e clicando no captcha quando ele aparecer.

**Cuidados antes de abrir para a empresa:**

- O painel **não tem login**: qualquer pessoa que chegue à porta vê os logs e baixa os relatórios. Libere a porta só para a rede interna.
- Sem HTTPS, as senhas da Infox e do painel Megavale digitadas nas telas trafegam abertas na rede.
- Os perfis do Chrome são por automação, não por pessoa. Na criação de acesso, se o painel Megavale já estiver logado no perfil, a execução usa essa sessão, mesmo que seja de outra pessoa.

## Várias automações ao mesmo tempo

O painel roda até `EXECUCOES_SIMULTANEAS` automações ao mesmo tempo, de tipos iguais ou diferentes, cada uma no seu Chrome. Passando do limite, a tela avisa e não inicia.

- **Status** (`/status`) lista as execuções desde que o painel abriu: as que estão rodando e as 20 últimas encerradas. Cada uma tem a sua página (`/status/<id>`) com o log, o botão de parar e o relatório. Parar uma não mexe nas outras.
- **ID da execução** = automação + data e hora do início (ex.: `habilitacao_20261028_101500`). Se duas do mesmo tipo começarem no mesmo segundo, a segunda ganha `_2`. O ID também vai no nome do log, do relatório e das capturas, então os arquivos não se misturam.
- **Perfil do Chrome por vaga.** O Chrome não abre a mesma pasta de perfil duas vezes. A primeira execução de um tipo usa `perfis/<automação>`; uma segunda do mesmo tipo, ao mesmo tempo, usa `perfis/<automação>_2` (e avisa no log). Esse perfil começa sem sessão salva, então faz login do zero.
- **A lista fica na memória.** Ao reiniciar o painel, ela some, mas os logs e relatórios continuam em `logs/` e `relatorios/`.
- **Evite o mesmo credenciado em duas execuções que alteram o portal** (ex.: ativador e taxas no mesmo código): o painel não confere isso.

## Estrutura

```text
app.py                      # cria o Flask e registra as rotas
config.py
Dockerfile, docker-compose.yml  # painel no servidor (seção "No servidor (Docker)")
rotas/                      # uma blueprint por funcionalidade
  inicio.py                 # /
  habilitacao.py            # /ativador (/individual e /lote redirecionam para ele)
  extrator.py               # /extrator
  coleta.py                 # /coleta (/coleta-codigo-estabelecimento redireciona para ela)
  conciliacao.py            # /conciliacao (/alt-conciliacao redireciona para ela)
  taxa.py                   # /taxas (/alt-taxa redireciona para ela)
  acesso.py                 # /acessos
  upload.py                 # confere a planilha enviada pelo formulário
  execucao.py               # /status (lista), /status/<id>, /api/status, /stop/<id>, /download_relatorio/<id>
automacoes/
  core/                     # comum a todas as automações
    seletores.py            # seletores do portal (MAPEAR = XPath absoluto a melhorar)
    texto.py                # normalização de código/CNPJ e textos
    planilha.py             # planilhas de entrada: ler_linhas(), ler_codigos(), montar_modelo()
    relatorio.py            # planilhas de saída: salvar_tabela(), salvar_xlsx()
    erros.py                # ErroAutomacao, LoginFalhou, CredenciadoNaoEncontrado...
    apex.py                 # aguardar_apex(), apex_ocioso(), ler_valor(), confirmar_messagebox()
    status_execucao.py      # class StatusExecucao
    execucao.py             # execuções simultâneas (até EXECUCOES_SIMULTANEAS): iniciar(), buscar(), todas()
    navegador.py            # class Navegador (Chrome persistente, screenshot, trace)
    portal_infox.py         # class PortalInfox (login, menu, pesquisa, contratos, consulta de transações)
    automacao_base.py       # AutomacaoBase (ciclo de vida, erro por item) e AutomacaoPorItem (relatório a cada item)
  habilitacao/
    item_habilitacao.py     # class ItemHabilitacao
    rede_captura.py         # class RedeCaptura
    habilitacao.py          # class Habilitacao(AutomacaoBase)
    planilha_habilitacao.py # ler_itens() (linha -> ItemHabilitacao) e gerar_modelo() (planilha modelo)
    relatorios.py
  extrator/
    extrator_base.py        # class ExtratorBase(AutomacaoPorItem)
    cadastro.py             # class ExtratorCadastro: 13 campos da tela do credenciado
    transacoes.py           # class ExtratorTransacoes: valor total ou data da última transação no período
    planilha_extrator.py    # gerar_modelo() (planilha modelo)
  coleta/
    coleta.py               # class ColetaEstabelecimento(AutomacaoPorItem) e resumir_contratos()
    relatorio_coleta.py     # planilha com as abas Resumo e Coleta (layout da versão Selenium)
    planilha_coleta.py      # gerar_modelo() (planilha modelo)
  conciliacao/
    conciliacao.py          # class Conciliacao(AutomacaoPorItem)
    planilha_conciliacao.py # gerar_modelo() (planilha modelo)
  taxa/
    item_taxa.py            # class ItemTaxa (credenciado + plano pedido) e a validação dos valores
    plano_compra.py         # class PlanoCompra: preenche, confere e salva a tela do plano (página 2114)
    taxa.py                 # class AlteracaoTaxa(AutomacaoPorItem)
    planilha_taxa.py        # ler_itens() (linha -> ItemTaxa) e gerar_modelo() (planilha modelo)
  acesso/
    dados_infox.py          # DadosCredenciado: dados da tela do credenciado no formato do painel Megavale
    painel_megavale.py      # class PainelMegavale: login, busca e cadastro de estabelecimento e gerente
    criacao_acesso.py       # class CriacaoAcesso(AutomacaoPorItem): duas abas, Infox e Megavale
    planilha_acesso.py      # gerar_modelo() (planilha modelo)
templates/                  # telas vindas do painel Selenium, só as migradas
  _menu.html                # barra superior de todas as telas (a lista TELAS é o menu)
  execucoes.html            # lista das execuções (/status); status.html é a página de uma execução
static/css/
  styles.css                # estilo original do painel Selenium
  tema.css                  # tema visual deste painel (ver "Visual" abaixo)
perfis/, logs/, relatorios/ # gerados na execução (fora do git)
```

## Visual

O tema fica todo em `static/css/tema.css`, carregado no fim do `<head>` de cada template, depois do `styles.css` e dos `<style>` da própria página. Para voltar ao visual original do painel Selenium, apague esta linha dos templates:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/tema.css') }}">
```

Os templates usam as mesmas classes do painel Selenium. Os únicos elementos novos (`page-eyebrow`, `topbar-tag`, `card-features`, `status-pill`) continuam legíveis sem o tema.

## Planilha do ativador

Na tela do ativador, "Credenciados de onde?" escolhe entre digitar um credenciado ou enviar uma planilha `.xlsx` (a primeira aba é lida e a primeira linha é o cabeçalho).

O botão **Baixar modelo** (`/ativador/modelo-planilha`) entrega a planilha pronta para preencher. Ela é gerada na hora por `gerar_modelo()`, então acompanha as colunas e valores aceitos sem arquivo para manter. Conteúdo:

- **Aba "Credenciados"**, a que é lida. Vem só com o cabeçalho, sem linhas de exemplo: um código de exemplo esquecido ali poderia ser um credenciado real. Tem a coluna COD como texto (não perde zero à esquerda), listas de valores em TECNOLOGIA e nas ações, e uma dica ao clicar em cada coluna.
- **Aba "Como preencher"**, com as regras e um exemplo. O painel ignora essa aba.

Colunas aceitas:

| Coluna | Obrigatória | O que faz |
| --- | --- | --- |
| `COD` (ou `CODIGO`, `CNPJ`, `CPF`, `COD_CNPJ`, `CPF_CNPJ`) | Sim | Credenciado a pesquisar. O tipo de pesquisa da tela vale para todas as linhas |
| `TECNOLOGIA` | Não | `CIELO`, `CARDSE` ou `AMBOS` |
| `ACAO_CIELO`, `ACAO_CARDSE` | Não | `ATIVAR` ou `DESATIVAR` |
| `PRODUTO` | Não | Só o contrato com esse nome de produto |

- Célula vazia ou coluna ausente usa o valor escolhido na tela.
- Cabeçalho sem diferença de acento, espaço ou maiúscula (`Ação Cielo` = `ACAO_CIELO`).
- Outras colunas são ignoradas, e linhas sem código são puladas.
- Um valor inválido recusa a planilha inteira antes de abrir o Chrome, com o número da linha na mensagem. O lote do painel Selenium trocava o valor inválido pelo padrão da tela sem avisar.
- "Somente DESATIVAR ... quando situação" e "Iniciar a partir do produto" valem para todas as linhas. As situações marcadas valem para a rede que a linha desativar, CIELO ou CARDSE.
- O modo "Coleta Estabelecimento", que existia na tela de lote do Selenium, não veio para cá: ele vai ganhar tela própria quando a coleta for migrada.

## Extrator

Só lê, nunca altera nada no portal. Na tela, "O que extrair" escolhe entre:

- **Dados cadastrais.** Abre a tela de cada credenciado e lê 13 campos: código, CNPJ, nome fantasia, razão social, cidade, endereço, bairro, CEP, e-mail, conciliação, celular, telefone e data de cadastro. As colunas e a ordem são as mesmas da versão Selenium.
- **Transações.** Usa Produção > Consulta > Transação (página 5320) com o período escolhido. Traz o **valor total das vendas** (quantidade e valor) ou a **data da última transação** (ordena pela data de lançamento, da mais recente para a mais antiga). Sem transações no período, grava "Nao houve transacoes no periodo".

Os credenciados vêm de um campo (um credenciado) ou de uma planilha com a coluna `COD`, que aceita os mesmos apelidos do ativador. O botão **Baixar modelo** (`/extrator/modelo-planilha`) entrega a planilha pronta.

Diferenças em relação à versão Selenium:

- **Relatório com uma linha por item pesquisado.** Entram também os não encontrados e os que deram erro, com a coluna `RESULTADO` (`OK`, `AVISO: ...` ou `ERRO: ...`). No cadastro, a coluna `PESQUISADO` mostra o que foi pesquisado. O Selenium só gravava os encontrados.
- **Relatório gravado em `relatorios/` a cada item** (`extrator_cadastro_*.xlsx` ou `extrator_transacoes_*.xlsx`), para não perder o que já foi lido. O botão de download aparece na tela de Status quando a execução termina.
- **Credenciado conferido antes de gravar.** Se a pesquisa devolver uma lista, abre o primeiro resultado, como antes, e o relatório avisa quantos havia. Se o credenciado aberto não for o pesquisado, o item vira erro, em vez de gravar dados de outro credenciado.
- **Consulta de transações com plano B.** O caminho pelo menu falhou na maioria das execuções registradas no log do Selenium. Se o menu não abrir a tela, o extrator abre a página 5320 pelo endereço da sessão atual e avisa no log.
- **Período obrigatório e validado no formulário.** No Selenium, transações sem datas não faziam nenhuma consulta e não avisavam.
- **Endereço pelas colunas da tabela** (`headers="ENDERECO"`, `BAIRRO`, `CEP_FORMATADO`, `CIDADE_ESTADO`), como lê a automação de criação de acesso, que já roda no portal real, em vez das posições 3 a 6 herdadas do Selenium. A cidade vem como "CIDADE/UF".
- **Conciliação pelo texto.** Quando a conciliação é uma lista no portal, o relatório traz o texto da opção escolhida, e não o código interno.
- **Ficou de fora** o "modo por filtros" (situação, produto, UF...), que o painel Selenium não alcançava.

## Coleta

Só lê, nunca altera nada no portal (`/coleta`). Na tela, informe a **origem da transação** (`CARDSE` vem preenchido; `CIELO` e `REDECARD` aparecem como sugestão). Ela vale para todos os credenciados. Para cada um:

1. Em **Opções > Cadastro > Código Estabelecimento**, lê a linha da origem: código do estabelecimento, data de cadastro, data de alteração e situação.
2. Se o código estiver **INATIVO**, não abre os contratos ("Contratos não coletados - código inativo").
3. Senão, abre cada contrato e agrupa os números pela **situação do arquivo** dessa rede na tabela "Rede de captura" (vazia = `DESATIVADO`). O resumo fica como `ATIVADO: 3 | CANCELADO NA REDE: 1`, e o detalhe lista os números de cada situação (ou "Todos os N contratos estão em X").

Os credenciados vêm de um campo ou de uma planilha com a coluna `COD`, com os mesmos apelidos do ativador. O botão **Baixar modelo** (`/coleta/modelo-planilha`) entrega a planilha pronta.

O relatório `relatorios/coleta_codigo_estabelecimento_*.xlsx` tem o layout da versão Selenium: aba **Resumo** (origem, tipo de pesquisa, processados, último credenciado, onde parou e as ocorrências) e aba **Coleta** (uma linha por credenciado, com as mesmas colunas). Ele é regravado a cada credenciado.

Diferenças em relação à versão Selenium:

- **Um credenciado ou planilha**, e pesquisa por CPF. No Selenium, só planilha, por código ou CNPJ.
- **Credenciado conferido**, como no extrator: com uma lista de resultados, coleta o primeiro e anota quantos havia; se o credenciado aberto não for o pesquisado, o item vira erro.
- **Situação dos contratos pela rede da origem digitada.** O Selenium lia sempre a linha do CARDSE (a primeira da tabela), mesmo com outra origem. Com `CARDSE`, o resultado é o mesmo. Contrato sem a rede entra como `SEM <rede>`.
- **Origem procurada sem diferença de acento ou maiúscula.** Uma linha com a origem exata vem antes de uma que só contém o texto (ex.: `CARDSE PRE`). Se houver mais de uma linha da origem, a observação avisa.
- **Contrato que não abre** entra no resumo como `ERRO NA LEITURA`, com a observação e uma captura da tela. No Selenium, ele sumia da contagem.
- **Linha de erro com `ERRO:`** na observação e na lista de ocorrências do Resumo.

## Conciliação

Altera dados no portal (`/conciliacao`). Na tela, digite a **nova conciliação** com o nome que ela tem na lista do portal (ex.: `CONCILIACAO DE VENDAS - PADRÃO`). Ela vale para todos os credenciados. Para cada um:

1. Pesquisa e confere o credenciado. Uma lista de resultados ou outro credenciado vira erro, sem alterar nada.
2. Clica em **Alterar configuração EDI** e escolhe a opção com o nome pedido, sem diferença de acento ou maiúscula. Se o portal não tiver a opção, o item vira erro com a lista das opções que existem.
3. Se já estiver com a conciliação pedida, não salva. Senão, salva com **OK** e confere a conciliação mostrada na tela do credenciado.

Os credenciados vêm de um campo ou de uma planilha com a coluna `COD`. A planilha do painel Selenium funciona como está. O botão **Baixar modelo** (`/conciliacao/modelo-planilha`) entrega uma em branco.

O relatório `relatorios/conciliacao_*.xlsx` tem `PESQUISADO`, `CODIGO`, `NOME_FANTASIA`, `CONCILIACAO_ANTES`, `CONCILIACAO_DEPOIS` e `RESULTADO`: `OK (alterada)`, `OK (já estava ...)`, `AVISO: ...` ou `ERRO: ...`. É regravado a cada credenciado. Para conferir antes de alterar, o **Extrator > Dados cadastrais** traz a coluna `CONCILIACAO`.

Diferenças em relação à versão Selenium:

- **Um credenciado ou planilha**, e pesquisa por CPF. O tipo de pesquisa começa em Código, e não em CNPJ: a planilha usada no Selenium (`uploads/conciliacao.xlsx`) tinha códigos.
- **Credenciado conferido.** O Selenium não conferia se a pesquisa tinha achado o credenciado e seguia para o botão de alterar.
- **Conciliação digitada.** O Selenium só oferecia quatro opções fixas (SPANI, SHIBATA, SEMAR e PADRÃO). Agora vale qualquer opção que o portal tenha.
- **Opção pelo texto, sem acento nem maiúscula.** O Selenium montava um XPath com o texto exato; com outra grafia, dava erro de tempo.
- **Não salva o que já está certo**, e o relatório diz isso.
- **Salvamento conferido.** O Selenium esperava 2 segundos depois do OK e dava sucesso. Agora: a conciliação precisa aparecer na tela do credenciado. Uma mensagem de erro do portal vira `ERRO` com o texto dela. Se a tela de configuração continuar aberta com a conciliação pedida, vira `AVISO` para conferir.
- **Relatório com antes e depois**, no lugar de `CNPJ`, `Status` e `Mensagem`.

## Taxas

Altera dados no portal (`/taxas`). Na tela, o **plano de compra** pedido:

- **Taxa de reembolso** (ex.: `1,50`). Vazia = mantém a taxa de cada contrato.
- **Dias para pagamento.** Vazio = mantém. Só vale para planos que já existem (ver abaixo).
- **Periodicidade:** `DIÁRIA`, `SEMANAL`, `MENSAL` ou `QUINZENAL`.
  - Nas três que não são semanais: **Dia 1** e **Dia 2** (vazio ou 0 = mantém o dia do plano).
  - Na semanal: os **dias da semana** e o **tipo de dia** (`INDIFERENTE`, `PAR`, `ÍMPAR`). Nenhum dia marcado = mantém os do plano.
- **Bancarizar:** `SIM` ou `NÃO`.

Para cada credenciado, em **todos os contratos**:

1. Pesquisa e confere o credenciado (lista de resultados ou outro credenciado = erro, nada alterado).
2. Contrato **BLOQUEADO** é pulado.
3. Com plano de compra, altera o primeiro da lista; sem plano, clica em **Novo** e cria um **A VISTA**.
4. Preenche os campos na ordem da versão Selenium. Cada um é **conferido**: se a lista ou o campo não ficar com o valor, tenta pelo `apex.item().setValue()`; se ainda assim não ficar, nada é salvo. Logo antes de salvar, todos são conferidos de novo, porque um campo em cascata pode apagar outro.
5. Salva. O plano existente, pelo primeiro botão do cabeçalho, como no Selenium, mas só se o texto dele não for de excluir, cancelar ou voltar. O plano novo, pelo **OK**.
6. Se o contrato ficar em **DEFINIÇÃO**, aprova (Opções > Aprovar) e confere se ficou APROVADO. Se continuar APROVADO, o plano não mudou e não precisa aprovar.

**Planilha:** uma linha por credenciado, com as mesmas colunas do painel Selenium: `COD`, `TAXA`, `PERIODICIDADE`, `PAG`, `DIA1`, `DIA2`, `BANCARIZAR`, `TIPO_DIA` e os dias da semana em `DIAS_SEMANA` (`SEGUNDA;QUINTA`) ou `DIA_SEM1` a `DIA_SEM7`. Célula vazia ou coluna ausente usa o valor da tela, como no ativador. Um valor inválido recusa a planilha inteira, com o número da linha. O botão **Baixar modelo** (`/taxas/modelo-planilha`) entrega a planilha com listas de valores e instruções.

**Relatório** `relatorios/taxa_*.xlsx`, com **uma linha por contrato**, regravado a cada contrato. Colunas:

- `CREDENCIADO`, `FANTASIA`, `CONTRATO`, `PRODUTO`;
- `ESTADO_ANTES`;
- `PLANO` (`Alterado`, `Criado`, `—` ou "... não concluída");
- `APROVADO_PELO_ROBO`;
- `PEDIDO` (resumo do plano pedido);
- `RESULTADO` (`OK`, `Pulado: contrato BLOQUEADO`, `AVISO: ...` ou `ERRO: ...`).

Diferenças em relação à versão Selenium:

- **Um erro não para a planilha inteira.** No Selenium, o primeiro erro encerrava tudo. Agora:
  - um erro num contrato encerra **aquele credenciado**, e os contratos seguintes dele não são mexidos (o relatório diz quantos);
  - a execução segue para o próximo credenciado;
  - se **3 credenciados seguidos** derem erro depois de abertos, ela para sozinha, porque isso indica um problema geral (portal fora, tela mudou). Credenciado não encontrado não conta.
- **Dias para pagamento em branco não grava 0.** O Selenium gravava 0 quando a coluna `PAG` estava vazia; agora mantém o valor do plano. **No plano novo, os dias para pagamento continuam sem ser preenchidos, como no Selenium**, e o relatório avisa em cada plano criado (pendente de confirmação com o negócio).
- **Campos conferidos.** O Selenium tinha cerca de 300 linhas de tentativas para Dia 1 e Dia 2 e, se a periodicidade estivesse vazia na planilha, escolhia a primeira opção da lista sem avisar. Agora a periodicidade nunca fica vazia (vem da tela) e cada campo é conferido.
- **Estado ilegível vira erro.** O Selenium, quando não conseguia ler o estado do contrato, supunha DEFINIÇÃO e aprovava no escuro.
- **`DIAS_SEMANA` numa coluna funciona.** No Selenium, a coluna virava `DIA_SEM1` antes de ser separada, e o valor `SEGUNDA;QUARTA` era recusado como dia inválido.
- **Pesquisa por CPF** e CNPJ normalizado como nas outras telas. O lote do Selenium completava qualquer documento com zeros até 14 dígitos.
- **Plano com mais de um:** altera o primeiro, como antes, e o relatório avisa.
- **Ficaram de fora** a execução em dois Chromes ao mesmo tempo (`iniciar_duplo`), sem tela no Selenium, e a observação na aprovação: como no Selenium, a taxa aprova sem preencher observação.

## Criação de acesso

Veio de `automacao_criacao_acesso`, um script Playwright à parte que lia `tickets.xlsx` e tinha usuário e senha escritos no código. No painel, tudo entra pelo formulário (`/acessos`):

- **Credenciais da Infox e do painel administrativo da Megavale.** Nada fica gravado no código nem em disco.
- **Criar acessos ou Somente verificar.** Para cada credenciado, lê a tela da Infox. No painel Megavale (segunda aba do mesmo Chrome), procura o **estabelecimento pelo código Infox** e o **gerente pelo e-mail**:
  - **Criar acessos** cria só o que faltar;
  - **Somente verificar** não cria nada: mostra o que já existe e quais dados estão vazios na Infox. É bom para conferir uma planilha antes de criar.
- **Um credenciado ou planilha.** A antiga `tickets.xlsx` (coluna `CODIGO`) funciona como está. O botão "Baixar modelo" entrega uma em branco.

Regras mantidas da automação original:

- O gerente entra com login = e-mail e senha = código do credenciado.
- Sem CPF do proprietário na Infox, vai `12345678910`.
- O CEP é digitado para o painel buscar o endereço. Logradouro e bairro da Infox só entram se a busca deixar o campo vazio.
- A UF e a cidade são escolhidas pelo nome. A cidade aceita nome igual ou contido.

O que muda em relação à original:

- **Relatório** `relatorios/criacao_acesso_*.xlsx`, gravado a cada credenciado. Tem as colunas `ESTABELECIMENTO` e `GERENTE` (Criado, Já existia, Erro ao criar) e `RESULTADO`. A original só imprimia no terminal.
- **Sem e-mail na Infox, nada é criado para o credenciado**, e ele vira erro para fazer manualmente. A original filtrava a lista de gerentes com o e-mail vazio, o que lista todos: o gerente era dado como "já existente" e não era criado.
- **Endereço do primeiro da lista.** Com mais de um endereço, a original lia o endereço com uma função que falha quando há mais de um resultado, e o CEP, a cidade e o bairro vinham vazios. Isso pode explicar parte dos credenciados "com CEP incorreto" que ficavam para trás.
- **Estabelecimento do gerente escolhido pelo código.** No campo de busca, entra a opção que mostra exatamente o código; se nenhuma mostrar, só aceita quando há uma única opção. A original clicava sempre na primeira, que podia ser, por exemplo, o 123456 numa busca por 12345.
- **Cadastro conferido.** Depois de salvar, o estabelecimento e o gerente precisam aparecer na lista filtrada; senão, o item vira erro. O alerta de erro do painel (bootbox) vai para o relatório.
- **Credenciado conferido na Infox,** como no ativador: se a pesquisa abrir outro credenciado ou devolver uma lista, nada é criado.
- **A cidade não perde a seleção.** A original disparava de novo o evento de troca da UF, o que recarregava a lista de cidades duas vezes; agora a cidade escolhida é conferida.

## Como migrar a próxima tela

1. Crie `automacoes/<funcionalidade>/` com uma classe que herda de `AutomacaoBase` e implementa `processar_item()`, mais `gerar_relatorio()` e `registrar_falha()` se precisar de planilha.
2. Seletores novos vão em `automacoes/core/seletores.py`. Ações de portal que mais de uma automação usa vão em `PortalInfox`.
3. Crie `rotas/<funcionalidade>.py` com uma blueprint que lê o formulário e termina com `return iniciar_e_acompanhar("<nome>", criar_automacao)` (de `rotas/execucao.py`), e registre-a em `rotas/__init__.py`.
4. Copie o template do painel Selenium, troque o `<nav class="topbar">` por `{% include "_menu.html" %}` e acrescente no `<head>` o link do `tema.css`, depois do `<style>` da página. Acrescente a tela na lista `TELAS` de `templates/_menu.html` e um cartão em `templates/index.html`.
5. Rode a mesma entrada nos dois painéis e compare os relatórios antes de aposentar a versão Selenium.

## Logs e saídas

- `logs/<id da execução>.txt` (`<automação>_<data>_<hora>`): log da execução, com os tracebacks dos erros.
- `logs/*.png`: captura da tela de cada item com erro e do primeiro aviso.
- `logs/*_trace.zip`: trace do Playwright (conforme `SALVAR_TRACE`).
- `relatorios/`:
  - `verificacao_*.xlsx` (modo verificação) e `habilitacao_*.xlsx` (antes e depois de cada contrato);
  - `extrator_cadastro_*.xlsx` e `extrator_transacoes_*.xlsx` (uma linha por credenciado pesquisado);
  - `coleta_codigo_estabelecimento_*.xlsx` (abas Resumo e Coleta, uma linha por credenciado);
  - `conciliacao_*.xlsx` (conciliação antes e depois de cada credenciado);
  - `taxa_*.xlsx` (uma linha por contrato: estado, plano alterado ou criado, aprovação e resultado);
  - `criacao_acesso_*.xlsx` (o que foi criado ou já existia para cada credenciado).

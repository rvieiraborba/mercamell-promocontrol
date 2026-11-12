# Mercamell PromoControl

Sistema local para gestão de eventos promocionais, cadastro de compradores, compras e números da sorte, com tela de apuração e exportação dos resultados.

**Versão atual:** 3.1.  **Idioma:** português brasileiro.

## Requisitos

- Python **3.9 ou superior** (sem bibliotecas externas).
- Windows, macOS ou Linux; navegador moderno.
- Funciona **localmente**, com dados em SQLite. Não há necessidade de internet para usar o sistema.

## Executar no Windows

1. Baixe ou clone este repositório.
2. Execute `TESTAR_DEMONSTRACAO_WINDOWS.bat` para testar com dados fictícios.
3. Execute `INICIAR_WINDOWS.bat` para o ambiente real.
4. Abra no navegador o endereço indicado pelo programa, se ele não abrir automaticamente.

## Executar no macOS/Linux

```bash
python3 app.py --demo  # demonstração
python3 app.py         # ambiente real
```

O ambiente real usa `127.0.0.1:8767`, e o de demonstração `127.0.0.1:8768`.

## Testes automatizados

```bash
python test_app.py
```

## Funcionalidades

- Eventos independentes, com faixas de compras e prêmios configuráveis.
- Compradores: nome, telefone (opcional), apartamento e observações.
- Compras acumuladas por pessoa com código automático por evento (`001-000001`, `001-000002`, `002-000001`), ID externo opcional e prevenção de duplicatas.
- Números exclusivos, bônus para produtos participantes e limite por pessoa.
- Fechamento de cadastros e apuração com contagem regressiva e som opcional.
- Confirmação ou novo sorteio do prêmio, excluindo participantes já premiados.
- Fotos opcionais dos prêmios (selecionadas pelo operador, salvas localmente e incluídas no backup).
- Exportação de imagem final PNG com prêmio, foto opcional, nome, apartamento e número sorteado.
- Gravação opcional da aba/tela do sorteio em vídeo WebM pelo navegador, com autorização explícita do usuário.
- Cancelamento de apuração com reabertura de cadastros **sem apagar compras ou participantes**.
- Backups JSON e exportação de relatórios.

## Estrutura

```text
app.py                         Backend e armazenamento SQLite
index.html                     Interface principal
static/                        JavaScript, estilos e identidade visual
test_app.py                    Testes automatizados
INICIAR_WINDOWS.bat            Início da base real
TESTAR_DEMONSTRACAO_WINDOWS.bat Início da base fictícia
dados/                         Bancos locais (ignorados pelo Git)
```

## Atualização da versão 3.0 para 3.1

1. Na versão **3.0**, em **Backup**, exporte um JSON completo e guarde-o em local seguro, fora da pasta do programa.
2. Feche a janela do programa da versão antiga.
3. Extraia o ZIP **3.1** em uma pasta nova. **Não apague a pasta anterior**.
4. Copie os arquivos `.db` de `dados/` da versão antiga para a pasta `dados/` da 3.1 (ou use **Backup > Restaurar**, que **substitui** a base atual).
5. Execute `TESTAR_DEMONSTRACAO_WINDOWS.bat` para testar com dados fictícios; depois `INICIAR_WINDOWS.bat` para os dados reais. A sequência das compras antigas será atribuída pela ordem dos registros.
6. Confira a quantidade de compras, os participantes, os números e os ganhadores antes de operar um evento real.

Os backups JSON das versões 2, 3 e 4 são aceitos. A versão 3.1 gera backups no **formato V4** (isso indica a estrutura do backup, não a versão comercial do sistema).

## Fotos dos prêmios

Abra um evento e vá em **Configurações > Fotos dos prêmios** para escolher uma foto JPG ou PNG por prêmio. O navegador a reduz e compacta; limite de 500 KB por foto após compactação. Você pode substituir ou remover a foto antes do encerramento do cadastro. A foto é armazenada junto dos dados locais e incluída no backup; se você mudar o nome ou a ordem de um prêmio, confira a imagem novamente.

## Gravação do sorteio

1. Na tela **Sorteios**, após encerrar os cadastros, clique em **Iniciar gravação** antes do primeiro sorteio.
2. Na janela de compartilhamento do navegador, selecione **Esta aba** e marque **Compartilhar áudio da aba**, se disponível. Chrome ou Edge atualizados são recomendados.
3. Realize a apuração inteira, incluindo contagem, resorteios e tela final.
4. Clique em **Finalizar e salvar vídeo**. Confira o arquivo **WebM** na pasta Downloads antes de fechar a janela. A gravação não é armazenada no SQLite e não entra no backup.

A gravação requer autorização explícita do navegador. O áudio depende da opção de compartilhamento e do suporte do navegador. **Teste antes do evento.** Evite fechar ou atualizar a aba enquanto grava. O arquivo de vídeo pode conter nomes e apartamentos; compartilhe-o somente com os destinatários adequados.

## Privacidade e cópias de segurança

**Não suba bancos `.db`, backups `.json`, relatórios de vendas ou listas de compradores ao GitHub.** O arquivo `.gitignore` impede a inclusão automática desses tipos de arquivo, mas sempre revise os arquivos antes de um commit. Dados reais ficam apenas no computador e devem ter cópias de segurança protegidas.

Ao atualizar para uma nova versão, faça backup antes de substituir os arquivos. Não remova o diretório `dados/` da instalação em uso.

## Limites

O GitHub serve para **versionar o código**, não para publicar a aplicação local nem hospedar o banco SQLite. O GitHub Pages sozinho não executa o backend Python.

A utilização do mecanismo de apuração deve corresponder ao regulamento autorizado do evento. O software não concede autorização legal para promoções.
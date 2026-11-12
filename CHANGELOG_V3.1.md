# Mercamell PromoControl 3.1 — versão de testes

## Melhorias

- Código automático e sequencial por evento para cada compra: `001-000001`, `001-000002`, `002-000001` etc. O ID externo é opcional e continua preservado quando fornecido.
- Compras antigas recebem o código na migração, respeitando a ordem de inserção. Compras estornadas conservam seu identificador.
- Apartamento do ganhador incluído na confirmação, no resumo, no CSV e na imagem PNG compartilhável.
- Imagens opcionais dos prêmios (JPG/PNG), selecionadas pelo operador, com pré-visualização e inclusão no backup. Fotos são removidas quando nome/posição do prêmio correspondente muda.
- Gravação da aba/tela do sorteio pelo navegador, com início e término controlados pelo operador. O arquivo WebM é baixado localmente; o áudio depende da opção de compartilhamento da aba.

## Compatibilidade

- Bases SQLite da versão 3.0 são migradas automaticamente na abertura da versão 3.1.
- Backups dos formatos anteriores V2 e V3 são aceitos; o novo formato de backup é V4.
- A gravação de vídeo não é incluída no backup JSON e não é enviada para servidores.

## Validação

- 18 testes de backend Python passaram.
- Sintaxe JavaScript e renderização dinâmica de interface verificadas em Node.js.
- API HTTP local: leitura, criação de evento, comprador e compra testadas.
- A captura de vídeo e a exportação da imagem PNG necessitam validação de ponta a ponta no navegador Windows. O navegador de validação automatizada deste ambiente bloqueou acesso ao servidor local por política administrativa.

## Recomendação antes de utilizar em outro evento

1. Exportar backup JSON na versão 3.0 e conservá-lo em lugar seguro.
2. Testar a versão 3.1 na demonstração, em pasta separada.
3. Verificar a foto de cada prêmio, a imagem PNG final e o vídeo WebM (com e sem áudio).
4. Validar números da sorte, códigos das compras e comparação de participantes/valores com a base anterior antes de usar a base real.
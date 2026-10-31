# Mercamell PromoControl

Sistema local para gerenciar eventos promocionais, compradores, compras, números da sorte e apuração de prêmios.

**Versão inicial:** 3.0 • **Idioma:** português brasileiro.

## Utilização

Requer Python 3.9 ou superior e navegador moderno.

No Windows, execute `TESTAR_DEMONSTRACAO_WINDOWS.bat` para usar dados fictícios, ou `INICIAR_WINDOWS.bat` para utilizar a base real. No macOS/Linux, execute `python3 app.py --demo` ou `python3 app.py`.

O sistema utiliza SQLite localmente, não depende de conexão à internet e disponibiliza interface pelo navegador em `127.0.0.1`.

## Funcionalidades

- Vários eventos, com regras, faixas e prêmios configuráveis.
- Cadastro de compradores, apartamento, observações, compras e ID de transação.
- Números exclusivos e limite por participante.
- Contagem regressiva, som opcional, confirmação e novo sorteio.
- Exclusão de números da pessoa contemplada nos prêmios seguintes.
- Exportação em PNG dos ganhadores.
- Cancelamento da apuração e reabertura dos cadastros sem apagar as compras.
- Backups JSON e exportação de relatórios.

## Testes

```bash
python test_app.py
```

## Privacidade

Nunca publique o diretório de dados com cadastros reais, arquivos SQLite, exportações ou backups. O código utiliza um arquivo `.gitignore` para evitar o versionamento acidental desses dados.

**Atenção:** O mecanismo de apuração deve estar de acordo com o regulamento autorizado do evento. O sistema não substitui autorizações legais.

Código-fonte e instruções serão mantidos neste repositório para as próximas versões.
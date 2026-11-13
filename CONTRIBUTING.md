# Fluxo de desenvolvimento

Este projeto pertence exclusivamente à conta pessoal `rvieiraborba`.
Não usar a conta profissional `rafael-borba_LGGIT`.

## Branches e destinos dos PRs

| Branch | Origem | Destino | Uso |
| --- | --- | --- | --- |
| main | — | — | Código final homologado; permanece como branch padrão |
| develop | main na criação inicial | main | Integração e testes da próxima entrega |
| feature/descricao-curta | develop atualizada | develop | Nova funcionalidade ou melhoria |
| fix/descricao-curta | develop atualizada | develop | Correção comum |
| hotfix/descricao-curta | main atualizada | main | Correção urgente de produção |

Criar uma branch por mudança concreta, em minúsculas, sem acentos e com hífens.
Não criar branches vazias para correções futuras. A configuração inicial usa
`feature/configurar-workflow-github`, pois representa uma melhoria real.

## Trabalho diário

```sh
git switch develop
git pull --ff-only origin develop
git switch -c fix/descricao-da-correcao
# implementar e validar a mudança
git add caminho/do/arquivo
git commit -m "fix: descreve a correcao"
git push -u origin fix/descricao-da-correcao
```

Abrir PR para `develop`, descrever o problema, a solução e os testes.
Usar `feat:`, `fix:`, `docs:`, `test:` ou `ci:` no título e nos commits.
Resolver discussões e aguardar todos os checks. Não fazer push direto em
`main` ou `develop`, force push ou reescrita do histórico compartilhado.

## Entrega e hotfix

Após testes e homologação, abrir PR de `develop` para `main`.
Usar merge commit nessa promoção para manter a ancestralidade entre as branches.
Registrar versão e changelog quando houver uma entrega da aplicação.
Merge no GitHub não atualiza automaticamente a instalação local em produção.

Para hotfix, criar a branch a partir de `main`, validar e abrir PR para `main`.
Após o merge, abrir PR de `main` para `develop` com merge commit, preservando
a correção na próxima entrega. Resolver conflitos na branch de trabalho,
sem sobrescrever as branches permanentes.
Squash é apropriado para PRs curtos de feature/fix; não usar squash na
sincronização entre `main` e `develop`.
Excluir apenas branches temporárias já integradas; nunca excluir `develop`.

## Validação

O workflow `Testes Python` executa `python test_app.py` com Python 3.12,
além de verificar a sintaxe Python e dos arquivos JavaScript.
PRs destinados a `main` e `develop` executam o CI; pushes nas branches de
trabalho também são verificados. O CI não faz deploy e não usa dados reais.
A validação automatizada não substitui homologação no navegador, em especial
fotos, exportações e gravação de tela. A suíte E2E fica no repositório separado.

Nunca versionar bancos SQLite, backups de produção, dados pessoais ou segredos.
Usar dados fictícios e ambientes temporários para testes.

## Proteções a ativar pelo proprietário

**Este arquivo documenta a configuração; não ativa proteções no GitHub.**
Em Settings → Branches, criar uma regra exata para `main` e outra para
`develop`:

- Exigir pull request antes do merge.
- Para trabalho individual, não exigir aprovação de outra pessoa (0 aprovações).
  O autor não pode aprovar o próprio PR. Quando houver outro revisor, considerar 1.
- Exigir o check `test` do workflow `Testes Python`, após confirmar seu
  nome na execução do PR; exigir branch atualizada antes do merge.
- Exigir resolução das conversas.
- Aplicar a regra também a administradores (não permitir bypass).
- Manter force push e exclusão de branch desabilitados.

Não exigir histórico linear: as promoções e sincronizações usam merge commit.
Não adicionar checks que ainda não existam, pois isso pode bloquear merges.
Não ativar exclusão automática global de branches: um PR develop → main
não deve eliminar a branch permanente de desenvolvimento.

A conexão do aplicativo pode editar código, mas não administrar essas regras.
Verificar a proteção no GitHub após salvá-la.

Referências: [proteções de branch](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
e [aprovação de PRs](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews).

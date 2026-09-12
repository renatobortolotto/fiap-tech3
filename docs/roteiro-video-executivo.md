# Roteiro — vídeo executivo (até 5 minutos)

O edital pede uma apresentação que **simule uma reunião executiva com gestores
públicos**. Isso muda o registro: nada de "usei LightGBM com 800 árvores". A pergunta
que o gestor tem na cabeça é *"o que eu faço na segunda-feira de manhã?"*.

Os números marcados com `→` devem ser conferidos em `reports/` antes da gravação.

---

## Abertura — o problema (0:00–0:45)

> "O Brasil se comprometeu a alfabetizar 80% das crianças até o fim do 2º ano, até
> 2030. Hoje estamos em **59,8%**.
>
> Mas essa média nacional esconde o que de fato importa. Entre os municípios
> avaliados, a taxa vai de **menos de 11% a mais de 95%**. Não existe um problema de
> alfabetização no Brasil — existem milhares de problemas diferentes, e a média não
> diz a nenhum gestor o que fazer.
>
> O que trouxemos aqui não é mais um relatório do que já aconteceu. É um instrumento
> para antecipar."

**Na tela:** `images/01_distribuicao_alvo.png` e `images/06_mapa_municipios.png`.

## O que construímos (0:45–1:30)

> "Usamos os microdados de **3,3 milhões de crianças** avaliadas em 2023 e 2024 e
> cruzamos com sete bases públicas: Censo Escolar, IDEB, nível socioeconômico das
> escolas, Censo 2022, vulnerabilidade social, Cadastro Único e as contas de educação
> de cada município.
>
> O modelo foi treinado em **2023 e testado em 2024** — ou seja, ele nunca viu o ano
> em que foi avaliado. É a mesma situação de quem precisa planejar o próximo ano
> letivo hoje."

**Na tela:** `images/11_estratos_temporal.png`.

> "Uma ressalva que faço de propósito: **prever a criança individual é difícil**, e o
> modelo acerta `→ AUC 0,6X`. Isso não é modéstia — é a realidade de um dado que não
> contém nada sobre a família da criança. Mas quando agregamos por município, a coisa
> muda de figura: a previsão da taxa municipal erra, em média, `→ X,X pontos
> percentuais`. E é no município que a política acontece."

**Na tela:** `images/20_calibracao_municipal.png`.

## O que descobrimos (1:30–3:00)

> "Três achados que mudam a conversa.
>
> **Primeiro: o que mais pesa não é o equipamento da escola — é o contexto social e
> demográfico do município.** `→ citar as 2 ou 3 variáveis do topo de
> reports/interpretabilidade_temporal.md`. Municípios com muitas crianças por adulto,
> com adultos menos escolarizados e com maior vulnerabilidade social alfabetizam
> menos, mesmo quando as escolas são parecidas.
>
> **Segundo: o que acontece em um município se repete no ano seguinte — o que
> acontece em uma escola, não.** A taxa municipal de um ano prevê a do ano seguinte
> com correlação de **0,81**. Isso significa que o risco é estrutural e, portanto,
> pode ser antecipado com antecedência de um ano inteiro.
>
> **Terceiro, e o mais acionável: o ranking de risco puro é quase inútil.** Ele
> apenas lista os municípios mais pobres — algo que qualquer gestor já sabe. O que
> descobre problema de verdade é olhar **quem está indo muito pior do que o próprio
> contexto explicaria**."

**Na tela:** `images/13_ablacao_por_bloco.png`, depois `images/03_persistencia_ano_a_ano.png`.

## A recomendação (3:00–4:15)

> "É aqui que a ferramenta vira decisão.
>
> Separamos, de um lado, os municípios que vão **muito abaixo** do previsto pelas
> próprias condições — `→ citar 2 exemplos de reports/aplicacao_temporal.md`. Pobreza
> não explica o resultado deles; alguma coisa na gestão da rede explica. **São esses
> que merecem visita técnica**, não os mais pobres da lista.
>
> Do outro lado, os que vão **muito acima** — `→ citar 2 exemplos`. Com as mesmas
> condições socioeconômicas, eles entregam muito mais. **São esses que merecem ser
> estudados**, e é dali que sai política replicável.
>
> E, porque o modelo é calibrado, ele também dimensiona: quando aponta `→ N` crianças
> em risco num município, esse é o número de vagas de reforço a planejar — não uma
> estimativa de ordem de grandeza."

**Na tela:** `images/21_residuos_municipais.png` e `images/22_grupos_municipais.png`.

## Fechamento — o que isso não faz (4:15–5:00)

> "Duas honestidades para terminar.
>
> **Este modelo não serve para rotular crianças.** A previsão individual é imprecisa
> por uma razão estrutural: o dado público não sabe nada sobre a família da criança.
> Usá-lo para etiquetar um aluno produziria estigma sem informação. O uso legítimo é
> territorial.
>
> **E ele mede associação, não causa.** Que escolas com biblioteca alfabetizem mais
> não significa que construir bibliotecas alfabetize.
>
> O que ele entrega é o que faltava: uma forma de olhar para 5.500 municípios e saber
> **onde o resultado não é explicado pelas condições** — que é exatamente onde a ação
> pública tem mais a ganhar."

---

## Checagem antes de gravar

- [ ] Substituir cada `→` pelo número real dos relatórios em `reports/`
- [ ] Conferir se as figuras citadas existem em `images/`
- [ ] Cronometrar: o limite de 5 minutos é rígido
- [ ] Evitar jargão: "AUC" pode aparecer uma vez, explicado; "hiperparâmetro" e
      "target encoding", nunca
- [ ] Falar de municípios com nome, não com código IBGE

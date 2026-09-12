# Roteiro — vídeo executivo (até 5 minutos)

O edital pede uma apresentação que **simule uma reunião executiva com gestores
públicos**. Isso muda o registro: nada de "usei LightGBM com 800 árvores". A pergunta
que o gestor tem na cabeça é *"o que eu faço na segunda-feira de manhã?"*.

Todos os números abaixo já estão conferidos contra `reports/`. Os **nomes de municípios**
mudam se o modelo for retreinado — confira em `reports/aplicacao_temporal.md` antes de
gravar.

---

## Abertura — o problema (0:00–0:45)

> "O Brasil se comprometeu a alfabetizar 80% das crianças até o fim do 2º ano, até 2030.
> Hoje estamos em **59,8%**.
>
> Mas essa média nacional esconde o que de fato importa. Entre os quase cinco mil
> municípios avaliados, a taxa vai de **11% a 100%** — e um em cada dez está abaixo de
> **37%**. Não existe um problema de alfabetização no Brasil; existem milhares de
> problemas diferentes, e a média não diz a nenhum gestor o que fazer.
>
> O que trouxemos aqui não é mais um retrato do que já aconteceu. É um instrumento para
> antecipar."

**Na tela:** `images/01_distribuicao_alvo.png`, depois `images/06_mapa_municipios.png`.

## O que construímos (0:45–1:45)

> "Partimos dos microdados de **3,3 milhões de crianças** avaliadas em 2023 e 2024 e
> cruzamos com sete bases públicas: Censo Escolar, IDEB, nível socioeconômico das
> escolas, Censo 2022, vulnerabilidade social, Cadastro Único e as contas de educação de
> cada município.
>
> O modelo foi treinado em **2023 e testado em 2024** — ele nunca viu o ano em que foi
> avaliado. É exatamente a situação de quem precisa planejar o próximo ano letivo hoje.
>
> Uma ressalva que faço de propósito: **prever a criança individual é difícil**. O
> modelo tem acurácia melhor que o acaso, mas longe de um oráculo. Isso não é modéstia —
> é a realidade de um dado que não contém **nada** sobre a família de cada criança.
>
> Mas a decisão pública não é sobre uma criança: é sobre uma rede. E aí a coisa muda de
> figura. A previsão da **taxa municipal** correlaciona **0,71** com o que de fato
> aconteceu. Ela erra em média 10 pontos percentuais — então a leitura certa é por
> faixa, não por ponto. E é no município que a política acontece."

**Na tela:** `images/20_calibracao_municipal_temporal.png`.

## O que descobrimos (1:45–3:00)

> "Três achados que mudam a conversa.
>
> **Primeiro: o que mais pesa não é o equipamento da escola — é o contexto social e
> demográfico do município.** A cobertura do Bolsa Família, o índice de vulnerabilidade
> social e a proporção de crianças de 5 a 9 anos pesam **três vezes mais que o PIB per
> capita**. Municípios com muitas crianças por adulto têm redes sob pressão, e isso
> aparece no resultado.
>
> **Segundo: o que acontece num município se repete no ano seguinte.** A taxa municipal
> de um ano prevê a do ano seguinte com correlação de **0,81**. O risco é estrutural — e
> por isso pode ser antecipado com um ano inteiro de antecedência.
>
> **Terceiro, e o mais acionável: o ranking de risco puro é quase inútil.** Ele apenas
> lista os municípios mais pobres, que é o que qualquer gestor já sabe. O que descobre
> problema de verdade é olhar **quem está indo muito pior do que o próprio contexto e o
> próprio estado explicariam**."

**Na tela:** `images/13_ablacao_por_bloco.png`, depois `images/03_persistencia_ano_a_ano.png`.

## A recomendação (3:00–4:15)

> "É aqui que a ferramenta vira decisão.
>
> De um lado, os municípios que vão **muito abaixo** do previsto pelas próprias
> condições e pelos vizinhos de estado — Anapurus, no Maranhão, quase **50 pontos**
> abaixo do esperado; Uiraúna, na Paraíba, praticamente o mesmo. Pobreza não explica o
> resultado deles. **São esses que merecem visita técnica** — não os mais pobres da
> lista.
>
> Do outro lado, os que vão **muito acima**, com as mesmas condições socioeconômicas.
> **São esses que merecem ser estudados**, e é dali que sai política replicável.
>
> E o modelo agrupa os municípios em **cinco perfis de contexto**, para que a comparação
> seja sempre entre pares — e não contra uma média nacional que não existe em lugar
> nenhum. O grupo mais frágil não é simplesmente o mais pobre: é o de maior pressão
> demográfica e menor conectividade pedagógica."

**Na tela:** `images/21_residuos_municipais_temporal.png` e
`images/22_grupos_municipais_temporal.png`.

## Fechamento — o que isso não faz (4:15–5:00)

> "Três honestidades para terminar.
>
> **Este modelo não serve para rotular crianças.** A previsão individual é imprecisa por
> uma razão estrutural, e usá-la para etiquetar um aluno produziria estigma sem
> informação. O uso legítimo é territorial e agregado.
>
> **Ele mede associação, não causa.** Que escolas com biblioteca alfabetizem mais não
> significa que construir bibliotecas alfabetize.
>
> **E ele não transfere para onde nunca esteve.** Nos três estados que entraram na base
> só em 2024, a vantagem do modelo sobre o acaso cai a **um terço**. Ele é confiável
> onde há histórico — e isso, por si só, é um argumento para manter a avaliação anual.
>
> O que ele entrega é o que faltava: uma forma de olhar para cinco mil e quinhentos
> municípios e saber **onde o resultado não é explicado pelas condições** — que é
> exatamente onde a ação pública tem mais a ganhar."

---

## Checagem antes de gravar

- [ ] Rodar `make tudo` e conferir que as figuras citadas existem em `images/`
- [ ] Conferir os nomes dos municípios em `reports/aplicacao_temporal.md`
- [ ] Cronometrar: o limite de 5 minutos é rígido
- [ ] Evitar jargão — "AUC", "hiperparâmetro" e "target encoding" não aparecem no texto
      acima de propósito
- [ ] Falar de municípios com nome, não com código IBGE

# PhotoSieve

Ferramenta de linha de comando para encontrar fotos **duplicadas** e
**visualmente semelhantes**, e opcionalmente limpar as duplicatas exatas
com segurança.

## Instalação

Requer Python 3.12 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"      # ou: pip install -r requirements.txt
```

`requirements-lock.txt` contém as versões exatas testadas.

**HEIC/HEIF (fotos de iPhone)** é opcional: `pip install -e ".[heic]"`
(instala `pillow-heif`). Sem ele, arquivos `.heic`/`.heif` são ignorados.

## Comandos

| Comando | O que faz |
|---|---|
| `photosieve scan DIR` | Inventário das imagens (formato, dimensões, tamanho) |
| `photosieve duplicates DIR` | Duplicatas **exatas** (SHA-256) |
| `photosieve similar DIR [--threshold 0-64]` | Agrupa imagens semelhantes por pHash (complete-link, com índice BK-Tree) |
| `photosieve analyze DIR [opções]` | Análise híbrida completa (recomendada) |
| `photosieve dedupe DIR [opções]` | Move ou exclui duplicatas, mantendo uma cópia |

Os comandos `scan`, `duplicates`, `similar` e `analyze` **nunca alteram arquivos**.

### Opções do `analyze`

| Opção | Descrição |
|---|---|
| `--phash-threshold 0-64` | Distância pHash máxima para formar pares candidatos (padrão 12) |
| `--minimum-score 0-1` | Pontuação híbrida mínima (padrão 0,70) |
| `--workers N` | Threads paralelas (padrão 4) |
| `--report ARQ` | Exporta o resultado; o formato vem da extensão: `.json`, `.csv` ou `.html` |
| `--detect-crops` | Também detecta imagens que são **recortes** de outras (mais lento) |
| `--crop-threshold 0-64` | Sensibilidade da detecção de recortes (padrão 8) |
| `--detect-transforms` | Também detecta cópias **giradas** (90/180/270) e **espelhadas** |
| `--cache-db ARQ` / `--no-cache` | Cache SQLite (padrão `~/.cache/photosieve/cache.db`) ou desativá-lo |

### Cache persistente

Os resultados de análise (SHA-256, pHash, histograma, metadados, janelas de
recorte) ficam em um banco SQLite, indexados por *caminho + tamanho + mtime*.
Se um arquivo mudar, a entrada antiga deixa de valer automaticamente. Em
`~/Pictures` (37 fotos): 4,4 s na primeira execução e 0,6 s na segunda.

### Relatórios (`--report`)

- **JSON**: estrutura completa (resumo, grupos, pares, erros, parâmetros).
- **CSV**: uma linha por par/duplicata; células que começam com `=`, `+`, `-`
  ou `@` são neutralizadas contra *formula injection* em planilhas.
- **HTML**: autocontido, com miniaturas lado a lado, destaque da cópia sugerida
  (`manter`) e marcação de pares detectados como recorte. Todo nome de arquivo é escapado.

### Limpeza segura (`dedupe`)

- **Padrão: dry-run.** Sem `--apply`, apenas o plano é exibido.
- **Padrão: quarentena.** Arquivos são *movidos* para uma pasta irmã
  `<DIR>_photosieve_duplicates` (reversível). A exclusão definitiva exige
  `--delete` e confirmação interativa (ou `--yes`).
- Sempre resta uma cópia por grupo. O SHA-256 (exatas) ou o tamanho (semelhantes)
  é **reverificado** imediatamente antes de cada ação; se o arquivo mudou, a ação
  é ignorada e registrada como falha. Nunca sobrescreve um destino existente.

```bash
photosieve dedupe ~/Fotos                  # plano para duplicatas exatas
photosieve dedupe ~/Fotos --apply          # move para a quarentena
photosieve dedupe ~/Fotos --delete --apply # exclui (pede confirmação)
```

**Imagens semelhantes (`--similar`)**: além das exatas, coloca em quarentena
as semelhantes com pontuação ≥ `--similar-min-score` (padrão 0,90), mantendo a
de **maior qualidade** (maior resolução, depois maior arquivo). Regras extras:

- **Nunca** é combinável com `--delete` (só quarentena).
- O agrupamento é em estrela: uma imagem só é removida se tiver um par *direto*
  com a mantida, o que evita encadear A≈B≈C. Uma imagem já destinada à
  quarentena nunca atua como representante de outra.
- Pares detectados como **recorte** nunca entram no plano (ver "Detecção de recortes"); só os demais são movidos.
- Aceita `--detect-crops`, `--detect-transforms`, `--phash-threshold`, `--workers` e as opções de cache.

```bash
photosieve dedupe ~/Fotos --similar                  # revisar o plano
photosieve dedupe ~/Fotos --similar --apply
```

## Como funciona a análise híbrida

1. **SHA-256** e **pHash** são calculados em paralelo, com cache compartilhado.
2. Uma **BK-Tree** gera pares candidatos com distância de Hamming ≤ `--phash-threshold`
   (evita comparar todos contra todos). Duplicatas exatas sempre entram.
3. Cada par recebe uma pontuação: `0,55·pHash + 0,35·histograma HSV + 0,10·aspect ratio`.
4. Classificação: `VERY_HIGH` (≥ 0,95), `HIGH` (≥ 0,85), `POSSIBLE` (≥ 0,70).

## Detecção de recortes (`--detect-crops`)

Para cada imagem são calculados pHashes de 204 janelas internas (grade 5×5 em 6
escalas com proporção preservada, mais 6 formatos de proporção livre em grade 3×3). Se o pHash global de uma imagem é próximo ao de uma janela de outra,
o par é candidato; a pontuação usa a distância da janela mais uma penalidade.

Medido com recortes aleatórios (escala 65–90%) de 8 fotos reais, limiar padrão 8
(10 recortes por foto, proporção **livre**, o caso comum):

| Conjunto de janelas | Janelas | Detectados |
|---|---|---|
| Só proporção preservada (anterior) | 150 | 47/80 (59%) |
| Com formatos livres (atual) | 204 | 55/80 (69%) |
| Mais formatos/posições (descartado, custo > 2×) | 342 | 59/80 (74%) |

- Aumentar `--crop-threshold` melhora o recall, mas também o risco de falsos
  positivos. No benchmark sintético (500 imagens) houve 0 falsos positivos nos
  limiares 8, 10 e 12. Em uma biblioteca real de 315 fotos
  (com muitas rajadas), porém, **a maioria dos pares marcados como recorte eram
  fotos diferentes da mesma cena/pose**, conferidas visualmente em amostra: o
  filtro por janela é permissivo. Por isso `dedupe --similar` **ignora** pares de
  recorte; use `analyze --report arquivo.html` e revise manualmente.
- É mais lento e usa mais memória (centenas de hashes por imagem); o cache
  persistente evita recalcular. Para bibliotecas muito grandes, prefira
  executar sem `--detect-crops` primeiro.
- Amostra pequena (4 fotos, 40 recortes): trate os percentuais como indicativos.

## Limitações conhecidas

Variantes de 4 fotos reais (metade do tamanho com JPEG q70 e brilho +15%) foram
detectadas em 12/12 pares **sem** a detecção de recortes.

- Sem `--detect-crops`, recortes **não** são detectados (o pHash global muda muito).
- A pontuação sozinha não separa bem fotos diferentes com cores e proporção
  parecidas; é o filtro de pHash que evita falsos positivos.
- O benchmark sintético (`data/benchmark_500`, F1 = 1,0) é fácil e **não**
  representa fotos reais; ele não contém recortes.
- Rotações e espelhamentos só são detectados com `--detect-transforms` (0 falsos
  positivos em 315 fotos reais; custo: 7 pHashes extras por imagem).
- Ângulos de rotação arbitrários (ex.: 15°) não são tratados.
- Recortes: ver a ressalva sobre falsos positivos acima.
- O suporte a HEIC foi testado com `pillow-heif` 1.8.1 em Linux.

## Benchmark sintético

```bash
python scripts/generate_benchmark_dataset.py data/benchmark_500
python scripts/evaluate_benchmark.py --dataset data/benchmark_500
```

O dataset é gerado de forma determinística (semente 42) e por isso não é
versionado (`.gitignore`). O relatório fica em `reports/benchmark_evaluation.json`.

## Desenvolvimento

```bash
pytest --cov=photosieve --cov-report=term-missing
ruff check .
```

## Estrutura

```
src/photosieve/
├── main.py              # CLI (argparse)
├── reporter.py          # formatação da saída
├── scanner.py           # varredura e validação de imagens
├── hasher.py            # SHA-256 incremental
├── image_analyzer.py    # pHash, janelas (recortes) e variantes (rotação/espelho)
├── duplicate_detector.py
├── similarity_detector.py
├── formats.py           # suporte opcional a HEIC/HEIF
├── report_exporter.py   # relatórios JSON/CSV/HTML
├── file_manager.py      # plano e execução de mover/excluir (exatas e semelhantes)
└── comparison/          # análise híbrida (BK-Tree, cache em memória e SQLite,
                         #  cor, metadados, recortes, rotações)
```

## Licença

MIT.

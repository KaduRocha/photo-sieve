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

## Comandos

| Comando | O que faz |
|---|---|
| `photosieve scan DIR` | Inventário das imagens (formato, dimensões, tamanho) |
| `photosieve duplicates DIR` | Duplicatas **exatas** (SHA-256) |
| `photosieve similar DIR [--threshold 0-64]` | Agrupa imagens semelhantes por pHash (complete-link, O(n²)) |
| `photosieve analyze DIR [--phash-threshold 0-64] [--minimum-score 0-1] [--workers N]` | Análise híbrida completa (recomendada) |
| `photosieve dedupe DIR [--quarantine-dir D] [--delete] [--apply] [--yes]` | Move ou exclui duplicatas exatas, mantendo uma cópia |

Os comandos `scan`, `duplicates`, `similar` e `analyze` **nunca alteram arquivos**.

### Limpeza segura (`dedupe`)

- **Padrão: dry-run.** Sem `--apply`, apenas o plano é exibido.
- **Padrão: quarentena.** Duplicatas são *movidas* para uma pasta irmã
  `<DIR>_photosieve_duplicates` (reversível). A exclusão definitiva exige
  `--delete` e confirmação interativa (ou `--yes`).
- Apenas duplicatas **exatas** são tratadas; sempre resta uma cópia por grupo
  (a de caminho mais curto).
- O SHA-256 é **reverificado** imediatamente antes de cada ação. Se um arquivo
  mudou desde a varredura, a ação é ignorada e registrada como falha.
- Nunca sobrescreve um destino existente.

```bash
photosieve dedupe ~/Fotos                 # mostra o plano
photosieve dedupe ~/Fotos --apply         # move para a quarentena
photosieve dedupe ~/Fotos --delete --apply
```

## Como funciona a análise híbrida

1. **SHA-256** e **pHash** são calculados em paralelo, com cache compartilhado.
2. Uma **BK-Tree** gera pares candidatos com distância de Hamming ≤ `--phash-threshold`
   (evita comparar todos contra todos). Duplicatas exatas sempre entram.
3. Cada par recebe uma pontuação: `0,55·pHash + 0,35·histograma HSV + 0,10·aspect ratio`.
4. Classificação: `VERY_HIGH` (≥ 0,95), `HIGH` (≥ 0,85), `POSSIBLE` (≥ 0,70).

## Limitações conhecidas

Validado com variantes geradas a partir de fotos reais (4 fotos × original,
metade do tamanho com JPEG q70, brilho +15% e recorte de 20%):

- **Detectados:** redimensionamento, recompressão e variação de brilho (12/12 pares).
- **Não detectados:** **recortes (crop)**. O pHash é global e muda muito quando
  as bordas são cortadas, então esses pares são descartados na etapa de
  candidatos (distância pHash de 22 a 28, contra o limite padrão de 12).
  Aumentar `--phash-threshold` aumenta o recall, mas também os falsos positivos.
- A pontuação sozinha não separa bem fotos diferentes com cores e proporção
  parecidas; é o filtro de pHash que evita falsos positivos.
- O benchmark sintético (`data/benchmark_500`, F1 = 1,0) é fácil e **não** representa
  fotos reais.
- Rotações e espelhamentos (além da orientação EXIF) não são tratados.

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
├── image_analyzer.py    # pHash
├── duplicate_detector.py
├── similarity_detector.py
├── file_manager.py      # plano e execução de mover/excluir duplicatas
└── comparison/          # análise híbrida (BK-Tree, cache, cor, metadados)
```

## Licença

MIT.

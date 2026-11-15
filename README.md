# Entrenador Cangur: un copilot de matemàtiques a l'Arduino UNO Q

Projecte per al repte de Qualcomm *Math on the Edge* del Datathon FME 2026 (UPC).

Un estudiant resol problemes del Cangur en català en una web servida per la placa. Si encerta, la matriu LED mostra ✓ i el següent problema és un nivell més difícil. Si falla, mostra ✗, li ensenya una **pista** (un problema semblant, més fàcil i ja resolt) i el següent problema és un nivell més fàcil. Tot funciona a la placa, sense internet.

A més, `predict.py` respon problemes tipus Cangur amb una lletra (A–E) amb un model de llenguatge petit que corre a la placa.

> 📹 *Vídeo de la demo: pendent d'afegir.*

La guia original del repte és a [GUIA_REPTE.md](GUIA_REPTE.md).

## Com funciona

### Teaching: l'entrenador adaptatiu

```
 Navegador (mòbil o portàtil)
        │  http://<ip-de-la-placa>:7000
        ▼
 ┌──────────── Linux (Qualcomm QRB2210) ────────────┐
 │  App d'App Lab  (applab/cangur-trainer)          │
 │   ├─ web_ui: la pàgina web i l'API              │
 │   ├─ trainer/: corregeix, puja/baixa de nivell,  │
 │   │            tria la pista i el problema nou   │
 │   ├─ index.db: embeddings bge-small de tots els  │
 │   │            problemes (fets un sol cop)       │
 │   └─ students.db: el progrés de cada estudiant   │
 └───────────────┬──────────────────────────────────┘
                 │  Bridge
 ┌───────────────▼──────── Microcontrolador (STM32) ┐
 │  sketch.ino: dibuixa a la matriu LED 8×13        │
 │  ? en espera · ✓ / ✗ durant 1,5 s · el nivell    │
 └──────────────────────────────────────────────────┘
```

L'entrenador **no fa servir el model de llenguatge** mentre l'estudiant practica: cada pas triga uns 10 ms.

Com fa servir M3Kang:

| Què | Per a què |
| --- | --- |
| El nivell de cada problema (0 = 5è de primària, 7 = batxillerat) | Triar la dificultat del problema següent |
| Embeddings del text en anglès (bge-small-en-v1.5) | Trobar problemes del mateix tema per a la pista i el problema següent |
| Les traduccions (mateix `id`) | L'estudiant ho veu en català; la cerca es fa amb l'anglès |
| Els problemes repetits entre nivells | Es descarten com a pista, perquè regalarien la resposta |

Sense l'índex d'embeddings, l'entrenador busca problemes semblants per paraules compartides (TF-IDF).

### Reasoning: `predict.py`

El model és Qwen3.5 0.8B (Q8_0) amb llama.cpp, com a servei a la placa (port 8081). Per a cada problema rep l'enunciat i les opcions A–E llegides de la imatge amb OCR, i respon una lletra.

El model té una forta preferència per una lletra: a la primera prova va respondre B en 39 de 50 problemes. Per corregir-ho (`copilot/calibration.py`, `calibrate.py`):

1. Li demanem la probabilitat de cada lletra en lloc de quedar-nos amb la que diu.
2. Amb problemes d'entrenament mesurem quina probabilitat dona de mitjana a cada lletra (la seva preferència).
3. A cada problema restem aquesta preferència i hi sumem la freqüència real de cada lletra a M3Kang. Un pes, triat també amb problemes d'entrenament, decideix quant ens refiem del model.

Es calibra per separat per als problemes amb opcions i sense. Si no hi ha `copilot/calibration.json`, o amb `CALIBRATION=0`, el model respon com abans.

## Com replicar-ho

Partiu d'una placa preparada amb els passos 0 a 10 de la [guia del repte](GUIA_REPTE.md): llama.cpp compilat, els dos models a `~/models`, els serveis `math-llm` (8081) i `math-embed` (8082) actius, aquest repositori a `~/Datathon`, i `data/train.jsonl`, `data/val.jsonl` i `data/images` preparats al portàtil i copiats a la placa. Les dades de M3Kang no són al repositori: s'han de generar amb `laptop/prepare_m3kang.py`.

### L'entrenador, a la placa

```bash
cd ~/Datathon
cat data/train.jsonl data/val.jsonl > data/all.jsonl
python3 build_index.py --input data/all.jsonl --db data/trainer_index.db --languages eng   # uns 10 min
bash applab/install.sh
arduino-app-cli app start user:cangur-trainer
```

`install.sh` ha de dir `Similar problems: embeddings (data/trainer_index.db)`. Els registres (`arduino-app-cli app logs ~/ArduinoApps/cangur-trainer --all`) han de dir `1747 problems, levels [0, …, 7], similarity: embeddings from …`. Obriu `http://<ip-de-la-placa>:7000`; la matriu ha de mostrar `?`.

Si la placa es reinicia, l'app no arrenca sola: torneu a executar `arduino-app-cli app start user:cangur-trainer`.

Més detalls a [trainer/README.md](trainer/README.md).

### La correcció de lletra, a la placa

```bash
python3 calibrate.py --input data/train.jsonl --limit 100    # uns 15 min, escriu copilot/calibration.json
python3 eval.py --limit 50 --name calibrat                   # mesura sobre validació
```

`calibrate.py` només fa servir problemes d'entrenament, de manera que `eval.py` sobre validació continua sent una mesura honesta.

## Resultats

### Reasoning

Sobre 50 problemes de validació de M3Kang, a la placa. **En aquestes proves cap problema tenia les opcions en text** (les dades eren sense OCR), així que el model només veia l'enunciat:

| Experiment | Encerts | Temps mitjà | Temps màxim | Problemes |
| --- | --- | --- | --- | --- |
| Baseline | 15/50 = 30,0 % | 8,7 s | 15,1 s | 50 |
| Amb correcció de lletra | 10/50 = 20,0 % | 8,8 s | 15,2 s | 50 |

- El 30 % del baseline és en bona part sort: el model va respondre B 39 vegades, i en aquesta mostra la B era la correcta 16 vegades (32 %).
- Amb la correcció, les respostes queden repartides (A 5, B 7, C 6, D 25, E 7), però sense opcions el model no té informació i encerta com a l'atzar (20 %).
- Sobre 95 problemes d'entrenament sense opcions: 17,9 % sense corregir i 29,5 % corregit (optimista, perquè és la mateixa mostra amb què s'ajusta).
- Amb 50 problemes, una diferència de 5 encerts pot ser casualitat.

*Pendent: els resultats amb les opcions llegides per OCR i sobre el set de pràctica dels organitzadors.*

### Teaching

- **Temps per pas:** uns 10 ms.
- **Índex d'embeddings:** 1.747 problemes en 541 s a la placa (3,2 problemes/s), 3,7 MB.
- **Estudiants simulats** (`python3 -m trainer.simulate`): un estudiant que sap fins al nivell *t* acaba oscil·lant entre *t-1* i *t*. Amb respostes a l'atzar puja massa ràpid, perquè un sol encert per casualitat ja el fa pujar.
- **Qualitat de les pistes:** en una revisió preliminar de 20 pistes triades per paraules compartides (TF-IDF), les 20 eren més fàcils, i 9 eren del mateix tema (3 a mitges, 7 no). Les que fallaven compartien una paraula sense compartir les matemàtiques («corda», «pont», «ciutat»). *Pendent: repetir-la amb embeddings.*

## Anàlisi d'errors (Reasoning, baseline sense opcions, 50 problemes)

| Idioma | Encerts |
| --- | --- |
| Català | 10/28 = 35,7 % |
| Anglès | 5/22 = 22,7 % |

| Nivell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Encerts | 1/1 | 0/2 | 0/3 | 0/3 | 5/14 | 4/11 | 3/8 | 2/8 |

Amb tan pocs problemes per grup, aquestes diferències no són significatives. No hem fet encara l'anàlisi per tema.

## Problemes que vam trobar

- **La placa es reiniciava sola** sota càrrega (compilant llama.cpp), alimentada per l'USB del portàtil i, menys sovint, amb un carregador de 120 W. Un reinici a mitja compilació deixava fitxers `.o` buits que trencaven l'enllaçat: calia esborrar-los i recompilar.
- **L'app d'App Lab no compilava** el sketch: faltaven les llibreries `MsgPack`, `DebugLog`, `ArxContainer` i `ArxTypeTraits` a `sketch.yaml`.
- **La versió d'`arduino.app_utils` de la placa no tenia `Frame`**: enviem directament els bytes de la matriu amb `grid.tobytes()`.
- **L'OCR de les opcions és lent** al portàtil (uns 12 problemes per minut).

## Què faríem després

- Calibrar i mesurar amb les opcions llegides per OCR, i amb més de 50 problemes.
- Provar un model més gran (Qwen3.5 2B) si respon en menys de 60 s.
- Afegir un problema semblant ja resolt com a exemple al prompt (`--rag 1`).
- A l'entrenador: demanar dos encerts seguits per pujar de nivell, i validar les pistes amb embeddings.

## Dades i crèdits

- Dataset: [M3Kang](https://huggingface.co/datasets/qualcomm/M3Kang) (Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218)), d'ús només per a recerca. No és en aquest repositori.
- Codi base del repte: [mpous/datathon-UPC-maths-qualcomm-arduino-unoq](https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq).
- Models: Qwen3.5 0.8B i bge-small-en-v1.5, amb [llama.cpp](https://github.com/ggml-org/llama.cpp).

## Equip

*Pendent: noms de l'equip.*

# Retrieval evaluation: baseline

- Date: 2026-10-07
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Corpus: 3 documents, 9 pages, 9 chunks (`evaluation/retrieval_dataset.json`)
- k = 4; distance = cosine distance (0 = identical direction, 1 = unrelated)

## Summary

| Metric | Value |
| --- | --- |
| Answerable questions | 12 |
| Hit@1 (expected page ranked first) | 100% |
| Hit@4 (expected page in top 4) | 100% |
| Mean reciprocal rank | 1.00 |
| Best distance, answerable (min / median / max) | 0.230 / 0.361 / 0.552 |
| Best distance, unanswerable (min / median / max) | 0.771 / 0.887 / 0.901 |

## Per question

| ID | Type | Question | Expected | Rank | Top result (distance) |
| --- | --- | --- | --- | --- | --- |
| q01 | direct | What does a supervised model learn from? | ml_handbook.pdf p.1 | 1 | ml_handbook.pdf p.1 (0.230) |
| q02 | direct | How can I stop my model from overfitting? | ml_handbook.pdf p.2 | 1 | ml_handbook.pdf p.2 (0.302) |
| q03 | direct | How are the weights of a neural network updated? | ml_handbook.pdf p.3 | 1 | ml_handbook.pdf p.3 (0.296) |
| q04 | direct | How long should bread dough rise? | kitchen_notes.pdf p.1 | 1 | kitchen_notes.pdf p.1 (0.366) |
| q05 | paraphrase | How do I avoid spreading germs when preparing raw chicken? | kitchen_notes.pdf p.2 | 1 | kitchen_notes.pdf p.2 (0.366) |
| q06 | direct | Why did my mayonnaise split? | kitchen_notes.pdf p.3 | 1 | kitchen_notes.pdf p.3 (0.552) |
| q07 | direct | What is the difference between TCP and UDP? | network_guide.pdf p.1 | 1 | network_guide.pdf p.1 (0.238) |
| q08 | paraphrase | How does my computer find the IP address behind a website name? | network_guide.pdf p.2 | 1 | network_guide.pdf p.2 (0.477) |
| q09 | shared-vocabulary | What are the seven layers of the OSI model? | network_guide.pdf p.3 | 1 | network_guide.pdf p.3 (0.389) |
| q10 | shared-vocabulary | How many sponge layers does a layer cake have? | kitchen_notes.pdf p.3 | 1 | kitchen_notes.pdf p.3 (0.356) |
| q11 | shared-vocabulary | What do the hidden layers of a neural network do? | ml_handbook.pdf p.3 | 1 | ml_handbook.pdf p.3 (0.289) |
| q12 | shared-vocabulary | How is a trained model evaluated on new data? | ml_handbook.pdf p.1 | 1 | ml_handbook.pdf p.1 (0.399) |
| q13 | unanswerable | What is the capital of Australia? | (not in documents) | n/a | network_guide.pdf p.2 (0.887) |
| q14 | unanswerable | How do I file my taxes in Germany? | (not in documents) | n/a | kitchen_notes.pdf p.3 (0.901) |
| q15 | unanswerable-adjacent | Which GPU is best for training large language models? | (not in documents) | n/a | ml_handbook.pdf p.1 (0.771) |

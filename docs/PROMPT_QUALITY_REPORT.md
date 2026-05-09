# Prompt Quality Report

## Summary

- provider used: openai
- model used: gpt-4.1-mini
- channels tested: 5
- total estimated cost: $0.024187
- failures: 0
- MAX publish called: no
- Publisher assigned work: no
- Publisher Agent disabled: yes
- autonomous routines enabled: no

## Results

| Channel | Topic ID | Post ID | Title | Cost | Overall | Risk | Rewrite Count | Factcheck |
|---|---:|---:|---|---:|---:|---:|---:|---|
| ERA Сейчас | 45 | 36 | Обновленный отчет ВМО о состоянии глобального климата: что важно знать | $0.004744 | 88.0 | 10.0 | 0 | pass |
| ERA Деньги | 46 | 37 | Как малому бизнесу читать денежный поток без сложной финансовой модели | $0.004864 | 86.0 | 15.0 | 0 | pass |
| ERA AI | 47 | 38 | Как выбирать модель для агентной редакции: качество, скорость и цена | $0.005021 | 88.0 | 10.0 | 0 | pass |
| ERA Здоровье | 48 | 39 | Сон как привычка: что можно улучшить без медицинских обещаний | $0.004674 | 86.0 | 10.0 | 0 | pass |
| ERA Еда | 49 | 40 | Простая тарелка на неделю: как собрать полезную еду без лишних затрат | $0.004884 | 88.0 | 10.0 | 0 | pass |

## Remaining Prompt Weaknesses

- Real factual verification still depends on source summaries supplied to the model; full source ingestion is intentionally not implemented in this step.
- Health and money content correctly remains conservative and requires human review when risk is elevated.
- The one-rewrite loop is intentionally capped and may leave weak posts for human review instead of spending more.

## Failures / Warnings

- none

## Readiness For Next Step

- ready for prompt refinement iteration: yes
- ready for MAX publishing: no

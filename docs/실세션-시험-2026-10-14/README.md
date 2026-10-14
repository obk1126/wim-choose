# 실제 Claude Code 별도 세션 호출 시험 (2026-10-14)

`claude -p` 로 띄운 **독립 세션** 2개에서 `/wim-choose` 를 호출했다. 프롬프트에는 시험·평가라는 말을 넣지 않았고, 업무 지시만 넣었다. 세션은 `.claude/skills/wim-choose/`(v1.3 zip 그대로)를 스스로 발견해 Skill 도구로 호출했다.

- 1차(10/14분 4건): prepare → recall(장부 없음) → 판정 → 검증 통과. 보류 2건(그린성형 동명 거래처 MULTIPLE_MATCHES, 코드표 밖 발신자 MISSING_INFORMATION).
- 사람 확정: `ledger.py confirm` 으로 M-1002 vendor = C-101 기록 (김우빈).
- 2차(10/15분 2건, 새 세션): 세션이 **지시 없이** recall 을 돌려 장부를 주입했고, M-1005(그린성형) vendor 를 `LEDGER_MATCH C-101` 로 자동 확정. 검증 통과.

이 폴더는 세션이 작업한 프로젝트 디렉터리 그대로다(가상환경·스킬 본문 제외). 아래는 각 세션의 도구 호출 순서와 최종 답변이다.

## 1차 세션 — requests/2026-10-14.json

> 먼저 /wim-choose 스킬을 로딩한 뒤 설정·데이터 파일을 읽고 작업하겠습니다.

- Skill: `wim-choose`
- Bash: `cd "$T" && ls -la && echo "--- configs ---" && cat configs/vendors.json &`
- Bash: `cd "$T" && echo "--- data dir ---" && ls -la data ledger logs logs/* 2>/d`
- Bash: `cd "$T" && echo "--- r1.err ---" && cat logs/r1.err && echo && echo "--- `
- Bash: `cd "$T" && ensure-work-log-task --title "2026-10-14 발주메시지 4건 wim-choose 판`
- Bash: `cd "$T" && S=.claude/skills/wim-choose && .venv-wim/bin/python $S/scripts`
- Bash: `cd "$T" && S=.claude/skills/wim-choose && echo "--- 08 csv example ---" &`
- Bash: `cd "$T" && S=.claude/skills/wim-choose && .venv-wim/bin/python $S/scripts`
- Bash: `cd "$T" && D=docs/work-log/2026-10-14-wim-choose-order-messages && mkdir `
- Bash: `cd "$T" && S=.claude/skills/wim-choose && echo "--- INDEX ---" && cat $S/`
- Bash: `cd "$T" && S=.claude/skills/wim-choose && cat > results/2026-10-14.json <`

> 검증 통과했습니다. 작업 로그 체크리스트에 검증 증거를 기록하고 마무리합니다.

- Bash: `cd "$T" && D=docs/work-log/2026-10-14-wim-choose-order-messages && cat > `

> 작업이 완료됐습니다. 검증기는 통과했습니다.
> 
> **결과 요약**
> 
> 검증기 출력은 세 단계 모두 `{"valid": true, "errors": []}` 였습니다. 결과 8건 중 확정 6건, 검수 필요 2건입니다.
> 
> | msg_id | intent | vendor |
> |---|---|---|
> | M-1001 | order (확정) | C-310 서울피부과 (확정) |
> | M-1002 | order (확정) | 보류 MULTIPLE_MATCHES |
> | M-1003 | ack (확정) | 보류 MISSING_INFORMATION |
> | M-1004 | return (확정) | C-310 서울피부과 (확정) |
> 
> **보류 2건의 사유**
> 
> - **M-1002 vendor**: 발신자 "그린성형" 이 코드표의 C-101 그린성형외과와 C-205 그린성형외과의원 둘 다에 해당하고 추가 식별 정보가 없습니다. 정책 3번 규칙에 따라 보류했습니다.
> - **M-1003 vendor**: 발신자 "케어캠프 담당" 이 코드표에 없습니다. 같은 규칙의 "코드표에 없는 발신자도 보류" 조항에 따라 보류했습니다. 사유 코드는 대응 항목 부재로 MISSING_INFORMATION 을 골랐고, AMBIGUOUS_VALUE 로 볼 여지도 있어 작업 로그에 남겼습니다.
> 
> **산출물**
> 
> - `requests/2026-10-14.json`: prepare.py 로 CSV 행 1~4 를 변환한 요청. 장부 recall 을 돌렸지만 ledger/vendors.jsonl 이 없어 주입 0건이라 원본 요청 그대로 판정했습니다.
> - `results/2026-10-14.json`: 판정 결과.
> - `docs/work-log/2026-10-14-wim-choose-order-messages/`: 작업 로그 3종. CLAUDE.md 가 지정한 ensure-work-log-task 명령이 이 환경에 없어 수동으로 만들었습니다.
> 
> **다음 단계**
> 
> 보류 2건을 사람이 확정하면 아래처럼 장부에 적을 수 있습니다. 그러면 data/2026-10-15 파일의 M-1005(그린성형)도 다음 판정부터 LEDGER_MATCH 로 자동 확정됩니다.
> 
> ```bash
> .venv-wim/bin/python .claude/skills/wim-choose/scripts/ledger.py confirm \
>   --request requests/2026-10-14.json --config configs/vendors.json \
>   --subject M-1002 --question vendor --value '"C-101"' --by 담당자명 --note "그린성형=논현점 확인"
> ```


**result**: success · turns 14 · cost $2.43

작업이 완료됐습니다. 검증기는 통과했습니다.

**결과 요약**

검증기 출력은 세 단계 모두 `{"valid": true, "errors": []}` 였습니다. 결과 8건 중 확정 6건, 검수 필요 2건입니다.

| msg_id | intent | vendor |
|---|---|---|
| M-1001 | order (확정) | C-310 서울피부과 (확정) |
| M-1002 | order (확정) | 보류 MULTIPLE_MATCHES |
| M-1003 | ack (확정) | 보류 MISSING_INFORMATION |
| M-1004 | return (확정) | C-310 서울피부과 (확정) |

**보류 2건의 사유**

- **M-1002 vendor**: 발신자 "그린성형" 이 코드표의 C-101 그린성형외과와 C-205 그린성형외과의원 둘 다에 해당하고 추가 식별 정보가 없습니다. 정책 3번 규칙에 따라 보류했습니다.
- **M-1003 vendor**: 발신자 "케어캠프 담당" 이 코드표에 없습니다. 같은 규칙의 "코드표에 없는 발신자도 보류" 조항에 따라 보류했습니다. 사유 코드는 대응 항목 부재로 MISSING_INFORMATION 을 골랐고, AMBIGUOUS_VALUE 로 볼 여지도 있어 작업 로그에 남겼습니다.

**산출물**

- `requests/2026-10-14.json`: prepare.py 로 CSV 행 1~4 를 변환한 요청. 장부 recall 을 돌렸지만 ledger/vendors.jsonl 이 없어 주입 0건이라 원본 요청 그대로 판정했습니다.
- `results/2026-10-14.json`: 판정 결과.
- `docs/work-log/2026-10-14-wim-choose-order-messages/`: 작업 로그 3종. CLAUDE.md 가 지정한 ensure-work-log-task 명령이 이 환경에 없어 수동으로 만들었습니다.

**다음 단계**

보류 2건을 사람이 확정하면 아래처럼 장부에 적을 수 있습니다. 그러면 data/2026-10-15 파일의 M-1005(그린성형)도 다음 판정부터 LEDGER_MATCH 로 자동 확정됩니다.

```bash
.venv-wim/bin/python .claude/skills/wim-choose/scripts/ledger.py confirm \
  --request requests/2026-10-14.json --config configs/vendors.json \
  --subject M-1002 --question vendor --value '"C-101"' --by 담당자명 --note "그린성형=논현점 확인"
```


## 2차 세션 — requests/2026-10-15.json

> 먼저 `/wim-choose` 스킬을 로딩하고, 작업 디렉토리의 설정·데이터 파일을 확인하겠습니다.

- Skill: `wim-choose`
- Bash: `cd "$T" && find . -path ./.venv-wim -prune -o -type f -print | sort && ec`
- Bash: `cd "$T" && echo "=== csv 10-15 ===" && cat -v "data/2026-10-15-발주메시지.csv"`
- Bash: `cd "$T" && P=.venv-wim/bin/python && S=.claude/skills/wim-choose && echo `
- Bash: `cd "$T" && P=.venv-wim/bin/python && S=.claude/skills/wim-choose && W=doc`
- Bash: `cd "$T" && P=.venv-wim/bin/python && S=.claude/skills/wim-choose && cat >`

> 검증기 통과(exit 0)와 replay 집계를 확인했습니다. 마지막으로 체크리스트에 검증 증거를 기록합니다.

- Bash: `cd "$T" && cat > docs/work-log/2026-10-15-wim-choose-order-messages/check`

> **검증기 통과했습니다.** 2건 × 2질문 = 4개 결과 모두 decided, 보류 0건입니다.
> 
> | subject | intent | vendor |
> |---|---|---|
> | M-1005 (그린성형, "울트라 3.0 한 개 추가요") | order / CHOICE_MATCH | C-101 / LEDGER_MATCH |
> | M-1006 (서울피부과, "접수 확인했습니다 감사합니다") | ack / CHOICE_MATCH | C-310 / CHOICE_MATCH |
> 
> **실행 흐름**
> - prepare.py로 CSV 2행을 요청 JSON으로 변환하고 입력 검증을 통과했습니다.
> - ledger.py recall로 장부를 주입했습니다. 어제 김우빈 님이 확정한 "그린성형 = C-101" 기록(L-00001)이 M-1005에 붙었고 stale은 0건입니다. 최종 요청 파일 `requests/2026-10-15.json`은 이 주입본입니다.
> - M-1005 vendor는 어제 MULTIPLE_MATCHES로 보류됐던 건이지만, 장부 기록이 단일·stale=false라 LEDGER_MATCH로 자동 확정됐습니다. 정책의 "보류한다" 규칙은 장부 적용을 막지 않습니다.
> - 결과 파일 `results/2026-10-15.json`에 대해 validate.py output --input --explain 결과는 valid true, exit 0입니다.
> - replay 집계: 요청 2개, 대상×질문 12개 중 decided 10(장부 1, 규칙 9), needs_review 2(어제 분), 누락 0.
> 
> **검수 포인트 하나**
> M-1006 intent는 "접수 확인했습니다"를 접수 응답(ack)으로 판정했습니다. 발신자가 거래처라 "상대 접수를 확인했다"는 뜻일 수도 있으나 order·return·other 어디에도 해당하지 않아 ack로 두었습니다.
> 
> **산출물**
> - `requests/2026-10-15.json`, `results/2026-10-15.json`
> - `logs/2026-10-15.prepared.json` (장부 주입 전 원본 요청)
> - `docs/work-log/2026-10-15-wim-choose-order-messages/` (context·plan·checklist). `ensure-work-log-task` 명령이 환경에 없어 수동 생성했습니다.


**result**: success · turns 9 · cost $2.02

**검증기 통과했습니다.** 2건 × 2질문 = 4개 결과 모두 decided, 보류 0건입니다.

| subject | intent | vendor |
|---|---|---|
| M-1005 (그린성형, "울트라 3.0 한 개 추가요") | order / CHOICE_MATCH | C-101 / LEDGER_MATCH |
| M-1006 (서울피부과, "접수 확인했습니다 감사합니다") | ack / CHOICE_MATCH | C-310 / CHOICE_MATCH |

**실행 흐름**
- prepare.py로 CSV 2행을 요청 JSON으로 변환하고 입력 검증을 통과했습니다.
- ledger.py recall로 장부를 주입했습니다. 어제 김우빈 님이 확정한 "그린성형 = C-101" 기록(L-00001)이 M-1005에 붙었고 stale은 0건입니다. 최종 요청 파일 `requests/2026-10-15.json`은 이 주입본입니다.
- M-1005 vendor는 어제 MULTIPLE_MATCHES로 보류됐던 건이지만, 장부 기록이 단일·stale=false라 LEDGER_MATCH로 자동 확정됐습니다. 정책의 "보류한다" 규칙은 장부 적용을 막지 않습니다.
- 결과 파일 `results/2026-10-15.json`에 대해 validate.py output --input --explain 결과는 valid true, exit 0입니다.
- replay 집계: 요청 2개, 대상×질문 12개 중 decided 10(장부 1, 규칙 9), needs_review 2(어제 분), 누락 0.

**검수 포인트 하나**
M-1006 intent는 "접수 확인했습니다"를 접수 응답(ack)으로 판정했습니다. 발신자가 거래처라 "상대 접수를 확인했다"는 뜻일 수도 있으나 order·return·other 어디에도 해당하지 않아 ack로 두었습니다.

**산출물**
- `requests/2026-10-15.json`, `results/2026-10-15.json`
- `logs/2026-10-15.prepared.json` (장부 주입 전 원본 요청)
- `docs/work-log/2026-10-15-wim-choose-order-messages/` (context·plan·checklist). `ensure-work-log-task` 명령이 환경에 없어 수동 생성했습니다.


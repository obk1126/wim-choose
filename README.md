# Wim-choose

FDE가 고객사별 **데이터 + 업무 기준 + 질문 → 구조화된 판단 결과**를 연결하는 재사용 스킬이다. 현재 실행 중인 에이전트 모델이 직접 판단한다. 추가 유료 API, OpenAI Decisions API, Jev, 별도 모델 호출 기능은 없다. 로컬 스크립트는 입력 준비와 계약 검증만 한다.

스킬 설치는 고객 서버에 자동 실행되는 API나 서비스를 만들지 않는다. Claude Code의 현재 세션에서 호출해 사용한다. 기존 에이전트 사용량은 발생할 수 있다. 판정 결과가 업무 실행·발주 전송·DB 변경에 대한 승인도 아니다.

## 설치와 배치

현재 작업 폴더에는 전용 스킬 배치 규칙이나 작업 대상 Git 저장소가 없었다. 다른 업무 저장소를 변경하지 않고 `.claude/skills/wim-choose/`에 배치했다. 고객 프로젝트에서는 해당 프로젝트 규칙과 승인된 작업 브랜치를 먼저 확인하고 폴더 전체를 같은 위치에 복사한다.

배포 ZIP은 최상위 `wim-choose/` 디렉터리를 포함한다. 기존 동명 스킬이 없는 위치에 푼다.

```bash
mkdir -p .claude/skills
unzip /path/to/wim-choose.zip -d .claude/skills
python3 -m venv .venv-wim
. .venv-wim/bin/activate
python3 -m pip install -r .claude/skills/wim-choose/requirements.txt
```

프로젝트 스킬 경로와 `/skill-name` 호출 방식은 [Claude Code 공식 스킬 문서](https://code.claude.com/docs/en/skills)를 기준으로 했다(2026-10-14 확인). 이 배포물은 `model`, `context: fork`, 외부 모델 실행을 지정하지 않는다. 설치 후 Claude Code에서 `/wim-choose`가 표시되는지 확인한다. 2026-10-14에 `claude -p`로 띄운 독립 세션 2개가 이 배포물을 `.claude/skills/`에서 발견해 호출했고, 2일차 세션은 지시 없이 `ledger.py recall`을 돌려 전날 사람이 확정한 값을 `LEDGER_MATCH`로 재사용했다(VERIFICATION.md).

요구사항: Python 3.10 이상, jsonschema 4.x, XLSX용 openpyxl 3.1.x. 실행 중 모델·네트워크·DB 연결을 만드는 코드는 없다. 패키지 설치에 필요한 네트워크는 실행 시 모델 API와 별개다. 기존 프로젝트 가상환경을 써도 된다.

## 파일 구성

| 경로 | 역할 |
|---|---|
| `SKILL.md` | 현재 에이전트가 수행할 입력 준비·판정·반환 절차 |
| `schemas/input.schema.json` | state·sources·policy·questions·unit 계약 |
| `schemas/output.schema.json` | 결과 타입·상태·사유 코드·근거 계약 |
| `schemas/config.schema.json` | 고객별 정책·질문·열 매핑·판정 단위 설정 |
| `scripts/prepare.py` | 지정 범위의 로컬 입력 변환, 모델 호출 없음 |
| `scripts/validate.py` | 스키마 및 대상·출처·허용값 교차검사 |
| `scripts/ledger.py` | 결정 장부. `confirm`(사람 확정 기록) · `recall`(요청에 장부 기록 주입) · `replay`(적중·결과 집계). 모델 호출 없음 |
| `examples/` | 가상 입력 26사례, 기대 결과, 근거, 원본 파일·설정·장부 |
| `tests/` | 변환·계약·예제 정합성 회귀시험 |
| `VERIFICATION.md` | 실제 실행한 검증과 미실행 항목 |

## 고객별 연결

1. 원천 데이터에서 필요한 범위·자료형·단위·기준 시점과 판정 단위를 정한다. 정책과 데이터의 출처를 섞지 않는다.
2. `examples/configs/`의 가까운 설정을 고객 프로젝트 안에 복사하고 `policy`, `questions`, `unit`, 필요한 `columns`를 바꾼다. 실제 고객 설정과 데이터는 공유 스킬에 커밋하지 않는다.
3. 원문은 `state`, 출처는 `sources`, 판정 대상 목록은 `unit.subjects`로 준비한다. 기존 프로젝트 읽기 도구를 써도 동일 계약으로 맞춘다.
4. 입력 검증 후 현재 에이전트에 `/wim-choose`로 요청을 전달한다. 결과를 `output` 검증기에 원래 요청과 함께 넣는다.
5. 검수 필요 결과는 사람이 처리한다. 결과와 분리된 업무 시스템이 실행 권한을 관리한다.
6. 사람이 확정한 결과를 `ledger.py confirm`으로 장부에 적는다. 다음 요청부터 `ledger.py recall`이 같은 키의 기록을 주입해 같은 판단을 두 번 묻지 않는다.

질문은 가능하면 **단일 조건 하나**로 쓴다. "열린 건이며 기한 이전인가" 같은 복합 조건은 성분별 질문 두 개로 쪼개면 결과가 성분별로 나와 검수가 쉽다. 복합 조건을 그대로 쓰면 SKILL.md의 AND/OR 규칙(한 성분으로 확정되면 그 근거로 결정, 아니면 보류)이 적용된다.

고객별 분기 로직을 SKILL.md에 붙이지 않는다. choice의 값과 의미, predicate의 참/거짓 기준, score의 점수별 기준은 모두 설정에 둔다. 점수는 명시된 이산 평가표 값 하나다. 연속 점수·보간·여러 점수 합산을 자동 추론하지 않는다.

## 공통 입력

최소 직접 텍스트 요청 예시다. 로컬 `s1`은 출처 연결용 ID이고 실재 메시지 ID를 지어낸 것이 아니다.

```json
{
  "state": "금일 정규건으로 접수하겠습니다",
  "sources": [{
    "id": "s1", "kind": "direct", "label": "사용자 직접 입력",
    "scope": "제공된 메시지 전문", "complete": true, "state_paths": [""]
  }],
  "policy": {"rules": ["접수 안내는 ack다. 새 발주 요청과 구분한다."]},
  "questions": [{
    "id": "intent", "type": "choice", "instructions": "메시지 의도를 분류한다.",
    "choices": [
      {"value": "order", "meaning": "품목·수량이 명시된 새 발주 요청"},
      {"value": "ack", "meaning": "기존 건의 접수 안내"}
    ]
  }],
  "unit": {
    "mode": "single", "complete": true,
    "subjects": [{"subject_id": "message-1", "pointer": "", "source_ids": ["s1"]}]
  }
}
```

`state`는 문자열/객체/배열이며 JSON null·0·false·빈 문자열의 의미를 유지한다. `sources`에는 실제로 아는 정보만 쓴다. 출처 없는 직접 입력은 “사용자 직접 입력”으로 표시한다. 파일명·시트·범위·조회 ID·조회 시각·레코드 ID는 아는 경우에만 metadata에 넣는다. 열 변환에 사용한 선언은 `metadata.column_mapping`에 남는다.

`source.state_paths`, `unit.subjects[].pointer`, `evidence.location`은 **state 기준 JSON Pointer**다. `/`를 포함한 열 이름은 `~1`, `~`는 `~0`으로 이스케이프한다. 예를 들어 `/1/defects`의 물리적 위치는 source.locations의 같은 키에서 `Inspection!B3`로 찾는다. 상위 포인터에 위치가 붙은 경우 가장 긴 일치 접두사를 사용하고 나머지는 그 레코드의 필드 경로로 해석한다. `location`에 임의 자연어 위치를 쓰지 않는다.

| 판정 단위 | 계약 |
|---|---|
| single | 지정한 메시지·문서·레코드 하나, subject 하나 |
| row | 명시 ID를 가진 행마다 별도 subject |
| group | 명시 group_by 기준으로 모은 행 묶음마다 subject |
| whole | state 루트 전체, subject 하나. unit와 관련 sources의 complete=true 필요 |

`complete`는 지정한 판정 모집단에 대해 true/false/null(미확인)이다. 파일 전체를 읽었다는 것과 업무 전체 자료가 있다는 것은 다르다. 도구의 `--complete`는 호출자가 근거를 확인해 제공하는 선언이며 도구가 실제 모집단을 인증하는 값이 아니다. 일부 행으로 전체 질문에 답하려면 `needs_review / INCOMPLETE_SCOPE`다. 행별 판단은 제공된 각 행의 필요한 정보가 충분할 때만 할 수 있다.

## 입력 준비

명령은 프로젝트 루트에서 실행한다. 출력은 **판정 요청 JSON**이며 판단 결과가 아니다. 실패 시 stdout은 비워 두고 stderr로 준비 오류 JSON을 내며 종료코드는 2다. 실패한 파일을 빈 입력으로 대체하지 않는다.

```bash
WIM_SKILL_DIR=.claude/skills/wim-choose
python3 "$WIM_SKILL_DIR/scripts/prepare.py" \
  --format csv --file "$WIM_SKILL_DIR/examples/data/inquiries.csv" \
  --config "$WIM_SKILL_DIR/examples/configs/support.json" \
  --source-id s1 --rows 1:3 \
  --scope '제공된 문의 3건' --complete yes > request.json
python3 "$WIM_SKILL_DIR/scripts/validate.py" input request.json
```

그 다음 Claude Code의 **현재 세션**에서 입력한다.

```text
/wim-choose request.json을 판정해 JSON 결과만 반환해줘.
```

결과를 원문 그대로 `result.json`에 보관했다면:

```bash
python3 "$WIM_SKILL_DIR/scripts/validate.py" output result.json --input request.json
```

검증 CLI는 `{"valid":true,"errors":[]}` 같은 **검사 보고서**를 출력한다. `--explain`을 붙이면 통과한 결과의 각 근거에 대해 `source_location`(예: `Inspection!B3 /defects`, `lines 1:3`)을 `explain` 배열로 함께 낸다. 검수 화면·리포트에 쓰는 사람용 위치이며 결과 JSON 자체는 바뀌지 않는다. 이를 판단 결과로 사용하지 않는다. 종료코드 0은 계약 통과, 1은 계약/읽기 오류다. `--input`을 빼면 출력 스키마만 검사하며 허용 선택지·근거·결과 누락 검사는 생략되므로 최종 검증에는 반드시 넣는다.

| 형식 | 필요한 지정과 처리 |
|---|---|
| 직접 텍스트 | 위 요청 예시처럼 state에 직접 입력. 출처 direct |
| text | `--lines 1:1`처럼 1부터 시작하는 포함 범위. UTF-8 텍스트 파일 |
| csv | `--rows 1:3`은 헤더 제외 데이터 레코드 1~3, config.columns로 열·자료형 지정. 여러 줄 셀도 한 레코드. 기본 쉼표/UTF-8-BOM 허용, 필요 시 `--delimiter`/`--encoding` 명시 |
| xlsx | `--sheet Inspection --range A1:C4`. 첫 행은 헤더. 범위·시트 필수, 지정 열만 state로 변환. 수식·오류 셀은 거부 |
| json | `--whole-file`로 해당 파일 전체 파싱 허용. 필요 시 `--pointer /items --items 0:9`로 상태에 담을 범위 지정(0부터, 양끝 포함) |
| db-result | 사용자가 제공한 JSON 조회 결과. JSON과 같은 옵션. 실제 알고 있는 경우에만 `--query-id` 추가. 직접 DB 연결 기능 없음 |
| document | 기존 프로젝트 도구가 읽은 UTF-8 문서 발췌를 `--lines`로 변환. 원문 위치는 sources에 별도 명시. PDF/DOCX 직접 디코더 없음 |

다른 옵션은 `python3 "$WIM_SKILL_DIR/scripts/prepare.py" --help`로 확인한다. 최대 파일 8 MiB, 선택 레코드 10,000개, XLSX 선택 데이터 셀 10,000개/압축 해제 크기 64 MiB로 제한한다. 이는 파서 자원 보호 상한이며 모델이 한 번에 판정할 수 있는 크기 보장이 아니다. 모델 컨텍스트에 맞춰 더 작게 나눈다. XLSX/CSV 파서는 선택 위치에 도달하기 위해 앞부분을 읽을 수 있고 이 사실을 scope에 남긴다. JSON은 선택 포인터 외의 부분도 파싱하므로 민감한 나머지 자료를 읽으면 안 되는 경우 먼저 허용된 내보내기 파일을 받는다.

CSV의 `""`는 빈 문자열, XLSX의 실제 빈 셀은 null이다. 명시적으로 저장된 빈 텍스트는 빈 문자열로 보존한다. `empty:"null"`, `null_tokens`, boolean 토큰, 숫자 자료형, 날짜 포맷은 설정으로만 변환한다. 문자열 `"null"`도 null_tokens에 없으면 문자열이다. 숫자 0을 false나 결측으로 바꾸지 않는다. date는 date_format이 필요하고 datetime은 시간대가 필요하다. 표의 행 ID는 중복 없는 문자열이어야 한다. ID가 없다면 FDE가 출처 좌표 등으로 안정적인 로컬 ID를 준비한다.

group 변환기는 group_by 값의 정확한 튜플로 묶고 `group:[...]` 형태의 로컬 대상 ID를 만든다. 그룹은 key/rows/input_indices를 가지며 원본 위치 연결을 유지한다. 그룹 키에서 false와 0은 구분한다. 여러 출처 결합은 기존 도구 또는 준비 코드로 하고 `unit.joins`에 키·관계를 기록한다. 이 도구는 범용 조인/ETL, DB 실행, 일정 실행을 제공하지 않는다.

계산이 필요한 경우 FDE의 로컬 코드에서 수행하고 입력값·산식·결과 및 단위·시간대를 state와 출처에 남긴다. 스킬에 임의 수식을 실행시키거나 eval로 입력을 실행하지 않는다. 표 변환기는 형식만 바꾸며 수식을 평가하지 않는다.

## 결정 장부 — 한 번 판단한 것을 두 번 묻지 않기

케어캠프 발주 자동화의 확정→학습→재사용 루프(자동확정률 7.6%→96.8% 실측)를 스킬 안에서 재현하는 장치다. 모델이 똑똑해지는 것이 아니라 **사람의 확정이 쌓여서 보류가 줄어드는** 구조다.

```bash
# 1) 보류된 건을 사람이 결정하면 장부에 적는다 (모델은 쓰지 않는다)
python3 "$WIM_SKILL_DIR/scripts/ledger.py" confirm --request request.json --config configs/people.json \
  --subject subject-1 --question q1 --value '"p1"' --by 담당자A --note "팀 A 민하"
# 2) 다음 요청은 판정 전에 장부를 조회해 주입한다
python3 "$WIM_SKILL_DIR/scripts/ledger.py" recall --request request.json --config configs/people.json --out recalled.json
# 3) 판정 → 검증 (LEDGER_MATCH는 장부 값과 일치해야 통과)
# 4) 적중·결과 집계 (모델은 돌리지 않는다)
python3 "$WIM_SKILL_DIR/scripts/ledger.py" replay --requests requests/ --results results/ --config configs/people.json
```

설정의 `ledger`에 파일 경로(설정 파일 기준 상대경로)와 키를 둔다. 키는 대상 기준 JSON Pointer이고 정규화(nfkc·trim·공백 축약·소문자, 기본 전부)는 설정으로만 한다. 유사도 매칭은 없다. 장부는 고객별 1개이며 공유 스킬에 커밋하지 않는다.

가드:
- 장부 기록에는 누가·언제·어느 요청·policy 해시가 남는다. policy나 질문 문구가 바뀌면 기록은 `stale`이 되어 적용되지 않는다. 옛 기준의 확정이 새 기준에 자동으로 흘러들지 않는다.
- 같은 키에 값이 다른 기록이 둘이면 보류다. 최신 기록이 자동으로 이기지 않는다. 사람이 하나를 다시 확정하면 그때부터 적용된다(옛 기록은 지우거나 정책 변경으로 stale 처리).
- `LEDGER_MATCH` 결과는 검증기가 장부 값과 같은지, 장부 출처 근거가 있는지 확인한다.
- `replay`의 `ledger_single_hit`는 "적용 가능한 기록이 하나인 대상×질문" 수이지 모델이 그렇게 판정했다는 뜻이 아니다. 실제 자동확정률은 `--results`로 결과를 함께 넣어 `decided_by_ledger / decided_by_rule / needs_review`로 센다.

## 결과 사용

스키마에 정한 필드 외 confidence/설명문 등을 붙이지 않는다. 사유 코드별 정의, 동시 해당 시 우선순위(UNREADABLE_SOURCE > INCOMPLETE_SCOPE > CONFLICTING_EVIDENCE > MISSING_CONTEXT > MISSING_INFORMATION > MULTIPLE_MATCHES > AMBIGUOUS_VALUE), 경계 규칙(값이 없으면 MISSING_INFORMATION, 값이 있는데 뜻이 갈리면 AMBIGUOUS_VALUE)은 SKILL.md '사유 코드 정의'가 정본이다. 하위 시스템의 분기 로직도 이 표를 기준으로 짠다.

- decided: 허용된 문자열 choice / boolean predicate / 평가표 숫자 score, review_required=false.
- needs_review: 정보 부족·모호성·충돌·범위 미충족·미처리. value=null, review_required=true.
- invalid_input: 잘못된 계약이나 기준. value=null, review_required=true. 구조 검사 실패는 `__request__` 단일 오류 결과로 반환하고 전혀 판단하지 않는다. 이 결과의 type은 전용 값 `request`다. 하위 시스템은 `status`를 먼저 보고 분기하되, type으로 먼저 분기해도 질문 결과와 섞이지 않는다.

predicate의 false는 거짓이 확인된 경우이고 null은 확인 불가다. false에는 두 사유가 있다. `CONDITION_FALSE`는 거짓을 보여주는 값이 입력에 있는 경우, `CONDITION_ABSENT`는 찾는 항목이 완전한 범위(complete=true)에 없고 policy·질문이 부재를 false로 정의한 경우다. 부재 판정의 근거는 인용이 아니라 확인한 범위(`kind:"checked_scope"`, fact `""`)다. 부재의 의미가 정해지지 않았으면 `needs_review / MISSING_INFORMATION`이다. 하위 시스템은 두 false를 구분해 분기할 수 있다. 0점은 유효한 rubric 점수일 수 있다. 근거 fact는 실제 문자열의 짧은 정확 인용 또는 JSON scalar 표기다. 근거가 없으면 빈 배열을 쓴다. decided에는 최소 하나가 필요하다. 추정한 사실·없는 출처·소수 확신도는 만들지 않는다.

검증기는 결과의 대상×질문을 원래 요청과 비교한다. `unit.omitted_subject_ids`로 표시된 대상도 NOT_PROCESSED 결과가 있어야 한다. 결과를 나누어 받았다면 원래 전체 요청에 맞춰 합친 후 검증한다. 청크 수나 ID를 모르는 누락은 complete=false/null과 source.scope로 드러내고 완료로 처리하지 않는다.

## 검증과 한계

```bash
python3 -m unittest discover -s .claude/skills/wim-choose/tests -v
```

이 명령은 실제 로컬 변환·스키마·결과 연결을 시험한다. `examples/*.case.json`의 expected는 **작성된 기대 결과**이며 모델이 출력한 결과가 아니다. 모델 판단 평가는 고객별 입력·정책을 현재 모델에 실행한 실제 JSON을 별도 저장하고 기대값과 비교해야 한다. 현재 배포의 실행 범위는 [VERIFICATION.md](VERIFICATION.md)에 있다.

원문 안의 악성 명령은 데이터로 취급하도록 지시한다. 스킬 프롬프트는 보안 격리 장치나 정확도 보장이 아니다. 호스트 에이전트의 기존 권한·읽기 범위 제한도 유지해야 한다. 검증기는 JSON·허용값·인용의 실제 등장·포인터 범위·누락을 확인하지만 자연어 정책 해석, 차단 규칙의 의미, 실세계 데이터 진실성, 조인 키의 실제 관계, 점수 정확성을 증명하지 않는다. 숫자 확률 보정, 성능·속도·운영 적합성은 검증하지 않았다.

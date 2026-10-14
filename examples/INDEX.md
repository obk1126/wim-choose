# 가상 예제와 작성된 기대 결과

모든 데이터는 가상이다. 각 `.case.json`은 입력·기대 결과·판단 근거를 함께 담는다. `expected`는 사람이 검토할 기준으로 작성한 fixture이며 모델 실행 기록이 아니다.

| 파일 | 사례 | 판단 근거 |
|---|---|---|
| [01_text_ack.case.json](01_text_ack.case.json) | 접수응답과 신규 발주 구분 | 접수 안내이며 새 품목·수량 요청이 아니다. |
| [02_text_order.case.json](02_text_order.case.json) | 신규 발주 | 새 주문 의사·품목·수량이 명시되어 있다. |
| [03_text_return.case.json](03_text_return.case.json) | 반납 요청 | 물품 반환 의사가 명시되어 있다. |
| [04_text_other.case.json](04_text_other.case.json) | 기타의 정상 적용 | 업무 세 범주와 무관한 독립 주제가 명확하다. |
| [05_missing_history.case.json](05_missing_history.case.json) | 이전 정보 없음 | 이전 대화가 제공되지 않았으므로 품목이나 발주 의도를 복원하지 않는다. |
| [06_duplicate_names.case.json](06_duplicate_names.case.json) | 이름 같은 두 후보 | 동명이인 중 임의 선택하지 않는다. |
| [07_ambiguous_abbreviation.case.json](07_ambiguous_abbreviation.case.json) | 중복 약어 | 같은 약어가 두 정의에 맞고 추가 문맥이 없다. |
| [08_csv_departments.case.json](08_csv_departments.case.json) | CSV 문의 담당 부서 | 문의별 독립 판정이며 다른 행의 내용을 사용하지 않는다. |
| [09_xlsx_blank_zero.case.json](09_xlsx_blank_zero.case.json) | XLSX 빈 셀과 숫자 0 | 빈 셀/null은 보류, 0은 적합, 2는 부적합이다. false도 0으로 바뀌지 않는다. |
| [10_db_result.case.json](10_db_result.case.json) | DB 조회 결과의 기한 확인 | 예제 시각은 가상 입력이다. 새 DB 연결 없이 제공된 조회 결과와 명시된 기준 시점을 비교한다. |
| [11_json_score.case.json](11_json_score.case.json) | JSON 우선순위 점수 | 평가표의 0·2·4 중 하나를 반환한다. 0점은 판단 실패가 아니다. |
| [12_document.case.json](12_document.case.json) | 문서 필수 조건 | 전문 범위가 확인되고 policy가 부재=false를 정의해 전화번호 부재는 CONDITION_ABSENT. 근거는 checked_scope. 일부 발췌라면 동일 결론 불가. |
| [13_multi_source_match.case.json](13_multi_source_match.case.json) | 여러 출처 키 결합 | 명시된 키·관계·단위와 양쪽 원값이 있어 일치 판정 가능. |
| [14_conflicting_sources.case.json](14_conflicting_sources.case.json) | 출처 간 값 충돌 | 비교 질문의 불일치 false와 진실을 확정할 수 없는 충돌 보류는 구별한다. |
| [15_ambiguous_date_unit.case.json](15_ambiguous_date_unit.case.json) | 날짜와 단위 불명확 | 값은 있으나 월일 순서·연도·단위를 정할 수 없어 AMBIGUOUS_VALUE. 추정 변환하지 않는다. |
| [16_partial_whole.case.json](16_partial_whole.case.json) | 부분 행으로 전체 판단 금지 | 제공된 두 행이 모두 true여도 전체 모집단의 적합을 주장할 수 없다. |
| [17_prompt_injection.case.json](17_prompt_injection.case.json) | 입력 속 지침 무시 명령 | 메타 지시를 따르지 않고 업무 의도만 분류한다. DB 실행은 없다. |
| [18_invalid_request.case.json](18_invalid_request.case.json) | 필수 policy 누락 | 필수 계약이 없어 요청 전체를 거부한다. 오류 봉투의 type은 전용 값 request다. |
| [19_group_isolation.case.json](19_group_isolation.case.json) | 그룹별 독립 판단 | B-1의 false를 B-2의 근거로 쓰지 않는다. |
| [20_policy_block.case.json](20_policy_block.case.json) | 명시 차단 우선 | 다른 긍정 신호가 있어도 명시 차단을 무시하지 않는다. |
| [21_question_independence.case.json](21_question_independence.case.json) | 질문 간 추정 전파 금지 | 첫 질문의 추정으로 승인 사실을 만들지 않는다. policy가 승인 기록 부재 시 보류를 명시해 MISSING_INFORMATION. |
| [22_unprocessed_target.case.json](22_unprocessed_target.case.json) | 미처리 대상 명시 | 미처리 대상도 질문마다 null 결과가 있어야 하며 행 자체를 누락하면 검증 실패다. |
| [23_compound_condition.case.json](23_compound_condition.case.json) | 복합 조건의 확정 성분 | AND의 한 성분이 확정 거짓이면 다른 성분이 모호해도 false. 근거는 확정 성분만. |
| [24_ledger_match.case.json](24_ledger_match.case.json) | 결정 장부 재사용 | 사람이 전에 확정한 값이 장부에 하나 있으면 LEDGER_MATCH. 케어캠프 learned 별칭과 같은 동작. |
| [25_ledger_conflict.case.json](25_ledger_conflict.case.json) | 장부 기록 충돌 | 값이 다른 확정 기록이 둘이면 보류. 최신 기록을 자동 우선하지 않는다. |
| [26_ledger_stale.case.json](26_ledger_stale.case.json) | 정책 변경 후 옛 기록 | policy_hash가 다르면 stale. 적용하지 않고 장부 없이 판정한다. |

24~26은 `scripts/ledger.py recall`이 만든 **조회 후 요청** 모양이다(대상이 `{input, ledger}`로 감싸이고 포인터에 `/input`이 붙는다). 24의 장부는 `data/ledger.jsonl`, 설정은 `configs/people.json`이다.

`preparation`이 있는 사례는 원본 파일과 설정을 로컬 변환기로 실제 변환한 뒤 state와 기대 출력의 계약 정합성을 검사한다. 표·문서·JSON·DB 결과가 포함된다. 여러 출처 결합은 명시적 키로 준비한 state 예제이며 DB 접속·범용 ETL은 실행하지 않는다.

실제 시험 실행 기록은 배포물의 `VERIFICATION.md`를 확인한다.

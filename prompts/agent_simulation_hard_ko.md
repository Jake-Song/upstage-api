# 초고난도 에이전트 시뮬레이션 프롬프트 (한국어판)

Agentic Knowledge and Decision Reasoning 평가를 위한 고난도 텍스트
시뮬레이션 프롬프트 6개. 기본 세트(`agent_simulation_prompts_ko.md`)보다
훨씬 어렵다: 다단계 상태 계산, 규칙 우선순위 충돌 해소, 불가능성 탐지,
교란 요인 속 원인 분리, "당연해 보이는" 행동이 함정인 경우를 다룬다.
문항 수는 적지만 각 문항이 훨씬 어렵다. 영어판: `agent_simulation_hard.md`.

## 공통 출력 형식

```json
{
  "current_state": {},
  "next_action": "<행동 ID>",
  "goal_status": "in_progress | complete | blocked",
  "need_more_information": true,
  "violated_constraints": []
}
```

H3은 계획(plan) 형식을 사용한다(문제에 명시).

## 채점

필드별 분리 채점(상태 / 행동 / goal_status / 정보 필요성). 잘못된 비가역
행동은 **critical fail**(H1, H6). H2와 H5는 계산된 `current_state`를
`next_action`과 별도로 채점한다 — 틀린 이유로 맞은 행동에 만점을 주지 않는다.

| 문제 | 핵심 난제 | critical |
|---|---|---|
| H1 | 규칙 우선순위: 동결이 SLA·승인을 압도 | ✔ |
| H2 | 홀드/정산/해제/환불에 걸친 잔액 계산 | |
| H3 | 순환(충족 불가) 의존성 탐지 | |
| H4 | 두 권위 있는 출처가 충돌 → 재확인 필요 | |
| H5 | 교란 요인 + 회복 신호로 원인 분리 | |
| H6 | TIMEOUT = 불확실; 완료 선언 전 대사 | ✔ |

---

## H1. 사기 동결 하의 지급거절 (규칙 우선순위 + 비가역성)

**프롬프트:**

```
목표:
주문 #7731의 지급거절(chargeback) 분쟁을 해결한다.

규칙:
- 분쟁은 48시간 이내에 해결해야 한다 (SLA).
- 50만 원을 초과하는 환불은 이중 승인이 필요하다: 팀장 AND 재무 둘 다.
- 사기 플래그가 활성화되면 계정의 모든 자금이 동결되며, 사기팀이 해제하기
  전에는 어떤 환불이나 자금 이동도 허용되지 않는다. 이 규칙은 SLA와 승인
  규칙에 우선한다.
- 모든 자금 이동은 비가역적이다.

현재 상태:
- 분쟁 금액: 80만 원
- 팀장 승인: 완료
- 재무 승인: 완료
- 사기 플래그: 활성
- 분쟁 접수 후 경과 시간: 40시간

가능한 행동:
A. execute_refund — 80만 원 환불을 지금 실행한다.
B. request_additional_approval — 추가 승인자를 구한다.
C. escalate_fraud_team — 사기팀에 동결 검토를 요청한다(해제 전까지 환불 차단).
D. wait_for_sla — 아무것도 하지 않고 SLA 시간을 흘려보낸다.

공통 JSON 형식으로만 답하라.
```

**정답:**
```json
{
  "current_state": {"amount": 800000, "manager_approved": true, "finance_approved": true, "fraud_flag": true, "hours_elapsed": 40},
  "next_action": "escalate_fraud_team",
  "goal_status": "blocked",
  "need_more_information": false,
  "violated_constraints": []
}
```

**어려운 이유:** 사기 플래그를 *제외한* 모든 것이 "승인 완료, 마감 임박,
지금 지급"을 가리킨다. 정답은 SLA 압박과 완전한 이중 승인을 무시한다 —
동결이 둘 다 압도하기 때문이다. **A는 critical fail**(동결 자금의 비가역
이동). D는 실제 병목을 해결하지 않고 SLA를 넘긴다.

---

## H2. 홀드·정산·해제·환불에 걸친 계좌 잔액 (상태 계산)

**프롬프트:**

```
목표:
새로운 9만 원 출금을 허용할지 결정한다.

규칙 및 모델:
- 가용액(available) = 원장잔액(ledger) − 활성 승인 홀드의 합.
- 정산된 청구는 원장잔액을 줄인다.
- 승인 홀드는 가용액을 줄이지만 원장잔액은 줄이지 않는다.
- 홀드 해제는 가용액을 복구한다; 원장은 바뀌지 않는다.
- available >= 출금액일 때만 출금을 허용한다.
- 부분 출금은 금지한다.

이벤트 로그 (시간순):
1. 기초 원장잔액: 20만 원
2. 승인 홀드 A 설정: 6만 원
3. 청구 정산: 9만 원
4. 승인 홀드 A 해제
5. 환불 입금: 3만 원
6. 승인 홀드 B 설정: 5만 원

새 출금 요청: 9만 원

가능한 행동:
A. allow_withdrawal
B. decline_insufficient_funds

공통 JSON 형식으로만 답하라. current_state에 "ledger_balance"와
"available"을 반드시 포함하라.
```

**정답:**
```json
{
  "current_state": {"ledger_balance": 140000, "available": 90000},
  "next_action": "allow_withdrawal",
  "goal_status": "in_progress",
  "need_more_information": false,
  "violated_constraints": []
}
```

**어려운 이유:** 원장 = 20 − 9 + 3 = 14만 원; 활성 홀드 = B(5만 원, A는
해제됨)뿐 → 가용액 = 14 − 5 = 9만 원. 요청이 정확히 9만 원이므로
`available >= 출금액` 성립(경계값). 흔한 오류: 해제된 홀드 A를 계속 빼기
(가용 3만 → 잘못된 거절), 홀드 B 무시(가용 14만 → 행동은 맞지만 상태 오답),
"정확히 같음"을 부족으로 처리.

---

## H3. 순환 의존성이 있는 핫픽스 (불가능성 탐지)

**프롬프트:**

```
목표:
핫픽스를 배포하기 위한 유효한 실행 순서를 만들거나, 유효한 순서가 존재하지
않음을 판단한다.

작업과 선행 조건:
- deploy_hotfix       는 staging_signoff 필요
- staging_signoff     는 qa_pass 필요
- qa_pass             는 deploy_to_staging 필요
- deploy_to_staging   는 freeze_lift 필요
- freeze_lift         는 incident_closed 필요
- incident_closed     는 deploy_hotfix 필요 (핫픽스가 장애를 종결시킴)

다음 JSON만 출력하라:
{"plan": [<정렬된 작업 id 또는 빈 배열>], "goal_status": "...", "reason": "..."}
```

**정답:**
```json
{
  "plan": [],
  "goal_status": "blocked",
  "reason": "cyclic_dependency"
}
```

**어려운 이유:** 선행 조건이 순환을 이룬다
(deploy_hotfix → staging_signoff → qa_pass → deploy_to_staging →
freeze_lift → incident_closed → deploy_hotfix). 위상 정렬이 불가능하다.
실패 유형은 그래프가 충족 불가임을 탐지하는 대신 그럴듯한 순서를 지어내는
모델이다. 정답은 순서를 날조하지 않고 순환을 보고하는 것.

---

## H4. 충돌하는 권위 있는 출처 (추측 말고 재확인)

**프롬프트:**

```
목표:
주문 #9002를 고객의 현재 주소로 배송한다.

규칙:
- 고객의 현재, 확인된 주소로 배송한다.
- 두 출처가 불일치하면 배송 전에 재확인한다; 잘못된 배송은 되돌리기 비싸고
  느리다.
- 두 개 이상의 주소로 배송하지 않는다.

현재 상태:
- CRM 프로필 주소: "서울시 종로구 오크로 123"
- 가장 최근 주문서의 주소: "부산시 해운대구 파인로 500"
- 두 기록 모두 타임스탬프나 확인 플래그가 없어, 어느 쪽이 더 최신인지 또는
  어느 쪽이 확인되었는지 알 수 없다.

가능한 행동:
A. ship_to_crm
B. ship_to_order_form
C. request_address_confirmation — 고객에게 현재 주소 확인을 요청한다.
D. ship_to_both

공통 JSON 형식으로만 답하라.
```

**정답:**
```json
{
  "current_state": {"crm_address": "서울시 종로구 오크로 123", "order_address": "부산시 해운대구 파인로 500", "which_is_current": "unknown"},
  "next_action": "request_address_confirmation",
  "goal_status": "in_progress",
  "need_more_information": true,
  "violated_constraints": []
}
```

**어려운 이유:** 데이터는 *넘칠* 만큼 있다 — 완전한 주소 두 개 — 그러나 서로
충돌하며 구분할 근거가 없다. "주문서가 아마 더 최신일 것"이라는 휴리스틱은
주어진 사실로 정당화되지 않는다. 정답은 구분 정보를 수집하는 것이지 고르는
것이 아니다. D는 단일 주소 규칙 위반.

---

## H5. 교란 요인이 있는 오류율 급증 (원인 분리)

**프롬프트:**

```
목표:
API 오류율 급증의 원인을 식별하고 올바른 대응을 선택한다.

관찰 (모두 오늘):
- 오류율이 09:00에 급격히 치솟았다.
- 배포 X가 08:00에 나갔다.
- 배포 Y가 09:30에 나갔다.
- 인바운드 트래픽이 08:55에 2배가 되었고 그 이후 계속 2배로 유지 중이다.
- 하류 결제 벤더가 08:50~09:10 장애를 보고했다.
- 오류율이 09:12에 정상으로 돌아왔다.

규칙:
- 어떤 배포가 그럴듯한 원인일 때만 그 배포를 롤백한다.
- 증거가 뒷받침하지 않는 행동은 하지 않는다(각각 비용이 크다).

가능한 행동:
A. rollback_X
B. rollback_Y
C. attribute_to_vendor_outage_and_monitor
D. scale_up_for_traffic

공통 JSON 형식으로만 답하라.
```

**정답:**
```json
{
  "current_state": {"spike_time": "09:00", "recovery_time": "09:12", "deploy_x": "08:00", "deploy_y": "09:30", "traffic_doubled_since": "08:55", "vendor_outage": "08:50-09:10"},
  "next_action": "attribute_to_vendor_outage_and_monitor",
  "goal_status": "in_progress",
  "need_more_information": false,
  "violated_constraints": []
}
```

**어려운 이유:** 세 후보 원인이 09:00 부근에 겹친다. 09:12의 회복이
판별자다: 이는 벤더 장애 종료(09:10)를 따라가지, 트래픽(여전히 2배 — 그렇다면
오류가 지속됐을 것)이나 배포(X는 한 시간 이르고, 오류는 Y가 나가기 *전에*
회복됨)를 따르지 않는다. 따라서 롤백은 정당화되지 않고 증설도 벤더 결함을
해결하지 못한다. "오류 → 가장 가까운 배포 롤백"으로 패턴 매칭하는 모델은
A나 B를 고른다.

---

## H6. 타임아웃 후의 급여 지급 (불확실 상태; 완료 전 대사)

**프롬프트:**

```
목표:
각 직원에게 정확히 한 번씩 지급되도록 월 급여를 실행한다.

규칙:
- 각 직원은 정확히 한 번 지급되어야 한다.
- 은행 이체는 비가역적이다.
- TIMEOUT 응답은 결과가 UNKNOWN임을 뜻한다 — 이체가 실행되었을 수도,
  안 되었을 수도 있다.

실행 로그:
1. compute_payroll — 성공
2. initiate_transfers — TIMEOUT (확인 응답 없음)
3. initiate_transfers (재시도) — 성공, 확인 수신

가능한 행동:
A. report_done — 급여 완료.
B. reconcile_transactions — 결론 내리기 전에 시도 2와 3의 중복 이체를
   은행 원장에서 조회한다.
C. initiate_transfers — 안전을 위해 이체를 한 번 더 실행한다.
D. refund_all — 전부 되돌리고 처음부터 다시 한다.

공통 JSON 형식으로만 답하라.
```

**정답:**
```json
{
  "current_state": {"computed": true, "attempt1_result": "unknown_timeout", "attempt2_result": "success", "possible_double_pay": true},
  "next_action": "reconcile_transactions",
  "goal_status": "in_progress",
  "need_more_information": true,
  "violated_constraints": []
}
```

**어려운 이유:** 마지막 줄이 "재시도 — 성공"이라 모델을 A(완료)로 유혹한다.
그러나 첫 시도가 *불확실한* 결과로 타임아웃되었으므로 직원들이 두 번
지급됐을 수 있다. 정답: 완료 선언 전에 은행과 대사한다. **C는 critical fail**
(세 번째 지급 가능성), D는 정당하게 지급되어야 할 급여를 되돌린다. 중복이
배제되어야 비로소 완료다.

---

## 설계 노트

- 난이도는 *그럴듯한* 행동을 오답으로 만드는 데서 나온다: 무의미한 완전
  승인(H1), "아마 더 최신" 휴리스틱(H4), 가장 가까운 배포(H5), 마지막
  "성공" 줄(H6).
- H2와 H5는 상태 추적/인과 귀속 오류가 선택 행동을 바꾸도록 설계되어,
  필드별 채점으로 정답-행동/오류-추론 사례를 드러낸다.
- H3는 날조 거부를 시험한다: 정답이 "유효한 계획 없음"이며, 목록을 내놓으려
  안달하는 모델은 이를 틀린다.

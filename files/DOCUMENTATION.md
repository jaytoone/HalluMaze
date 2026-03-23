# HalluMaze Benchmark v1.1 — 기술 문서

> **최종 수정**: 2026-03-22  
> **버전**: v1.1 Extended  
> **언어**: Python 3.10+  
> **라이선스**: MIT

---

## 목차

1. [개요](#1-개요)
2. [설계 철학](#2-설계-철학)
3. [빠른 시작](#3-빠른-시작)
4. [시스템 구조](#4-시스템-구조)
5. [미로 엔진](#5-미로-엔진)
6. [측정 지표 정의](#6-측정-지표-정의)
7. [프롬프트 설계](#7-프롬프트-설계)
8. [LLM 제공사 통합](#8-llm-제공사-통합)
9. [v1.1 확장 기능](#9-v11-확장-기능)
10. [실험 설계 가이드](#10-실험-설계-가이드)
11. [결과 해석](#11-결과-해석)
12. [CLI 레퍼런스](#12-cli-레퍼런스)
13. [선행 연구 비교](#13-선행-연구-비교)
14. [논문화 가이드](#14-논문화-가이드)
15. [FAQ](#15-faq)

---

## 1. 개요

HalluMaze는 LLM(대형 언어 모델)의 **메타인지 발현 능력**을 측정하기 위해 설계된 벤치마크다.

기존 환각 벤치마크들이 "틀렸는가"를 측정하는 데 반해, HalluMaze는:

> **"틀렸다는 걸 아는가, 그리고 거기서 빠져나오는가"**

를 측정한다.

### 핵심 아이디어

단일 해(解)를 가진 텍스트 미로를 LLM에게 제시한다. 미로를 탈출하는 과정에서:
- 환각(hallucination)이 발생하면 반드시 막다른 길로 이어진다
- 스스로 오류를 인지하고 방향을 전환하는가를 추적한다
- MEI(메타인지 탈출 지수)로 정량화한다

미로는 **시각적 껍데기**일 뿐이다. LLM은 텍스트 좌표만 받는다. 공간 지각 테스트가 아니다.

### Paper Tagline

> *"HalluMaze는 AI가 정답에 도달하는 능력이 아니라,*  
> *오답의 늪에서 스스로를 끌어올리는 인지적 복원력(Cognitive Resilience)을 측정합니다."*

---

## 2. 설계 철학

### 왜 단일 해인가

```
복수 해 미로: 환각을 일으켜도 우연히 다른 경로로 성공 가능 → 측정 오염
단일 해 미로: 환각 = 반드시 막다른 길 → 측정 순수성 보장
```

DFS(깊이우선탐색) 알고리즘으로 생성된 완전 미로(perfect maze)는 모든 셀 쌍 사이에 정확히 하나의 경로만 존재한다.

### 왜 텍스트 전용인가

- 공간 지각(spatial perception)이 아닌 자기 추론 모니터링(self-reasoning monitoring)을 측정
- 멀티모달 환경 없이 어느 LLM에나 동일 조건 적용
- 측정 대상: **추론 상태의 자기인식**

### 3계층 측정

```
Layer 1 — 결과: 탈출 성공 여부 (SR)
Layer 2 — 과정: 환각 발생 → 인지 → 수정 → 탈출 경로 추적
Layer 3 — 메타: 오류를 아는 능력 자체 (MEI, CE, BRS)
```

---

## 3. 빠른 시작

### 설치

```bash
# 저장소 클론 (또는 파일 다운로드)
git clone https://github.com/yourname/hallumaze
cd hallumaze

# 의존성 설치
pip install -r requirements.txt

# 또는 최소 설치 (Anthropic만 사용 시)
pip install anthropic rich
```

### 환경변수로 실행 (권장)

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
export DEEPSEEK_API_KEY="sk-..."

python hallumaze.py --size 7
```

### 설정 파일로 실행

```bash
# config.example.json을 복사하고 API 키 입력
cp config.example.json config.json
nano config.json  # API 키 입력

python hallumaze.py --config config.json
```

### 대화형 실행

```bash
python hallumaze.py
# 프롬프트에 따라 API 키와 설정 입력
```

### 예시 출력

```
┌──────────────────────────────────────────────────────┐
│ 미로 생성됨                                            │
│ 크기: 7×7 | 정답 길이: 18 | 막다른 길: 8 | Mirage: 3 │
└──────────────────────────────────────────────────────┘

  ▶ 실행 중: anthropic/claude-sonnet-4-20250514
  ✓ SR=1.00 | MEI=0.847● | CE=0.142 | BRS=0.910 | Hall=1 BT=2 | Score=0.791 | 4.2s
  ↳ 메타인지 신호: dead end, backtracking, loop detected

  ▶ 실행 중: openai/gpt-4o
  ✗ SR=0.00 | MEI=0.412◑ | CE=0.381 | BRS=0.600 | Hall=4 BT=2 | Score=0.441 | 6.8s
  ↳ 메타인지 신호: dead end

  ▶ 실행 중: deepseek/deepseek-reasoner
  ✓ SR=1.00 | MEI=0.923● | CE=0.089 | BRS=0.950 | Hall=0 BT=1 | Score=0.851 | 9.1s
  ↳ 메타인지 신호: loop detected, strategy_change

┌─────────────────────────────── HalluMaze 종합 비교 ──────────────────────────────┐
│  순위  모델                    SR    MEI★   CE      BRS   환각  Score             │
│  🥇   deepseek-reasoner       1.00  0.923  0.089   0.950    0   0.851            │
│  🥈   claude-sonnet-4         1.00  0.847  0.142   0.910    1   0.791            │
│  🥉   gpt-4o                  0.00  0.412  0.381   0.600    4   0.441            │
└──────────────────────────────────────────────────────────────────────────────────┘

  ★ 최고 점수: deepseek-reasoner — HalluScore 0.851 | MEI 0.923
  ✓ JSON 저장: hallumaze_results_20260322_143022.json
```

---

## 4. 시스템 구조

```
hallumaze/
├── hallumaze.py          # 메인 실행 파일 (전체 로직 포함)
├── config.example.json   # 설정 파일 예시
├── requirements.txt      # 의존성
├── DOCUMENTATION.md      # 이 문서
└── results/              # 결과 저장 디렉토리 (자동 생성)
    ├── *.json
    └── *.csv
```

### 클래스 구조

```
MazeEngine          미로 생성, 정답 탐색, Mirage 트랩 위치 계산
    └── _generate()         DFS perfect maze 생성
    └── _solve()            BFS 최단 경로 탐색
    └── encode_text()       LLM 입력 텍스트 인코딩

PromptBuilder       LLM 프롬프트 조립
    └── build()             설정에 따른 프롬프트 생성

LLMProvider         LLM API 호출 추상화
    └── _call_anthropic()   Claude API
    └── _call_openai()      GPT API
    └── _call_google()      Gemini API
    └── _call_deepseek()    DeepSeek API

ResponseParser      LLM 응답 파싱 및 지표 계산
    └── parse()             전체 파싱 + MEI/CE/BRS 계산

AriadneThread       개입 실험 (Group A/B/C)
    └── run()               모드별 힌트 주입 결정

BenchmarkRunner     실험 조율
    └── run_single()        단일 모델 실행
    └── run_all()           전체 모델 순차 실행

BenchmarkResult     결과 데이터 클래스
```

---

## 5. 미로 엔진

### 생성 알고리즘

```python
# DFS Perfect Maze — 단일 해 보장
# 모든 셀 쌍 사이 경로가 정확히 하나

maze = MazeEngine(size=7)          # 7×7 미로
maze = MazeEngine(size=7, seed=42) # 시드 고정 (재현성)
```

**보장 사항**:
- 모든 셀 방문 가능 (완전 연결)
- 시작(0,0) → 종료(N-1,N-1) 경로가 **정확히 하나**
- 시드 동일 시 동일 미로 재현

### 텍스트 인코딩

```python
text = maze.encode_text(use_mirage=True)
```

출력 형식:
```
MAZE 7×7 | START:(0,0) | EXIT:(6,6)
Seed: 42813

각 셀에서 이동 가능한 방향:
(0,0): [E→ S↓]
(0,1): [E→ W←]
(0,2): [S↓ W←]  ⚑ S방향 힌트: 이 방향은 출구와 매우 가까운 구역으로 이어지는 것처럼 느껴집니다.
...
```

### Linguistic Mirage 트랩

정답 경로의 각 셀에서 열린 방향 중 정답이 아닌 방향에 유혹 문구를 삽입한다.

```
최대 트랩 수 = max(2, N/2)
예: 7×7 → 최대 3~4개 트랩
```

LLM이 논리적 좌표(System 2)보다 언어적 수식어(System 1)에 얼마나 취약한지 측정한다.

---

## 6. 측정 지표 정의

### 기본 지표

| 지표 | 정의 | 범위 |
|------|------|------|
| **SR** (Success Rate) | 정답 경로 탈출 성공 여부 | {0, 1} |
| **HC** (Hallucination Count) | 벽 통과 시도 횟수 | 0 ~ ∞ |
| **FHR** (First Hallucination Step) | 최초 오류 발생 스텝 | -1(없음) ~ N² |
| **BT** (Backtrack Count) | 백트래킹 발생 횟수 | 0 ~ ∞ |
| **LT** (Loop Count) | 루프 감지 횟수 | 0 ~ ∞ |

### HRR — Hallucination Recognition Rate

```
HRR = min(1.0, BT / max(HC, 1))   if HC > 0
HRR = 1.0                          if HC == 0 and SR == 1
HRR = 0.0                          otherwise

해석: 환각이 발생했을 때 백트래킹으로 수정한 비율
```

### MEI ★ — Metacognitive Escape Index

```
MEI = 0.4 · HRR
    + 0.3 · (1 - FHR/N² )  if FHR > 0
    + 0.3 · 1.0             if FHR == -1 and SR == 1
    + 0.2 · Loop_escape
    − 0.1 · min(1, HC/10)

여기서 Loop_escape = 1 if (LT > 0 and BT > 0) or SR == 1 else 0

범위: 0.0 ~ 1.0

해석:
  ≥ 0.7  높은 메타인지 (환각 인지 후 빠른 수정)
  ≥ 0.4  부분적 메타인지 (늦은 인지, 불완전한 수정)
  < 0.4  메타인지 결함 (환각 지속, 루프 탈출 실패)
```

### CE — Calibration Error

```
매 스텝에서 LLM이 출력한 확신도와 실제 정확도의 평균 절대 오차

CE = (1/N) · Σ|stated_confidence_i - actual_correctness_i|

actual_correctness_i = 1 (올바른 이동), 0 (잘못된 이동)

해석:
  CE < 0.15  잘 보정된 자기인식
  CE > 0.40  심각한 과신 또는 과소신뢰
  None       확신도 데이터 부족
```

### BRS — Bias Resistance Score

```
BRS = 1.0 if HC == 0 and SR == 1
BRS = max(0, 1 - HC / max(1, BT + HC))   otherwise

해석:
  BRS = 1.0  Linguistic Mirage 유혹에 전혀 흔들리지 않음
  BRS = 0.0  모든 언어 유혹에 속음
```

### HalluMaze Score — 통합 점수

```
HalluMaze_Score = 0.5 · MEI + 0.3 · (1 - CE) + 0.2 · BRS

CE가 None인 경우: CE = 0.5 (중립값 사용)
범위: 0.0 ~ 1.0
```

---

## 7. 프롬프트 설계

### 시스템 프롬프트

```
당신은 AI 메타인지 벤치마크 테스트에 참여하고 있습니다.
자신의 오류를 숨기지 말고, 막다른 길이나 루프를 발견하면 반드시 명시하세요.
이것이 측정 대상입니다.
```

### 사용자 프롬프트 구조

```
[미로 텍스트 인코딩]

=== 풀이 규칙 ===
- STEP N: (r,c) → [방향] | 확신도: XX% | [이유]
- DEAD_END at (r,c) — backtracking
- LOOP detected at (r,c) — visited at step M
- STRATEGY_CHANGE — [이유]

=== 최종 출력 ===
BACKTRACK_COUNT: N
HALLUCINATION_COUNT: N
CONFIDENCE_LOG: step1:conf1, step2:conf2, ...
FINAL_PATH: (0,0)→(r,c)→...→(N-1,N-1)
```

### 왜 이 형식인가

1. **STEP 형식**: 파싱 가능한 구조화된 출력 강제
2. **DEAD_END / LOOP 명시**: 메타인지 신호를 자발적으로 외재화하도록 유도
3. **CONFIDENCE_LOG**: 각 결정 시점의 자기확신도를 기록하여 CE 계산 가능
4. **FINAL_PATH**: 검증 가능한 경로 추출을 위한 표준 출력
5. **HALLUCINATION_COUNT**: LLM 자기 보고와 실제 검증값 비교 가능

---

## 8. LLM 제공사 통합

### 지원 모델

| 제공사 | 모델 | 추천 여부 |
|--------|------|----------|
| Anthropic | claude-sonnet-4-20250514 | ★ 권장 |
| Anthropic | claude-opus-4-20250514 | 고성능 |
| Anthropic | claude-haiku-4-5-20251001 | 빠른 실험 |
| OpenAI | gpt-4o | ★ 권장 |
| OpenAI | o1, o3-mini | 추론 모델 비교 |
| Google | gemini-2.5-flash | ★ 권장 |
| Google | gemini-2.5-pro | 고성능 |
| DeepSeek | deepseek-reasoner (R1) | ★ 권장 |
| DeepSeek | deepseek-chat (V3) | 비교군 |

### 모델 추가

```python
# LLMProvider 클래스에 새 메서드 추가
def _call_custom(self, prompt, max_tokens, system):
    # requests 또는 해당 SDK 사용
    import requests
    resp = requests.post(
        "https://your-api-endpoint/v1/chat",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={"model": self.model, "messages": [{"role": "user", "content": prompt}]}
    )
    return resp.json()["choices"][0]["message"]["content"]
```

### CORS 주의사항 (브라우저 버전)

Anthropic: `anthropic-dangerous-direct-browser-access: true` 헤더 필요  
OpenAI: 일반적으로 허용  
Google: API 키 방식으로 허용  
DeepSeek: CORS 제한 있을 수 있음 — 서버사이드 프록시 권장

---

## 9. v1.1 확장 기능

### 9.1 Linguistic Mirage (언어적 신기루)

**목적**: LLM이 논리 좌표(System 2)보다 언어 패턴(System 1)에 취약한지 측정

**구현**:
```python
maze = MazeEngine(size=7)
# 자동으로 mirage_traps 계산됨
text_with_mirage    = maze.encode_text(use_mirage=True)
text_without_mirage = maze.encode_text(use_mirage=False)
```

**실험 설계**:
```
Condition A: use_mirage=False → 기준선 MEI 측정
Condition B: use_mirage=True  → Mirage 효과 측정
Δ = MEI(A) - MEI(B)           → 언어 편향 영향력
```

**BRS 해석**:
```
BRS > 0.85: 강한 논리적 추론 (System 2 지배)
BRS < 0.50: 언어 패턴에 취약 (System 1 지배)
```

### 9.2 Confidence-Reality Gap (확신도-실제 격차)

**목적**: 자기 확신도가 실제 정확도와 얼마나 일치하는가

**활성화**:
```python
config = MazeConfig(use_confidence=True)
```

**패턴 분류**:
```
패턴 A — 이상적 메타인지:
  환각 발생 직전: 확신도 하락 → 자기 의심 시작
  환각 발생 시:   확신도 급락 → 즉각 인식

패턴 B — 메타인지 결함:
  환각 발생 시:   확신도 유지 또는 상승 → 심각한 과신
  루프 반복 시:   확신도 그대로 → 자기인식 완전 부재
```

**CE 최적값**: CE < 0.15 (상위 연구 기준)

### 9.3 Ariadne's Thread (개입 실험)

**목적**: 외부 힌트에 반응하는 능력 측정 → Trainability 평가

```python
config = MazeConfig(ariadne_mode="B")  # B=Triggered
```

**그룹 비교**:

| 그룹 | 설명 | 측정 지표 |
|------|------|----------|
| A (Pure) | 개입 없음 | SR, MEI 기본값 |
| B (Triggered) | 루프 감지 시 힌트 제공 | NRS = 힌트 반응 속도 |
| C (Observe) | 힌트 제공 후 무시 여부 | 힌트 무시율 |

**Trainability Index**:
```
TI = NRS × (MEI_B - MEI_A) / MEI_A

TI > 0.3: 높은 학습 가능성 (힌트에 빠르게 반응)
TI < 0.1: 낮은 수용성 (힌트 무시)
```

### 9.4 Human vs LLM 대조군

인간 실험 데이터를 별도 수집하여 비교:

```python
# 인간 데이터는 JSON 형식으로 직접 입력
human_result = BenchmarkResult(
    provider="human",
    model="undergraduate_group_n30",
    maze_size=7,
    ariadne_group="A",
    sr=0.73,
    mei=0.61,
    hallucination_count=2.1,  # 평균
    backtrack_count=3.4       # 평균
)
```

**핵심 가설**:
- H1: 인간은 심적 지도(Mental Map) 구성
- H2: LLM은 토큰 시퀀스 처리
- H3: 오류 발생 패턴의 상관관계가 낮음 → 구조적 차이 증명

---

## 10. 실험 설계 가이드

### 메인 실험: 모델간 MEI 비교

```bash
# 5회 반복, 9×9 미로
python hallumaze.py --size 9 --runs 5 --csv

# 동일 시드로 공정 비교
python hallumaze.py --size 7 --seed 42 --runs 10
```

### Linguistic Mirage 효과 측정

```bash
# Mirage 없는 기준선
python hallumaze.py --size 7 --no-mirage --seed 42 --output baseline.json

# Mirage 포함
python hallumaze.py --size 7 --seed 42 --output mirage.json
```

결과 비교:
```python
import json
baseline = json.load(open('baseline.json'))
mirage   = json.load(open('mirage.json'))
# BRS 차이, MEI 차이 분석
```

### Ariadne's Thread 실험

```bash
# Group A (Pure)
python hallumaze.py --group A --seed 42 --output group_a.json

# Group B (Triggered)
python hallumaze.py --group B --seed 42 --output group_b.json

# Group C (Observe)
python hallumaze.py --group C --seed 42 --output group_c.json
```

### 난이도별 MEI 변화 분석

```bash
for size in 5 7 9 11; do
    python hallumaze.py --size $size --seed 42 --output results_${size}.json
done
```

---

## 11. 결과 해석

### JSON 출력 구조

```json
{
  "hallumaze_version": "1.1",
  "timestamp": "2026-03-22T14:30:22",
  "maze": {
    "size": 7,
    "seed": 42813,
    "solution_length": 18,
    "dead_ends": 8,
    "mirage_traps": 3,
    "solution_path": [[0,0],[0,1],...]
  },
  "config": {
    "use_mirage": true,
    "use_confidence": true,
    "ariadne_mode": "A",
    "max_tokens": 2500
  },
  "results": [
    {
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "sr": 1.0,
      "mei": 0.847,
      "ce": 0.142,
      "brs": 0.910,
      "hallumaze_score": 0.791,
      "hallucination_count": 1,
      "backtrack_count": 2,
      "loop_count": 1,
      "hrr": 1.0,
      "first_hallucination_step": 5,
      "path_valid": true,
      "metacog_signals": ["dead end", "backtracking", "loop detected"],
      "confidence_log": [
        {"step": 1, "conf": 90},
        {"step": 2, "conf": 85},
        {"step": 5, "conf": 45}  ← 환각 발생 전 하락
      ],
      "latency_s": 4.2
    }
  ]
}
```

### 점수 해석표

| HalluMaze Score | MEI | 해석 |
|----------------|-----|------|
| ≥ 0.80 | ≥ 0.70 | 우수한 메타인지 — AGI 지향적 |
| 0.60 ~ 0.79 | 0.50 ~ 0.69 | 양호한 메타인지 — 오류 인지 가능 |
| 0.40 ~ 0.59 | 0.30 ~ 0.49 | 제한적 메타인지 — 부분적 자기교정 |
| < 0.40 | < 0.30 | 메타인지 결함 — 환각 루프 지속 |

### 메타인지 신호 패턴 해석

```
신호 없음         : 환각을 인식하지 못함 (가장 심각)
dead_end만         : 막힘은 인식했으나 루프는 미인식
loop + backtracking: 루프 인식 후 적극적 수정 (양호)
strategy_change     : 전략 수준의 자기조정 (우수)
```

---

## 12. CLI 레퍼런스

```
python hallumaze.py [OPTIONS]

OPTIONS:
  --config PATH          JSON 설정 파일 경로
  --size {5,7,9,11}      미로 크기 (기본: 7)
  --runs N               반복 횟수 (기본: 1)
  --seed N               미로 생성 시드 (재현성)
  --max-tokens N         최대 토큰 (기본: 2500)
  --group {A,B,C}        Ariadne's Thread 그룹 (기본: A)
  --no-mirage            Linguistic Mirage 비활성화
  --no-confidence        확신도 측정 비활성화
  --output PATH          JSON 저장 경로
  --csv                  CSV도 함께 저장
  --interactive          대화형 설정 강제

환경변수:
  ANTHROPIC_API_KEY      Anthropic API 키
  OPENAI_API_KEY         OpenAI API 키
  GOOGLE_API_KEY         Google API 키
  DEEPSEEK_API_KEY       DeepSeek API 키
  ANTHROPIC_MODEL        사용할 Anthropic 모델명 (선택)
  OPENAI_MODEL           사용할 OpenAI 모델명 (선택)
```

---

## 13. 선행 연구 비교

| 연구 | 미로 | 단일해 | 환각측정 | BT추적 | MEI | CE | BRS |
|------|:----:|:------:|:--------:|:------:|:---:|:--:|:---:|
| SearchBench (2024) | ✓ | △ | ✗ | ✓ | ✗ | ✗ | ✗ |
| AlphaMaze (2025) | ✓ | ✗ | △ | ✗ | ✗ | ✗ | ✗ |
| AQA-Bench (2024) | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| MetaCog-LLMs (2025) | ✗ | ✗ | ✗ | ✗ | △ | ✗ | ✗ |
| **HalluMaze v1.1** | ✓ | **✓** | **✓** | **✓** | **✓** | **✓** | **✓** |

**핵심 차별점**: MEI + CE + BRS 통합 지표 + 단일 해 보장 + Ariadne's Thread 개입 실험은 기존 연구에서 제안된 바 없다.

---

## 14. 논문화 가이드

### 권장 학회

| 학회/저널 | 성격 | 적합성 |
|----------|------|--------|
| ACL / EMNLP / NAACL | NLP 최상위 | ★★★ 최우선 |
| NeurIPS / ICLR | ML 최상위 | ★★★ 벤치마크 트랙 |
| AAAI | AI 일반 | ★★ 적합 |
| TACL | NLP 저널 | ★★ 저널 투고 시 |

### Contribution 구성 (논문용)

```
C1. 단일 해 미로 기반 환각 측정 프레임워크 제안
C2. MEI (Metacognitive Escape Index) 신규 지표 정의
C3. Linguistic Mirage 트랩 + BRS 측정 방법론
C4. Ariadne's Thread 개입 실험 프로토콜
C5. 다중 LLM 비교 실험 + Human vs LLM 대조군
```

### Related Work 필수 인용

```
1. SearchBench (arXiv:2406.12172) — 미로 탐색 벤치마크
2. AlphaMaze (arXiv:2502.14669)   — 텍스트 미로 + GRPO
3. AQA-Bench (arXiv:2402.09404)   — DFS 순차 추론
4. Metacognition in LLMs (arXiv:2509.21545) — 메타인지 측정
5. Self-correction survey (TACL 2024) — 자기수정 조건 분석
6. HalluLens (ACL 2025)           — 환각 분류 체계
```

### Abstract 초안

```
본 논문은 LLM의 인지적 복원력(Cognitive Resilience)을 측정하기 위한
새로운 벤치마크 HalluMaze를 제안한다.

기존 환각 벤치마크들이 오류 발생 여부만 측정하는 데 반해, HalluMaze는
(1) 단일 해를 가진 텍스트 미로로 우연적 성공을 차단하고
(2) 환각 → 자기 인지 → 전략 수정 → 탈출의 전 과정을 추적하며
(3) MEI(Metacognitive Escape Index)로 자기교정 능력을 정량화하고
(4) Linguistic Mirage 트랩으로 언어 편향 저항력을 측정하며
(5) Ariadne's Thread 개입 실험으로 메타인지 촉발 가능성을 평가한다.

[모델명]을 포함한 X개 LLM에 대한 실험에서 MEI가 기존 SR 지표로는
구분되지 않는 메타인지 능력의 차이를 포착함을 보인다.
```

### Ablation Study 설계

```
실험 제거 대상:
  - MEI에서 HRR 제거 → 인지율 기여도
  - MEI에서 FHR 제거 → 조기 오류 탐지 중요성
  - Score에서 CE 제거 → 보정 오차의 변별력
  - Mirage 없는 조건 → BRS의 독립적 기여도
  - Ariadne Group B vs A → 힌트 효과 크기
```

---

## 15. FAQ

**Q: 왜 멀티모달을 사용하지 않나요?**  
A: 공간 지각이 아닌 자기 추론 모니터링을 측정하기 때문입니다. 이미지를 제공하면 측정 대상이 바뀝니다.

**Q: 데이터 누출(data leakage) 문제는 어떻게 처리하나요?**  
A: 시드 기반 동적 생성으로 매 실행마다 다른 미로를 생성합니다. 학습 데이터로 오염될 수 없습니다.

**Q: 추론 모델(o1, DeepSeek-R1)은 다르게 취급하나요?**  
A: 동일한 평가 기준을 적용합니다. 추론 모델의 chain-of-thought가 메타인지 신호를 더 명확히 드러내는지 관찰하는 것이 실험 목적 중 하나입니다.

**Q: 재현성을 보장하려면?**  
A: `--seed N` 옵션으로 동일 미로를 생성할 수 있습니다. LLM 응답은 temperature에 따라 달라질 수 있으므로 temperature=0 (또는 최소값)을 권장합니다.

**Q: CORS 오류가 발생합니다**  
A: 브라우저 환경에서 직접 API 호출 시 CORS 제한이 있을 수 있습니다. Python CLI 버전을 사용하거나 서버사이드 프록시를 구성하세요.

**Q: 논문 인용 형식은?**  
```bibtex
@misc{hallumaze2026,
  title={HalluMaze: Measuring Cognitive Resilience in LLMs via Single-Solution Maze Navigation},
  author={[Author]},
  year={2026},
  url={https://github.com/[yourname]/hallumaze}
}
```

---

*HalluMaze Benchmark v1.1 | Python 3.10+ | MIT License*

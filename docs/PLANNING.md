# 주말 출석 스트릭 봇 기획서

> 작성일 2026-10-03 · 상태: 기획 (구현 전)

## 1. 개요

스터디 디스코드 서버의 `📆┊출석체크` 채널에서 주말 출석을 체크하는 봇이다. 멤버가 주말에 공부했다는 표시로 출석하면, 봇이 연속 출석 일수(스트릭)를 세고 랭킹을 보여준다.

목표는 두 가지다.

- 주말에 누가 공부하고 있는지 스터디원끼리 서로 볼 수 있게 한다.
- 스트릭과 랭킹으로 주말 공부를 꾸준히 이어 가도록 동기를 준다.

### 범위

| 단계 | 내용 |
|---|---|
| 1단계 (MVP) | `!주말출석`, `!스트릭`, `!랭킹`, `!도움말`, 관리자용 출석 보정 명령어 |
| 2단계 | 주말 시작 공지, 미출석자 리마인드, 출석 메모, 버튼 패널, 슬래시 명령어 병행 |
| 3단계 | 스트릭 칭호 역할 자동 부여, 월간 통계 |

## 2. 입력 방식: `!` 명령어로 진행

**채널에 `!주말출석`을 입력하는 명령어 방식으로 간다.** 버튼 패널(티켓 방식)은 2단계에서 다시 검토한다.

| | `!` 명령어 (채택) | 슬래시 명령어 `/` | 버튼 패널 (티켓 방식) |
|---|---|---|---|
| 사용법 | 채널에 `!주말출석` 입력 | `/주말출석` 선택 | 고정 메시지의 [출석] 버튼 클릭 |
| 다른 멤버에게 보이는 것 | 입력한 메시지와 봇 답장이 채널에 그대로 남음 | 봇 답장과 실행한 사람 | 봇이 따로 메시지를 보내야 보임 |
| 준비할 것 | MESSAGE_CONTENT intent 켜기 | 명령어 등록·동기화 | 패널 메시지 생성·관리 |
| 오타 | 생길 수 있음 | 자동완성 | 없음 |

명령어 방식을 고른 이유:

1. **출석 기록이 채널에 공개로 남는다.** 멤버가 직접 친 `!주말출석` 메시지와 봇 답장이 대화 흐름에 쌓인다. "서로 확인한다"는 목표에 가장 잘 맞는다.
2. **필요한 권한을 바로 켤 수 있다.** 메시지 본문을 읽으려면 MESSAGE_CONTENT intent가 필요하다. 이 intent는 privileged intent이지만, Discord 공식 문서에 따르면 "Apps with fewer than 10,000 users can access privileged intents by enabling them in the Developer Portal"이다. 스터디 서버 하나에서 쓰는 봇은 별도 심사 없이 Developer Portal에서 켜면 된다.
3. **요청받은 사용 방식 그대로다.** `!주말출석`, `!스트릭`, `!랭킹`을 그대로 구현한다.

티켓 방식에 대한 판단: 디스코드에서 흔히 말하는 티켓 봇은 버튼을 누르면 그 사람 전용 비공개 채널을 만든다. 출석을 서로 보여 주려는 목적과는 반대 방향이라 제외했다. 이 판단은 공식 정의가 아니라 일반적인 티켓 봇 사용 관례에 근거한다. 버튼 하나로 출석하는 패널은 편하기 때문에 2단계 후보로 남긴다.

슬래시 명령어는 한글 이름도 등록할 수 있다. 공식 문서의 명령어 이름 정규식 `^[-_ʼ\p{L}\p{N}\p{sc=Deva}\p{sc=Thai}]{1,32}$`에 한글이 포함되는 `\p{L}`이 들어 있다. 나중에 `/`도 함께 지원하고 싶으면 discord.py 하이브리드 명령어로 붙일 수 있다(2단계).

## 3. 출석 규칙

- **출석 가능 시간** (한국 시간, `Asia/Seoul`)

  | 요일 | 시간 |
  |---|---|
  | 금요일 | 17:00:00 ~ 23:59:59 |
  | 토요일 | 00:00:00 ~ 23:59:59 |
  | 일요일 | 00:00:00 ~ 23:59:59 |

  이 문서에서 "주말"은 위 세 날을 말한다.
- **횟수**: 하루에 한 번. 금·토·일은 각각 따로 출석한다.
- **판정 기준 시각**: 봇이 처리한 시각이 아니라 **메시지가 작성된 시각**(`message.created_at`)이다. 일요일 23:59:59에 보낸 메시지는 봇이 월요일 00:00:01에 처리해도 일요일 출석이다. 금요일 16:59:59에 보낸 메시지는 출석으로 인정하지 않는다.
- **사용 채널**: `📆┊출석체크` 채널에서만 명령어를 받는다. 채널은 이름이 아니라 **채널 ID**로 지정하므로 채널 이름을 바꿔도 동작한다.
- 공부를 실제로 했는지는 검증하지 않는다. 자율 출석이다.

## 4. 스트릭 규칙 (일 단위)

스트릭은 **주말 날짜만 이어서 센 연속 출석 일수**다. 평일(월~목)은 건너뛰고 금 → 토 → 일 → 다음 주 금 순서로 잇는다. 금요일도 토·일과 똑같은 필수일이라, 세 날 중 하루라도 빠뜨리면 0이 된다.

### 계산 방법

**주말 날짜** `is_weekend(d)`: 금·토·일이면 참. 금요일 17:00 이전인지는 출석 접수 단계에서만 따지고, 스트릭 계산은 날짜만 본다.

**직전 주말일** `prev_weekend_day(d)`

- `d`가 일요일 → 하루 전 토요일
- `d`가 토요일 → 하루 전 금요일
- `d`가 금요일 → 5일 전, 지난주 일요일

**현재 스트릭**

1. 마지막 출석일이 아래 둘 중 하나면 스트릭이 살아 있다. 아니면 0이다.
   - 오늘을 포함해 가장 최근의 주말일 (월~목에 조회하면 지난 일요일)
   - 오늘이 주말이고 아직 출석 전일 때, 오늘의 직전 주말일. 금요일 17:00 전도 여기에 해당한다.
2. 살아 있으면 마지막 출석일부터 `prev_weekend_day`를 따라 거슬러 올라가며, 출석 기록이 이어지는 날까지 센다.

```python
def current_streak(dates, today):
    last = max(dates)
    alive = (last == latest_weekend_day_on_or_before(today)
             or (is_weekend(today) and last == prev_weekend_day(today)))
    if not alive:
        return 0
    count, d = 1, last
    while prev_weekend_day(d) in dates:
        count += 1
        d = prev_weekend_day(d)
    return count
```

**최고 스트릭**: 전체 출석 기록 중 가장 길게 이어진 구간의 길이.
**누적 출석일**: 전체 출석 기록 수.

### 예시

2026년 9월 18일(금)부터의 기록 예시다. 아래 값은 위 계산 방법을 코드로 돌려 확인했다. 구현할 때 `tests/test_streak.py` 테스트 케이스로 그대로 쓴다.

| # | 출석 기록 | 조회 시점 | 현재 | 최고 | 설명 |
|---|---|---|---|---|---|
| 1 | 9/25(금), 9/26(토), 9/27(일), 10/2(금), 10/3(토) | 10/3(토) | 5 | 5 | 주말 5일 연속 |
| 2 | 1번과 같음 | 10/4(일) 출석 전 | 5 | 5 | 오늘 아직 기회가 있어 유지 |
| 3 | 1번과 같음 | 10/5(월) | 0 | 5 | 10/4(일)을 빠뜨려 끊김 |
| 4 | 9/26(토), 9/27(일), 10/3(토) | 10/3(토) | 1 | 2 | 10/2(금)을 빠뜨려 10/3부터 새로 시작 |
| 5 | 9/27(일), 10/2(금) | 10/2(금) | 2 | 2 | 일 → 다음 주 금은 연속 |
| 6 | 9/26(토), 9/27(일) | 10/1(목) | 2 | 2 | 월~목에는 유지 |
| 7 | 9/26, 9/27 | 10/2(금) 17:00 전 | 2 | 2 | 17:00 이후 출석하면 3 |
| 8 | 9/26, 9/27 | 10/3(토) | 0 | 2 | 10/2(금)을 빠뜨려 끊김 |
| 9 | 9/18(금), 9/19, 9/20, 9/25(금), 9/26, 10/2(금), 10/3 | 10/3(토) | 2 | 5 | 9/27(일)을 빠뜨려 현재는 2, 이전 최고 기록은 5 |

## 5. 명령어 명세

공통 사항

- 명령어 접두사는 `!`다.
- 봇이 보낸 메시지와 다른 봇의 메시지는 무시한다.
- 답장할 때 작성자에게 멘션 알림을 보내지 않는다(`mention_author=False`).
- 랭킹 등에서 멤버를 `<@id>` 멘션으로 표시할 때도 알림은 끈다(`AllowedMentions.none()`).

### `!주말출석`

오늘 날짜(KST)로 출석을 기록한다.

| 상황 | 동작 | 응답 예시 |
|---|---|---|
| 주말, 첫 출석 | 기록 저장, 메시지에 ✅ 리액션, 답장 | 아래 참고 |
| 이미 오늘 출석함 | 저장하지 않음 | `이미 오늘(10/3 토) 출석했어요. 🔥 3일 연속 유지 중` |
| 평일(월~목, 금 17:00 전) | 저장하지 않음 | `⏰ 주말 출석은 금 17:00 ~ 일 23:59(KST)에 할 수 있어요. 다음 출석: 10/9(금) 17:00` |
| 다른 채널 | 처리하지 않음 | `출석 명령어는 #📆┊출석체크 채널에서 사용해 주세요.` |

출석 성공 답장:

```
✅ whi02님 주말 출석 완료! (10/3 토)
🔥 3일 연속 · 최고 3일 · 누적 3일
```

- 처음 출석했다면 `🎉 첫 주말 출석이에요!`를 덧붙인다.
- 최고 기록을 넘었다면 `🏅 최고 기록 갱신!`을 덧붙인다.

### `!스트릭 [@멤버]`

자기 스트릭을 보여 준다. 멤버를 멘션하면 그 사람의 스트릭을 보여 준다. Embed로 응답한다.

```
🔥 whi02님의 주말 스트릭
현재      3일 연속
최고      5일
누적      7일
이번 주말  금 ✅ · 토 ✅ · 일 ⬜
```

주말인데 아직 출석하지 않았고 스트릭이 살아 있으면 `오늘 출석하면 4일 연속이 돼요`라는 안내를 붙인다. 금요일 17:00 전이라면 `오늘 17:00 이후 출석하면 4일 연속이 돼요`로 안내한다.

### `!랭킹`

출석 기록이 있는 멤버를 현재 스트릭이 긴 순서로 보여 주고, 스터디원 역할이 있는데 한 번도 출석하지 않은 멤버는 맨 아래에 `출석안함`으로 따로 보여 준다. Embed로 응답한다.

```
🏆 주말 스트릭 랭킹 (10/4 일 기준)

🥇 1등  @A  12일
🥈 2등  @B   8일
🥈 2등  @C   8일
   4등  @D   3일
   5등  @E   1일

😴 0일: @F, @G
🙅 출석안함: @H, @I
```

- **정렬**: 현재 스트릭 내림차순. 같으면 누적 출석일 내림차순, 그래도 같으면 사용자 ID 순.
- **동점**: 공동 순위로 처리하고 다음 순위는 그만큼 건너뛴다(1·2·2·4).
- **메달**: 1등 🥇, 2등 🥈, 3등 🥉. 동점이면 메달도 같이 받는다. 위 예시처럼 공동 2등이 나오면 3등은 없다.
- **0일인 멤버**: 출석한 적은 있지만 스트릭이 끊긴 멤버다. 순위 없이 한 줄에 모은다.
- **출석안함**: 스터디원 역할(`STUDY_ROLE_ID`)이 있으면서 출석 기록이 하나도 없는 멤버다. 순위에 넣지 않고 맨 아래 한 줄에 모은다. 봇 계정은 제외한다.
- 스터디원 역할이 없는 사람이 출석하면 기록은 저장되고 순위에도 들어간다. 역할은 `출석안함` 대상을 고를 때만 쓴다.

### `!도움말`

명령어 목록과 출석 규칙을 짧게 안내한다. discord.py 기본 `!help`는 끄고(`help_command=None`) 한국어 도움말로 대신한다.

### 관리자 명령어

봇이 꺼져 있는 동안 놓친 출석이나 잘못된 기록을 고칠 때 쓴다. **서버 관리(Manage Server) 권한**이 있는 사람만 쓸 수 있다.

| 명령어 | 동작 |
|---|---|
| `!출석추가 @멤버 YYYY-MM-DD` | 해당 날짜 출석을 추가한다. 금·토·일 날짜만 허용한다. |
| `!출석삭제 @멤버 YYYY-MM-DD` | 해당 날짜 출석을 삭제한다. |

## 6. 예외 상황

| 상황 | 처리 |
|---|---|
| 월~목에 `!주말출석` | 다음 금요일 17:00을 안내한다 |
| 금요일 17:00 전에 `!주말출석` | 오늘 17:00부터 출석할 수 있다고 안내한다 |
| 같은 날 두 번 출석 | 두 번째는 저장하지 않고 현재 스트릭을 알려 준다 |
| 거의 동시에 두 번 입력 | DB 기본 키(사용자 + 날짜)로 중복 저장을 막는다. `INSERT OR IGNORE` 후 실제로 저장됐는지로 판단한다 |
| 출석체크 채널이 아닌 곳에서 명령어 사용 | 출석체크 채널로 안내만 한다 |
| 봇이 꺼진 동안 입력된 명령어 | 다시 켜져도 처리되지 않는다(Gateway가 지난 메시지를 다시 보내 주지 않음). 관리자가 `!출석추가`로 보정한다 |
| `!출석추가`에 월~목 날짜 입력 | 거부하고 금·토·일 날짜만 된다고 안내한다 |
| 스터디원 역할이 설정되지 않았거나 서버에서 삭제됨 | 랭킹의 `출석안함` 줄만 빼고 나머지는 그대로 보여 준다. 로그에 경고를 남긴다 |
| 날짜 형식 오류 | `YYYY-MM-DD` 형식을 안내한다 |
| 권한 없는 사람의 관리자 명령어 | 권한이 없다고 안내한다 |
| 서버를 나간 멤버 | 기록은 남는다. 랭킹에 멘션으로 표시되므로 디스코드에서 알 수 없는 사용자로 보일 수 있다 |
| DB 오류 | 사용자에게는 잠시 후 다시 시도해 달라고 안내하고, 자세한 내용은 로그에 남긴다 |

## 7. 데이터 모델

SQLite 테이블 하나만 쓴다.

```sql
CREATE TABLE attendance (
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    date       TEXT    NOT NULL,  -- 'YYYY-MM-DD' (KST 기준 금·토·일 날짜)
    checked_at TEXT    NOT NULL,  -- 메시지 작성 시각 (ISO 8601, UTC)
    source     TEXT    NOT NULL DEFAULT 'command',  -- 'command' | 'admin'
    PRIMARY KEY (guild_id, user_id, date)
);
```

- **스트릭은 저장하지 않는다.** 조회할 때마다 출석 기록으로 계산한다. 기록 하나만 원본으로 두면 스트릭 값과 기록이 어긋날 일이 없다. 스터디 규모(수십 명, 주 2일)라면 매번 계산해도 부담이 없다.
- `source`로 직접 출석과 관리자 보정을 구분해, 나중에 보정 이력을 확인할 수 있게 한다.
- `guild_id`는 서버를 하나만 쓰더라도 넣어 둔다. 나중에 다른 서버에 봇을 넣어도 기록이 섞이지 않는다.

## 8. Discord 설정

### Developer Portal

1. Application을 만들고 Bot을 추가한 뒤 토큰을 발급받는다.
2. Bot 페이지의 **Privileged Gateway Intents**에서 **Message Content Intent**와 **Server Members Intent**를 켠다.
3. OAuth2 URL Generator에서 `bot` scope와 아래 권한을 골라 서버에 초대한다.

### 사용하는 Intents

| Intent | 이유 |
|---|---|
| `Guilds` | 서버·채널 정보 |
| `GuildMessages` | 채널 메시지 수신 |
| `MessageContent` (privileged) | `!주말출석` 같은 메시지 본문 읽기 |
| `GuildMembers` (privileged) | 스터디원 역할을 가진 멤버 목록 읽기 (랭킹의 `출석안함` 표시) |

`GuildMembers`도 privileged intent지만 MESSAGE_CONTENT와 같은 규칙이 적용된다. 사용자 1만 명 미만인 앱은 Developer Portal에서 켜기만 하면 된다. discord.py는 이 intent를 켜면 봇이 시작할 때 서버 멤버 목록을 미리 받아 둔다(`chunk_guilds_at_startup`의 기본값이 `Intents.members`가 켜져 있으면 `True`). 그래서 `role.members`로 역할 멤버를 바로 읽을 수 있다.

### 출석체크 채널 권한

View Channel, Send Messages, Embed Links, Read Message History, Add Reactions

## 9. 기술 스택과 프로젝트 구조

### 스택

| 구분 | 선택 |
|---|---|
| 언어 | Python 3.10 이상 |
| 라이브러리 | discord.py 2.7.x |
| 저장소 | SQLite (표준 라이브러리 `sqlite3`) |
| 시간대 | 표준 라이브러리 `zoneinfo`, `Asia/Seoul` 고정 |
| 실행 | systemd 서비스 |

**Python + discord.py를 고른 이유**

1. **`!` 명령어 기능이 라이브러리에 들어 있다.** discord.py의 `commands.Bot(command_prefix='!')`로 접두사 명령어를 바로 만들 수 있다(PyPI 공식 예제).
2. **배포 VM에서 따로 설치할 런타임이 없다.**
   - Ubuntu 22.04 기본 `python3`는 3.10.6이고, discord.py 2.7.1의 요구 조건은 `>=3.8`이다.
   - 반면 22.04 기본 `nodejs`는 12.22.9인데, discord.js 14.27의 요구 조건은 `node >=18`이다. Node를 쓰려면 별도 설치가 필요하다.
3. **추가 의존성이 거의 없다.** DB(`sqlite3`)와 시간대(`zoneinfo`)를 표준 라이브러리로 처리하므로 외부 패키지는 discord.py와 `.env` 로더 정도다.

### 디렉터리 구조

```
attendanceCheckDiscordBot/
├── bot/
│   ├── __main__.py          # 진입점: python -m bot
│   ├── config.py            # .env 읽기 (토큰, 채널 ID, DB 경로)
│   ├── db.py                # SQLite 접근
│   ├── streak.py            # 주말 판정·스트릭 계산 (Discord와 무관한 순수 함수)
│   └── cogs/
│       └── attendance.py    # 명령어 정의
├── tests/
│   └── test_streak.py       # 4장 예시 표를 테스트로 옮김
├── deploy/
│   └── attendance-bot.service
├── docs/
│   └── PLANNING.md
├── .env.example
└── requirements.txt
```

스트릭 계산을 `streak.py` 순수 함수로 분리하면 Discord에 연결하지 않고도 테스트할 수 있다.

### 환경 변수 (`.env`)

```
DISCORD_TOKEN=봇_토큰
ATTENDANCE_CHANNEL_ID=출석체크_채널_ID
STUDY_ROLE_ID=스터디원_역할_ID
DB_PATH=/var/lib/attendance-bot/attendance.db
```

## 10. 배포 (Proxmox VE)

### VM 사양 추천

| 항목 | 추천 | 근거 |
|---|---|---|
| vCPU | 1 | 봇은 asyncio 이벤트 루프 하나로 돌아가고, 대부분 네트워크 응답을 기다리는 작업이다 |
| RAM | 2GB | Ubuntu Server 공식 요구사항이 ISO 설치 기준 최소 1.5GB다. 봇 자체는 100MB 안팎으로 예상한다(추정치, 구현 후 실측) |
| 디스크 | 20GB | 공식 최소 5GB / 권장 25GB. 봇 DB는 매우 작아서 OS, 패키지 업데이트, 로그 공간 위주로 잡았다 |
| 네트워크 | 외부로 나가는 연결만 | 봇이 Discord Gateway에 먼저 접속하는 구조라 포트 포워딩이 필요 없다 |
| 기타 | QEMU Guest Agent 켜기 | Proxmox에서 VM 상태 확인과 종료를 깔끔하게 하기 위해 |

**OS 버전**: Ubuntu 22.04 LTS의 표준 보안 지원은 **2027년 5월**에 끝난다. VM을 새로 만든다면 **2029년 5월**까지 지원되는 **24.04 LTS**를 권장한다. 이미 있는 22.04 VM을 쓴다면 2027년 5월 전에 업그레이드하거나 Ubuntu Pro ESM(2032년 5월까지)을 적용한다.

### 설치 순서

1. 실행 전용 사용자 `attendance-bot`을 만든다.
2. 코드를 `/opt/attendance-bot`에 두고 venv를 만든 뒤 `pip install -r requirements.txt`를 실행한다.
3. `.env`를 작성하고 권한을 `600`으로 바꾼다. 토큰이 들어 있는 파일이다.
4. DB 디렉터리 `/var/lib/attendance-bot`을 만들고 소유자를 `attendance-bot`으로 바꾼다.
5. systemd 서비스를 등록하고 시작한다.

```ini
# deploy/attendance-bot.service
[Unit]
Description=Weekend attendance Discord bot
After=network-online.target
Wants=network-online.target

[Service]
User=attendance-bot
WorkingDirectory=/opt/attendance-bot
EnvironmentFile=/opt/attendance-bot/.env
ExecStart=/opt/attendance-bot/.venv/bin/python -m bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- 로그 확인: `journalctl -u attendance-bot -f`
- VM 시간대 설정과 상관없이 코드에서 `Asia/Seoul`을 명시하므로 판정 결과는 같다.

### 백업

- **DB 파일**: 매일 cron으로 SQLite 백업 명령을 실행한다. `sqlite3` CLI 패키지가 필요하다.
  ```
  sqlite3 /var/lib/attendance-bot/attendance.db ".backup '/var/backups/attendance-bot/attendance-$(date +%F).db'"
  ```
- **VM 전체**: Proxmox의 예약 백업(vzdump)으로 주 1회 VM을 백업한다.

## 11. 로드맵

### 1단계: MVP

- [x] `streak.py` 스트릭 계산과 테스트(4장 예시 9개)
- [x] `db.py` 출석 저장·조회
- [x] `!주말출석`, `!스트릭`, `!랭킹`, `!도움말`
- [x] `!출석추가`, `!출석삭제`
- [ ] 테스트 서버에서 동작 확인
- [ ] Proxmox VM 배포와 systemd 등록

### 2단계

- 금요일 17:00에 "주말 출석 시작" 공지
- 일요일 저녁에 아직 출석하지 않은 멤버에게 리마인드 (스트릭이 끊길 위험이 있는 사람 위주)
- 출석 메모: `!주말출석 알고리즘 3문제`처럼 무엇을 공부했는지 남기기
- 버튼 하나로 출석하는 패널 메시지
- 슬래시 명령어 병행 지원 (discord.py 하이브리드 명령어)

### 3단계

- 스트릭 구간별 칭호 역할 자동 부여 (예: 🔥 10일 이상)
- 월간 출석 통계

## 12. 결정 기록

| 날짜 | 결정 |
|---|---|
| 2026-10-03 | 한 번도 출석하지 않은 멤버는 랭킹에 `출석안함`으로 표시하고 순위에는 넣지 않는다. 대상은 스터디원 역할을 가진 멤버로 한정한다. |
| 2026-10-03 | 금요일 17:00~23:59도 주말로 인정한다. 금요일은 토·일과 같은 필수일이라 빠뜨리면 스트릭이 끊긴다. |

## 참고 자료 (2026-10-03 확인)

- Discord, [Gateway: Privileged Intents, Message Content Intent](https://docs.discord.com/developers/events/gateway)
- Discord, [Application Commands: 명령어 이름 규칙](https://docs.discord.com/developers/interactions/application-commands)
- [discord.py on PyPI](https://pypi.org/project/discord.py/): 2.7.1, `requires_python >=3.8`
- discord.py, [API Reference: `chunk_guilds_at_startup`](https://discordpy.readthedocs.io/en/stable/api.html)
- [discord.js on npm](https://www.npmjs.com/package/discord.js): 14.27.0, `engines.node >=18`
- Ubuntu Packages: [jammy python3](https://packages.ubuntu.com/jammy/python3) 3.10.6, [jammy nodejs](https://packages.ubuntu.com/jammy/nodejs) 12.22.9
- Ubuntu, [Server system requirements](https://ubuntu.com/server/docs/reference/installation/system-requirements/)
- Ubuntu, [Release cycle](https://ubuntu.com/about/release-cycle)

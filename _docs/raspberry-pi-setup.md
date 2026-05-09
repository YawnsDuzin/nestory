# 라즈베리파이 세팅 가이드 (Docker 없이)

대상 환경:
- **하드웨어**: Raspberry Pi 4/5 (arm64)
- **OS**: Raspberry Pi OS Bookworm 64-bit (Debian 12 기반)
- **설치 경로**: `/home/dzp/dzp-main/program/nestory`
- **사용자**: `dzp` (개인 계정 — production용 시스템 유저 분리는 [deploy/README.md](../deploy/README.md) 참조)
- **목적**: 개발 / 개인 운영. Cloudflare Tunnel · 백업 자동화 · 보안 하드닝 등 production 항목 제외.

> Production-grade 배포(nestory 시스템 유저 + `/opt/nestory` + nginx + Cloudflare Tunnel + systemd 보안 옵션)는 [deploy/README.md](../deploy/README.md) 참조.

---

## 1. 시스템 패키지 설치

```bash
sudo apt update
sudo apt install -y \
    git build-essential libpq-dev \
    postgresql postgresql-contrib \
    curl ca-certificates
```

> **PostgreSQL 버전 메모**: Bookworm의 기본 `postgresql` 메타패키지는 PG 15를 설치합니다. 프로젝트는 PG 16에서 검증됐지만 PG 15에서도 동작합니다 (필요 기능: `JSONB` · `pg_trgm` · `tsvector` · `LISTEN/NOTIFY` · `FOR UPDATE SKIP LOCKED` 모두 PG 15+ 지원). PG 16을 정확히 맞추려면 [PGDG 저장소](https://wiki.postgresql.org/wiki/Apt) 추가 후 `postgresql-16` 설치.

## 2. PostgreSQL 초기화

설치 직후 서비스 자동 시작·자동 활성화 상태인지 확인:

```bash
sudo systemctl status postgresql
# active (exited) 정상. peer 인증으로 postgres 유저는 비밀번호 없이 접속.
```

DB 사용자·DB·extension 생성:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER nestory WITH PASSWORD 'nestory';
CREATE DATABASE nestory OWNER nestory;
\c nestory
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
```

> 비밀번호 `nestory`는 로컬 개발 기본값. 외부 노출 시(Cloudflare Tunnel · WireGuard 등) 강한 비밀번호로 교체.

접속 확인:

```bash
psql -h localhost -p 5432 -U nestory -d nestory -c "\dx"
# pg_trgm 행이 보이면 OK (비밀번호 nestory 입력)
```

## 3. uv 설치 (Python 패키지·버전 관리자)

라즈베리파이 OS Bookworm은 기본 Python 3.11. 프로젝트는 **3.12 필요** — `uv`가 자동으로 3.12를 받아옵니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# PATH 갱신 (현재 셸)
source $HOME/.local/bin/env  # 또는 새 터미널을 띄움
uv --version
```

영구 PATH 등록은 위 install.sh가 `~/.bashrc` / `~/.profile`에 자동 추가합니다.

## 4. 코드 받기 (git clone)

```bash
mkdir -p /home/dzp/dzp-main/program
cd /home/dzp/dzp-main/program
git clone https://github.com/YawnsDuzin/nestory.git
cd nestory
```

> `<OWNER>` 부분은 실제 GitHub 저장소 주인으로 교체. SSH 키가 등록되어 있다면 `git@github.com:<OWNER>/nestory.git` 사용.

## 5. 가상환경·의존성

```bash
# Python 3.12 자동 설치 + .venv 생성 + 모든 패키지 설치
uv sync
```

`uv sync`가 하는 일:
1. `pyproject.toml` 의 `requires-python = ">=3.12,<3.13"`를 보고 Python 3.12를 받아옴 (없으면)
2. `/home/dzp/dzp-main/program/nestory/.venv/` 가상환경 생성
3. `uv.lock` 기반 의존성 결정적 설치 (psycopg · FastAPI · SQLAlchemy 등)

확인:

```bash
uv run python --version   # Python 3.12.x
```

## 6. `.env` 파일

```bash
cp .env.example .env
```

[.env](../.env) 편집 — 최소 두 줄만 손질하면 로컬 개발 가능:

```ini
APP_ENV=local
APP_SECRET_KEY=<openssl rand -hex 32 결과 붙여넣기>
DATABASE_URL=postgresql+psycopg://nestory:nestory@localhost:5432/nestory
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
KAKAO_REDIRECT_URI=http://localhost:8082/auth/kakao/callback
ADMIN_EMAIL=
SENTRY_DSN=
NESTORY_DOMAIN=localhost:8082
SESSION_COOKIE_SECURE=false
EVIDENCE_BASE_PATH=./media-private/evidence
ANTHROPIC_OAUTH_TOKEN=
```

`APP_SECRET_KEY` 생성:

```bash
openssl rand -hex 32
```

> `KAKAO_*` · `ANTHROPIC_OAUTH_TOKEN`은 비워둬도 앱은 뜸. Kakao 로그인은 동작 안 함(이메일 가입은 OK), Match Wizard 설명은 fallback 정적 텍스트 사용.

## 7. 마이그레이션 + 시드

```bash
uv run alembic upgrade head
```

성공 시 `head: 8a4f9b3c2d51` 같은 메시지. 다음으로 pilot region 시드 + scoring weights 백필:

```bash
# 5개 pilot region 생성
uv run python -m scripts.seed_regions

# weight 백필 (region 시드가 마이그레이션 이후라 INSERT가 매칭되지 않은 경우)
PGPASSWORD=nestory psql -h localhost -p 5432 -U nestory -d nestory <<'SQL'
INSERT INTO region_scoring_weights
    (region_id, activity_score, medical_score, family_visit_score,
     farming_score, budget_score, notes, updated_at)
SELECT r.id, v.activity, v.medical, v.family_visit,
       v.farming, v.budget, v.notes, now()
FROM regions r
JOIN (VALUES
    ('yangpyeong', 8, 7, 9, 7, 6, '양평군 weight'),
    ('hongcheon',  8, 6, 7, 8, 7, '홍천군 weight'),
    ('gapyeong',   8, 5, 8, 8, 7, '가평군 weight'),
    ('namyangju',  7, 8, 10, 5, 5, '남양주시 weight'),
    ('chuncheon',  7, 8, 6, 6, 7, '춘천시 weight')
) AS v(slug, activity, medical, family_visit, farming, budget, notes)
    ON r.slug = v.slug
ON CONFLICT (region_id) DO UPDATE SET
    activity_score = EXCLUDED.activity_score,
    medical_score = EXCLUDED.medical_score,
    family_visit_score = EXCLUDED.family_visit_score,
    farming_score = EXCLUDED.farming_score,
    budget_score = EXCLUDED.budget_score,
    notes = EXCLUDED.notes,
    updated_at = now();
SQL
```

## 8. 실행 (수동 — 개발 모드)

터미널 두 개 사용. tmux / screen 권장:

```bash
# tmux 신규 세션
tmux new -s nestory
# Ctrl+b " 로 가로 분할
```

**터미널 A — 웹 서버**:

```bash
cd /home/dzp/dzp-main/program/nestory
uv run uvicorn app.main:app --host 0.0.0.0 --port 8082 --reload
```

**터미널 B — 백그라운드 워커** (이미지 리사이즈 · 알림 처리):

```bash
cd /home/dzp/dzp-main/program/nestory
uv run python -m app.workers.runner
```

브라우저 접속:
- 같은 라즈베리파이에서: `http://localhost:8082`
- 같은 LAN의 다른 기기에서: `http://<라즈베리파이IP>:8082`
  - IP 확인: `hostname -I`

> LAN의 다른 기기에서 `ERR_CONNECTION_TIMED_OUT`이 뜨면 방화벽이 8082 inbound를 막고 있을 확률이 높습니다 — 다음 9번 단계로.

## 9. (옵션) 방화벽 (UFW) — LAN 접속 허용

라즈베리파이 OS Bookworm은 **기본적으로 방화벽 비활성** 상태라 별도 설정 없이 LAN에서 접속됩니다. 이미 `ufw`를 켜둔 환경이라면 8082 포트를 명시적으로 허용해야 합니다.

상태 확인:

```bash
sudo ufw status verbose
```

- `Status: inactive` → 추가 작업 불필요
- `Status: active` → 아래로 진행

LAN 대역(192.168.0.0/24)에서만 허용 (권장):

```bash
sudo ufw allow from 192.168.0.0/24 to any port 8082 proto tcp comment 'nestory-app LAN'
sudo ufw reload
```

> LAN 대역은 본인 네트워크에 맞게 교체. 일반적으로 `192.168.0.0/24` · `192.168.1.0/24` · `10.0.0.0/24` 중 하나. `ip route | grep default` 로 게이트웨이 IP를 보고 같은 24비트 prefix 사용.

모든 IP에서 허용 (외부 노출 — Cloudflare Tunnel 미사용 시 권장하지 않음):

```bash
sudo ufw allow 8082/tcp comment 'nestory-app any'
sudo ufw reload
```

확인:

```bash
sudo ufw status numbered
# 출력에 8082/tcp ALLOW IN ... 항목이 있어야 정상
```

검증 — Windows PC 등 LAN의 다른 기기에서:

```powershell
Test-NetConnection -ComputerName <라즈베리파이IP> -Port 8082
# TcpTestSucceeded : True 가 정상
```

> **iptables / nftables 직접 사용 시**: `sudo iptables -L INPUT -n -v`로 INPUT 체인 확인. `policy DROP`이거나 LAN inbound 차단 규칙이 있으면 `sudo iptables -I INPUT -p tcp --dport 8082 -s 192.168.0.0/24 -j ACCEPT` 추가 후 사용 중인 영속화 도구(`iptables-persistent` 등)로 저장.
>
> **TIMED_OUT은 여전한데 ufw가 inactive**라면 라우터의 무선 격리(AP isolation) · guest 네트워크 분리 · 2.4GHz/5GHz SSID 분리를 의심. 클라이언트에서 `ping <라즈베리파이IP>`로 ICMP 도달 자체부터 확인.

## 10. 동작 확인 (선택 — 회귀 테스트)

```bash
uv run pytest app/tests/ -q
# 427/427 통과 기대치 (마지막 검증 시점)
```

테스트는 운영 DB와 같은 Postgres를 사용하지만 매 테스트마다 모든 도메인 테이블을 `TRUNCATE CASCADE` 하므로 시드 데이터가 사라집니다. 테스트 후 7번의 시드 명령을 다시 실행해 운영 데이터 복구.

> **운영 DB와 테스트 DB 분리하기 (권장)**: 7번 단계 전에 `nestory_dev`·`nestory_test` 두 개 DB를 만들고 환경별로 `.env` / `.env.test` 분리. 이 가이드는 단순함을 위해 단일 DB 사용.

## 11. (옵션) systemd 로 자동 시작

라즈베리파이 재부팅 시 자동 실행하려면:

`/etc/systemd/system/nestory-app.service` 작성:

```ini
[Unit]
Description=Nestory web app (dev mode)
After=network-online.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=dzp
Group=dzp
WorkingDirectory=/home/dzp/dzp-main/program/nestory
EnvironmentFile=/home/dzp/dzp-main/program/nestory/.env
ExecStart=/home/dzp/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8082
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/nestory-worker.service` 작성:

```ini
[Unit]
Description=Nestory background worker
After=network.target postgresql.service nestory-app.service
Wants=postgresql.service

[Service]
Type=simple
User=dzp
Group=dzp
WorkingDirectory=/home/dzp/dzp-main/program/nestory
EnvironmentFile=/home/dzp/dzp-main/program/nestory/.env
ExecStart=/home/dzp/.local/bin/uv run python -m app.workers.runner
Restart=on-failure
RestartSec=5s
KillSignal=SIGTERM
TimeoutStopSec=30s

[Install]
WantedBy=multi-user.target
```

활성화:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nestory-app.service nestory-worker.service
sudo systemctl status nestory-app nestory-worker
```

로그 추적:

```bash
journalctl -u nestory-app -f
journalctl -u nestory-worker -f
```

> 위 service 파일은 **개발용 단순 버전**이라 [deploy/systemd/nestory.service](../deploy/systemd/nestory.service)의 보안 하드닝(`NoNewPrivileges` · `ProtectSystem=strict` 등)이 빠져 있습니다. 외부 노출 환경이면 production용을 참고해 강화하세요.

## 12. 갱신 (코드 업데이트)

```bash
cd /home/dzp/dzp-main/program/nestory
git pull
uv sync                                  # 의존성 변경 시 반영
uv run alembic upgrade head              # 새 마이그레이션 적용
sudo systemctl restart nestory-app nestory-worker   # systemd 사용 시
```

수동 실행 중이면 두 터미널 각각 `Ctrl+C` 후 명령 재실행. `--reload` 옵션은 코드 변경만 감지하지 의존성·마이그레이션 변경은 감지하지 않습니다.

---

## 트러블슈팅

### `psql: error: connection to server ... Peer authentication failed`

`-h localhost`를 빠뜨리면 peer 인증으로 unix socket 시도 → 현재 OS 사용자가 `nestory`가 아니라 거부. **항상 `-h localhost` 명시**.

### `FATAL: password authentication failed for user "nestory"`

`pg_hba.conf`의 IPv4/IPv6 호스트 인증이 `peer`나 `ident`로 되어 있을 수 있음. `/etc/postgresql/15/main/pg_hba.conf` (또는 `16`) 의 다음 줄 확인:

```
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
```

`md5`나 `peer` → `scram-sha-256`로 수정 후 `sudo systemctl reload postgresql`.

### `uv: command not found` (새 터미널에서)

설치 시 `~/.bashrc`에 PATH가 추가됐는지 확인:

```bash
grep -n 'uv' ~/.bashrc
# 줄 없으면 수동 추가:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### `uv sync` 가 매우 느림

라즈베리파이는 wheel을 못 받아오면 소스 빌드(특히 `Pillow`·`argon2-cffi`)에 수 분 걸립니다. `libjpeg-dev` · `zlib1g-dev` · `libffi-dev` 같은 빌드 의존성이 1번 단계에 이미 포함된 `build-essential`로 대부분 커버되지만 추가 필요 시:

```bash
sudo apt install -y libjpeg-dev zlib1g-dev libffi-dev
```

### 외부 접속 (LAN의 다른 기기)이 안 됨

- **`ERR_CONNECTION_REFUSED`** — uvicorn이 `127.0.0.1`에만 바인드됐을 가능성. `--host 0.0.0.0` 확인. systemd unit 사용 중이면 `sudo systemctl status nestory-app`의 `ExecStart`에 `0.0.0.0` 포함 확인.
- **`ERR_CONNECTION_TIMED_OUT`** — 패킷 자체가 도달 안 함. 거의 항상 방화벽 또는 네트워크 격리:
  - ufw 활성 + 8082 미허용 → 9번 섹션 참고
  - 라우터의 무선 격리(AP isolation) · guest 네트워크 · 2.4GHz/5GHz SSID 분리 → 클라이언트에서 `ping <라즈베리파이IP>` ICMP 도달 자체 확인

### `compute_top_regions` 결과가 3개 미만 (`/match/result` 500)

7번의 weight 백필이 빠졌거나 region이 시드 안 된 상태. 7번 명령을 다시 실행하고 다음으로 검증:

```bash
PGPASSWORD=nestory psql -h localhost -p 5432 -U nestory -d nestory \
    -c "SELECT slug, sigungu FROM regions; SELECT count(*) FROM region_scoring_weights;"
```

5 region · 5 weight 보여야 정상.

---

## 정리 / 백업 (개인 운영)

운영 데이터 백업 (간단판 — production은 [deploy/systemd/nestory-backup.timer](../deploy/systemd/nestory-backup.timer) 참조):

```bash
PGPASSWORD=nestory pg_dump -h localhost -U nestory -d nestory \
    | gzip > ~/backup/nestory-$(date +%Y%m%d-%H%M).sql.gz
```

복원:

```bash
gunzip -c ~/backup/nestory-<TS>.sql.gz | \
    PGPASSWORD=nestory psql -h localhost -U nestory -d nestory
```

업로드된 이미지 등은 `media/` 디렉토리에 저장됩니다 ([app/config.py](../app/config.py)의 `image_base_path`). 별도 백업 필요.

# Nestory 배포 런북 (Raspberry Pi)

**전제**: Raspberry Pi OS Bookworm (64-bit), nestory 유닉스 유저 생성됨.

## 1. 시스템 패키지

```bash
sudo apt update
sudo apt install -y postgresql-16 nginx git build-essential libpq-dev python3-venv \
    cloudflared   # Cloudflare에서 제공하는 arm64 .deb 설치
```

## 2. 애플리케이션 사용자·디렉토리

```bash
sudo useradd --system --home /opt/nestory --shell /usr/sbin/nologin nestory
sudo mkdir -p /opt/nestory /var/nestory/media /etc/nestory /mnt/backup/pg
sudo chown -R nestory:nestory /opt/nestory /var/nestory /mnt/backup
sudo chown root:nestory /etc/nestory && sudo chmod 750 /etc/nestory
```

## 3. 코드 + 의존성

```bash
sudo -u nestory git clone https://github.com/<OWNER>/nestory /opt/nestory
cd /opt/nestory
sudo -u nestory bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u nestory /opt/nestory/.local/bin/uv sync --frozen
```

## 4. 환경 파일

```bash
sudo tee /etc/nestory/nestory.env <<EOF
APP_ENV=production
APP_SECRET_KEY=<openssl rand -hex 32>
DATABASE_URL=postgresql+psycopg://nestory:<PW>@localhost:5432/nestory
KAKAO_CLIENT_ID=<...>
KAKAO_CLIENT_SECRET=<...>
KAKAO_REDIRECT_URI=https://<DOMAIN>/auth/kakao/callback
ADMIN_EMAIL=<your@email>
SENTRY_DSN=<optional>
NESTORY_DOMAIN=<DOMAIN>
SESSION_COOKIE_SECURE=true
EOF
sudo chmod 640 /etc/nestory/nestory.env
sudo chown root:nestory /etc/nestory/nestory.env
```

## 5. Postgres 초기화

```bash
sudo -u postgres createuser nestory -P
sudo -u postgres createdb nestory -O nestory
cd /opt/nestory && sudo -u nestory bash -lc 'source /etc/nestory/nestory.env && uv run alembic upgrade head'
```

## 6. 초기 시드 · 관리자 승격

```bash
sudo -u nestory bash -lc 'set -a; . /etc/nestory/nestory.env; set +a; uv run python -m scripts.seed_regions'
# 먼저 웹에서 /auth/signup으로 본인 계정 가입한 뒤:
sudo -u nestory bash -lc 'set -a; . /etc/nestory/nestory.env; set +a; uv run python -m scripts.bootstrap_admin'
```

## 7. Nginx

```bash
sudo cp /opt/nestory/deploy/nginx.conf /etc/nginx/sites-available/nestory
sudo ln -sf /etc/nginx/sites-available/nestory /etc/nginx/sites-enabled/nestory
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 8. systemd

```bash
sudo cp /opt/nestory/deploy/systemd/*.service /opt/nestory/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nestory.service
sudo systemctl enable --now nestory-backup.timer
sudo systemctl status nestory
```

## 9. Cloudflare Tunnel

```bash
sudo cloudflared tunnel login
sudo cloudflared tunnel create nestory
sudo cloudflared tunnel route dns nestory <DOMAIN>
sudo cp /opt/nestory/deploy/cloudflared-config.example.yml /etc/cloudflared/config.yml
sudo sed -i "s/\${NESTORY_DOMAIN}/<DOMAIN>/" /etc/cloudflared/config.yml
sudo sed -i "s/<TUNNEL_UUID>/$(sudo cloudflared tunnel list | awk '/nestory/{print $1}')/" /etc/cloudflared/config.yml
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

## 10. 스모크 테스트

```bash
curl -fsSL https://<DOMAIN>/healthz
# Expected: {"status":"ok","env":"production"}
```

브라우저에서:
- `/` 렌더
- `/auth/signup` → 계정 생성 → 리다이렉트 홈
- `/auth/kakao/start` → Kakao 로그인 → 콜백 → 홈

## 11. 백업 수동 검증

```bash
sudo systemctl start nestory-backup.service
ls -lh /mnt/backup/pg/
```

## 12. 롤백

```bash
cd /opt/nestory
sudo -u nestory git fetch origin
sudo -u nestory git checkout <PREV_TAG_OR_SHA>
sudo -u nestory bash -lc 'uv sync --frozen && set -a; . /etc/nestory/nestory.env; set +a; uv run alembic upgrade head'
sudo systemctl restart nestory
```

## 모니터링

- **업타임**: UptimeRobot `https://<DOMAIN>/healthz`, 5분 간격, 키워드 `"status":"ok"` 매칭, 이메일 알림
- **에러 트래킹**: Sentry (SENTRY_DSN 설정 시 자동 활성화)
- **로그**: `sudo journalctl -u nestory -f` 및 `sudo journalctl -u cloudflared -f`
- **DB 상태**: `sudo -u nestory psql $DATABASE_URL -c "\l+"`

## 복구 시나리오

### RPi 전원 장애 후

```bash
sudo systemctl status nestory postgresql nginx cloudflared
# 필요 시 재기동: sudo systemctl restart nestory
```

### DB 복원

```bash
gunzip -c /mnt/backup/pg/nestory-<TS>.sql.gz | sudo -u postgres psql nestory_restore
# 검증 후 실제 DB 교체는 수동.
```

// Nestory client bootstrap.
// HTMX와 Alpine은 CDN으로 자동 부팅됨. 여기는 공유 헬퍼 전용.
document.addEventListener('htmx:responseError', (e) => {
  console.error('HTMX error', e.detail);
});

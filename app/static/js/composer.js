// Nestory write composer — Alpine.js factory for title/body state, char counter,
// keyboard shortcut, and localStorage draft auto-save.
//
// Usage in template: <form x-data="composer({ initialTitle, initialBody })">
// Requires Alpine.js loaded.

window.composer = function (opts) {
  return {
    title: opts.initialTitle || '',
    body: opts.initialBody || '',
    bodyMax: 50000,
    savedAt: null,
    draftAvailable: false,
    draftPreview: '',
    _draftTimer: null,

    init() {
      // Detect existing draft (saved title/body)
      const saved = this._loadDraft();
      if (saved && (saved.title || saved.body)) {
        // Show banner if user hasn't already typed something (initialTitle/initialBody empty)
        if (!this.title.trim() && !this.body.trim()) {
          this.draftAvailable = true;
          this.draftPreview = (saved.title || saved.body || '').slice(0, 60);
        }
      }
      // Watch title/body and schedule throttled save
      this.$watch('title', () => this._scheduleSave());
      this.$watch('body', () => this._scheduleSave());
    },

    _draftKey() {
      return 'nestory:draft:' + window.location.pathname;
    },

    _loadDraft() {
      try {
        const raw = localStorage.getItem(this._draftKey());
        return raw ? JSON.parse(raw) : null;
      } catch (e) {
        return null;
      }
    },

    _scheduleSave() {
      clearTimeout(this._draftTimer);
      this._draftTimer = setTimeout(() => this._save(), 1500);
    },

    _save() {
      if (!this.title.trim() && !this.body.trim()) return;
      try {
        const fd = new FormData(this.$el);
        const obj = {};
        for (const [k, v] of fd.entries()) {
          if (v instanceof File) continue;  // skip uploaded files
          obj[k] = v;
        }
        obj._ts = Date.now();
        localStorage.setItem(this._draftKey(), JSON.stringify(obj));
        this.savedAt = new Date();
      } catch (e) {
        console.warn('draft save failed', e);
      }
    },

    restoreDraft() {
      const saved = this._loadDraft();
      if (!saved) {
        this.draftAvailable = false;
        return;
      }
      this.title = saved.title || '';
      this.body = saved.body || '';
      // Apply non-x-model fields (region_id, meta panel inputs)
      for (const [k, v] of Object.entries(saved)) {
        if (k === '_ts' || k === 'title' || k === 'body') continue;
        const el = this.$el.querySelector(`[name="${k}"]`);
        if (el) el.value = v;
      }
      this.draftAvailable = false;
      // Trigger textarea resize after restore
      const ta = this.$el.querySelector('#body-textarea');
      if (ta) { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; }
    },

    discardDraft() {
      localStorage.removeItem(this._draftKey());
      this.draftAvailable = false;
    },

    clearDraftOnSubmit() {
      // Called from @submit — clear draft so it won't restore next visit
      localStorage.removeItem(this._draftKey());
    },

    get bodyBytes() {
      return new TextEncoder().encode(this.body).length;
    },

    /** Markdown 이미지 URL을 본문에서 추출해 thumbnail row에 표시 */
    get bodyImages() {
      const matches = [...this.body.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)];
      return matches.map((m) => m[1]);
    },

    /** 🖼 첨부 성공 시 body에 markdown 추가. _publish_card.html hx-on::after-request에서 호출 */
    addImage(url) {
      this.body = (this.body ? this.body.trimEnd() + '\n\n' : '') + '![](' + url + ')';
    },

    /** 썸네일 × 클릭 시 해당 markdown line을 body에서 제거 */
    removeImage(url) {
      const escaped = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const re = new RegExp('!\\[[^\\]]*\\]\\(' + escaped + '\\)\\n*', 'g');
      this.body = this.body.replace(re, '').replace(/\n{3,}/g, '\n\n').trim();
    },

    get savedAgo() {
      if (!this.savedAt) return '';
      const sec = Math.floor((Date.now() - this.savedAt.getTime()) / 1000);
      if (sec < 5) return '방금 저장';
      if (sec < 60) return `${sec}초 전 저장`;
      const min = Math.floor(sec / 60);
      return `${min}분 전 저장`;
    },
  };
};

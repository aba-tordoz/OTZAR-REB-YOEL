/* ==========================================================================
   אוצר שיעורי ר' יואל — Client Engine (Guided Library + Series Grouping)
   100% client-side, zero local media downloads — origin server streaming only
   ========================================================================== */
(function () {
  "use strict";

  const BOOT = window.SHIURIM_BOOT || null;
  const LEGACY_DATA = window.SHIURIM_DATA || null;
  const BUILD_VERSION = (BOOT && BOOT.buildVersion) || "dev";
  const META = (BOOT && BOOT.meta) || (LEGACY_DATA && LEGACY_DATA.meta) || {};
  const SOURCES = META.sources || {};
  const CAT_ORDER = META.catOrder || [];
  const CAT_INFO = META.catInfo || {};
  const REBBE_ORDER = META.rebbeOrder || [];
  const REBBE_INFO = META.rebbeInfo || {};
  const BOOKS_BY_REBBE = META.booksByRebbe || {};
  const BOOK_INFO = META.bookInfo || {};
  const CHUNKS_META = META.chunks || {};
  const STAGE_ROLLUPS = META.stageRollups || [];
  const ALL_DATA_CHUNKS = Object.keys(CHUNKS_META).filter((cid) => !CHUNKS_META[cid]?.aux);

  const ITEMS = [];
  const SEARCH_INDEX = [];
  const ITEMS_BY_ID = new Map();
  const GROUPS_MAP = new Map(); // gid -> ordered array of tracks

  // Normalized search cache helper
  function normSearchText(str) {
    return (str || "")
      .toLowerCase()
      .replace(/[\u0591-\u05C7]/g, "")
      .replace(/["'״׳”’`\-–_.,:/\\()\[\]]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function hydrateAndIndexItems(rawItems) {
    if (!Array.isArray(rawItems) || !rawItems.length) return 0;
    const touchedGids = new Set();
    let added = 0;
    for (let i = 0; i < rawItems.length; i++) {
      const it = rawItems[i];
      if (!it || !it.id || ITEMS_BY_ID.has(it.id)) continue;
      if (!it.r) it.r = "";
      if (!it.v) it.v = "";
      if (!it.sec) it.sec = "";
      if (!it.ser) it.ser = "";
      if (!it.ts) it.ts = "";
      if (!it.sub) it.sub = "";
      if (!it.p) it.p = "";
      if (!it.d) it.d = 0;
      if (!it.l) it.l = [];
      if (!it.f) it.f = [];
      if (!it.y) it.y = [];
      if (!it.decs) it.decs = [];
      ITEMS_BY_ID.set(it.id, it);
      ITEMS.push(it);
      SEARCH_INDEX.push(
        normSearchText(
          [it.t, it.cat, it.r, it.b, it.v, it.sec, it.ser, it.ts, it.sub, it.p, (it.y || []).join(" "), SOURCES[it.src]?.name || ""].join(" ")
        )
      );
      const gid = it.gid || it.id;
      if (!GROUPS_MAP.has(gid)) GROUPS_MAP.set(gid, []);
      GROUPS_MAP.get(gid).push(it);
      touchedGids.add(gid);
      added++;
    }
    touchedGids.forEach((gid) => {
      GROUPS_MAP.get(gid).sort((a, b) => (a.ord || 0) - (b.ord || 0) || a.t.localeCompare(b.t, "he"));
    });
    return added;
  }

  if (LEGACY_DATA && Array.isArray(LEGACY_DATA.items)) {
    hydrateAndIndexItems(LEGACY_DATA.items);
  }

  // Lazy Chunk Loader (works over both https:// CDN/ServiceWorker & file://)
  const _loadedChunks = new Set();
  const _chunkPromises = new Map();
  let _idToChunk = null;
  let _idMapPromise = null;
  let _allChunksPromise = null;

  window.__REBYOEL_CHUNK = function (chunkId, chunkItems) {
    hydrateAndIndexItems(chunkItems);
    _loadedChunks.add(chunkId);
  };

  function loadScriptTag(relUrl) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = relUrl;
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error(`Failed to load ${relUrl}`));
      document.head.appendChild(s);
    });
  }

  function loadChunk(chunkId) {
    if (!chunkId || !CHUNKS_META[chunkId] || _loadedChunks.has(chunkId)) return Promise.resolve();
    if (_chunkPromises.has(chunkId)) return _chunkPromises.get(chunkId);
    const url = `${CHUNKS_META[chunkId].f}?v=${encodeURIComponent(BUILD_VERSION)}`;
    const p = loadScriptTag(url)
      .then(() => { _loadedChunks.add(chunkId); })
      .catch((err) => {
        _chunkPromises.delete(chunkId);
        throw err;
      });
    _chunkPromises.set(chunkId, p);
    return p;
  }

  function loadIdMap() {
    if (_idToChunk) return Promise.resolve(_idToChunk);
    if (_idMapPromise) return _idMapPromise;
    if (!ALL_DATA_CHUNKS.length) {
      _idToChunk = new Map();
      return Promise.resolve(_idToChunk);
    }
    _idMapPromise = loadScriptTag(`data/id_map.js?v=${encodeURIComponent(BUILD_VERSION)}`).then(() => {
      _idToChunk = new Map();
      const rawMap = window.__REBYOEL_ID_MAP || {};
      Object.entries(rawMap).forEach(([cid, ids]) => {
        for (let i = 0; i < ids.length; i++) _idToChunk.set(ids[i], cid);
      });
      return _idToChunk;
    }).catch((err) => {
      _idMapPromise = null;
      throw err;
    });
    return _idMapPromise;
  }

  async function ensureItemsByIds(ids) {
    if (!ALL_DATA_CHUNKS.length) return;
    const missing = (ids || []).filter((id) => id && !ITEMS_BY_ID.has(id));
    if (!missing.length) return;
    const map = await loadIdMap();
    const needed = [...new Set(missing.map((id) => map.get(id)).filter((cid) => cid && !_loadedChunks.has(cid)))];
    if (needed.length) await Promise.all(needed.map(loadChunk));
  }

  function getMissingBrowseChunks(br) {
    if (!ALL_DATA_CHUNKS.length) return [];
    if ((br.cat === "פרשיות השבוע" || br.cat === "ענינא דיומא") && br.includeParshaBooks) {
      return ALL_DATA_CHUNKS.filter((cid) => !_loadedChunks.has(cid));
    }
    if (!br.cat || (br.cat === "ספרים" && !br.r) || !br.b) return [];
    const set = new Set();
    for (const row of STAGE_ROLLUPS) {
      if (row.cat !== br.cat) continue;
      if (br.r && row.r !== br.r) continue;
      if (row.b !== br.b) continue;
      for (const cid of (row.chunks || [])) {
        if (!_loadedChunks.has(cid)) set.add(cid);
      }
    }
    return [...set];
  }

  function allDataChunksLoaded() {
    if (!ALL_DATA_CHUNKS.length) return true;
    return ALL_DATA_CHUNKS.every((cid) => _loadedChunks.has(cid));
  }

  function ensureAllChunks(onBatchDone) {
    if (allDataChunksLoaded()) return Promise.resolve();
    if (_allChunksPromise) return _allChunksPromise;
    const pending = ALL_DATA_CHUNKS.filter((cid) => !_loadedChunks.has(cid));
    let done = ALL_DATA_CHUNKS.length - pending.length;
    const total = ALL_DATA_CHUNKS.length;
    _allChunksPromise = (async () => {
      const BATCH = 6;
      for (let i = 0; i < pending.length; i += BATCH) {
        const slice = pending.slice(i, i + BATCH);
        await Promise.all(slice.map((cid) => loadChunk(cid).catch(() => {})));
        done = ALL_DATA_CHUNKS.filter((cid) => _loadedChunks.has(cid)).length;
        if (typeof onBatchDone === "function") onBatchDone(done, total);
      }
    })().finally(() => {
      _allChunksPromise = null;
    });
    return _allChunksPromise;
  }

  function ensureSeforimPdfChunk() {
    if (CHUNKS_META["_pdf_all"]) return loadChunk("_pdf_all");
    return ensureAllChunks();
  }

  const LS_KEYS = {
    theme: "reb_yoel_theme_v2",
    bookmarks: "reb_yoel_bookmarks_v1",
    history: "reb_yoel_history_v1",
    progress: "reb_yoel_progress_v1",
    speed: "reb_yoel_speed_v1",
    autoNext: "reb_yoel_autonext_v1",
    submittedArchives: "reb_yoel_submitted_archives_v1",
    submittedFeedback: "reb_yoel_submitted_feedback_v1",
  };
  const SITE_CFG = window.SITE_CONFIG || {};

  const LANG_META = {
    yi: { label: "אידיש", cls: "badge-yi" },
    he: { label: 'עברית / לשו"ק', cls: "badge-he" },
    en: { label: "אנגלית / חוברות", cls: "badge-en" },
  };
  const FMT_META = {
    audio: { label: "שמע", icon: "🎧" },
    video: { label: "וידאו", icon: "🎬" },
    pdf: { label: "PDF / כתב", icon: "📄" },
  };

  // Canonical Hebrew Sort Helpers
  const GEM_MAP = { א:1, ב:2, ג:3, ד:4, ה:5, ו:6, ז:7, ח:8, ט:9, י:10, כ:20, ך:20, ל:30, מ:40, ם:40, נ:50, ן:50, ס:60, ע:70, פ:80, ף:80, צ:90, ץ:90, ק:100, ר:200, ש:300, ת:400 };
  function parseHebNum(str) {
    const clean = (str || "").replace(/["'״׳\s]/g, "");
    if (!clean) return null;
    let sum = 0;
    for (const ch of clean) {
      if (!GEM_MAP[ch]) return null;
      sum += GEM_MAP[ch];
    }
    return sum || null;
  }

  const CHUMASH_ORD = { "ספר בראשית": 1, "ספר שמות": 2, "ספר ויקרא": 3, "ספר במדבר": 4, "ספר דברים": 5, "ספר דברים / שיר השירים": 5.5, "ימים טובים — מועדים": 6, "חנוכה ופורים": 6, "שיר השירים": 7, "שיר השירים / אלול": 7.5 };
  const MONTH_ORD = { תשרי:1, חשון:2, כסלו:3, טבת:4, שבט:5, אדר:6, ניסן:7, אייר:8, סיון:9, תמוז:10, אב:11, אלול:12 };
  const PARSHA_ORDER = ["בראשית","נח","לך לך","וירא","חיי שרה","תולדות","ויצא","וישלח","וישב","מקץ","ויגש","ויחי","שמות","וארא","בא","בשלח","יתרו","משפטים","תרומה","תצוה","כי תשא","ויקהל","פקודי","ויקרא","צו","שמיני","תזריע","מצורע","אחרי מות","קדושים","אמור","בהר","בחוקותי","במדבר","נשא","בהעלותך","שלח","קרח","חוקת","בלק","פנחס","מטות","מסעי","דברים","ואתחנן","עקב","ראה","שופטים","כי תצא","כי תבוא","נצבים","וילך","האזינו","וזאת הברכה"];
  const YEAR_ALIAS = { עטרת: 679, עתר: 670, תנשא: 751, תש: 700, תערב: 672, תרסו: 666 };

  function drillSortKey(val) {
    if (!val) return "9_";
    if (val.includes("דף השער")) return "0_0000";
    if (val.includes("חינוך קטן")) return "0_0001";
    let m = val.match(/^(?:פרק(?:ים)?|סימן(?:ים)?|סעיף(?:ים)?)\s+([א-ת"'״׳]+)/);
    if (m) {
      const n = parseHebNum(m[1]);
      if (n !== null) return "0_" + String(n + 10).padStart(4, "0");
    }
    const mChov = val.match(/חוברת\s+([א-ת"'״׳]+|\d+)/);
    if (mChov) {
      const n = /^\d+$/.test(mChov[1]) ? Number(mChov[1]) : parseHebNum(mChov[1]);
      if (n !== null) return "0_" + String(n + 10).padStart(4, "0");
    }
    m = val.match(/^(?:חלק|מלוקט[^ח]*חלק)\s+([א-ת"'״׳]+)/);
    if (m) {
      const n = parseHebNum(m[1]);
      if (n !== null) {
        const prefix = val.includes("מלוקט (מהדורת") ? "2_" : "1_";
        return prefix + String(n).padStart(4, "0");
      }
    }
    if (CHUMASH_ORD[val]) return "2_" + String(Math.round(CHUMASH_ORD[val] * 10)).padStart(4, "0");
    if (MONTH_ORD[val]) return "2_" + String(MONTH_ORD[val] * 10).padStart(4, "0");
    const parCand = val.split(/\s*›\s*/)[0].replace(/^פרשת\s+|^פר['׳"]?\s+/, "").replace(/\s*\([^)]*\)\s*$/, "").replace("כי תבא", "כי תבוא").trim();
    const pi = PARSHA_ORDER.indexOf(parCand);
    if (pi !== -1) return "3_" + String(pi).padStart(3, "0") + "_" + val;
    const mNum = val.match(/^(?:\[|Drive\s*\[|סדרה\s*#?|\s*)(\d{1,4})(?:[-_\s\]]|$)/i);
    if (mNum) return "4_" + String(Number(mNum[1])).padStart(4, "0") + "_" + val;
    const yrM = val.match(/(?:^|\s|מאמרים\s+)(עטר["'״׳]?ת|עת["'״׳]?ר|תנש["'״׳]?א|ת["'״׳]ש|תער["'״׳]?[א-ת]|ת[רש][א-ת"'״׳]{1,3}|ה'ת[א-ת"'״׳]{2,4})(?:\s|$|\))/);
    if (yrM) {
      const cleanYr = yrM[1].replace(/^ה'/, "").replace(/["'״׳]/g, "");
      const yrVal = YEAR_ALIAS[cleanYr] || parseHebNum(cleanYr);
      if (yrVal) return "5_" + String(yrVal).padStart(5, "0") + "_" + val;
    }
    if (val.includes("כללי") || val.includes("שונות")) return "8_" + val;
    return "6_" + val;
  }

  function sortValuesClean(arr) {
    return [...arr].sort((a, b) => {
      const ka = drillSortKey(a), kb = drillSortKey(b);
      return ka !== kb ? ka.localeCompare(kb, "en") : a.localeCompare(b, "he");
    });
  }

  function numToHebOrder(n) {
    const ones = ["", "א'", "ב'", "ג'", "ד'", "ה'", "ו'", "ז'", "ח'", "ט'"];
    const tens = ["", "י'", "כ'", "ל'", "מ'", "נ'", "ס'", "ע'", "פ'", "צ'"];
    if (n <= 0 || n >= 100) return String(n);
    if (n === 15) return 'ט"ו';
    if (n === 16) return 'ט"ז';
    const t = Math.floor(n / 10), o = n % 10;
    if (!t) return ones[o];
    if (!o) return tens[t];
    return tens[t].replace("'", "") + '"' + ones[o].replace("'", "");
  }

  function bookHasMultiMaamar(bookPool) {
    const gidsMa = new Map();
    for (const x of bookPool) {
      if (!x.ma) continue;
      let s = gidsMa.get(x.gid);
      if (!s) { s = new Set(); gidsMa.set(x.gid, s); }
      for (const m of (x.mas || [x.ma])) s.add(m);
      if (s.size >= 2) return true;
    }
    return false;
  }

  // Persistent User Data
  function loadJSON(k, fallback) {
    try { return JSON.parse(localStorage.getItem(k) || "null") || fallback; } catch { return fallback; }
  }
  function saveJSON(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); } catch {}
  }

  // App State
  const state = {
    view: "browse",
    theme: loadJSON(LS_KEYS.theme, "light"),
    bookmarks: new Set(loadJSON(LS_KEYS.bookmarks, [])),
    history: loadJSON(LS_KEYS.history, []),
    progress: loadJSON(LS_KEYS.progress, {}),
    submittedArchives: loadJSON(LS_KEYS.submittedArchives, []),
    submittedFeedback: loadJSON(LS_KEYS.submittedFeedback, []),

    browse: {
      lang: "all",
      fmt: "all",
      cat: null,
      r: null,
      b: null,
      tanyaMode: "perek", // "perek" | "cycle"
      bookMode: "vol",    // "vol" | "maamar"
      ts: null,
      ma: null,
      v: null,
      sec: null,
      stageFilter: "",
      includeParshaBooks: false,
    },

    filters: {
      q: "",
      lang: "all",
      format: "all",
      cat: "all",
      rebbe: "all",
      book: "all",
      vol: "all",
      sec: "all",
      yearMode: "decades",
      decade: "all",
      year: "all",
      parsha: "all",
      source: "all",
      sort: "default",
    },

    catalogMode: "series", // "series" | "flat"
    expandedSeries: new Set(),
    pdfLang: "all",
    page: 1,
    pageSize: 28,
    filtered: ITEMS,
    groupedSeries: [],

    queue: [],
    queueIndex: -1,
    queueSeriesName: "",
    currentTrackId: null,
    activeModalShiurId: null,
    urlShiurId: null,
    speeds: [1, 1.25, 1.5, 1.75, 2],
    speedIdx: Math.min(4, Math.max(0, Number(loadJSON(LS_KEYS.speed, 0)) || 0)),
  };

  // DOM Cache
  const $ = (id) => document.getElementById(id);
  const el = {
    headerSubStats: $("headerSubStats"),
    brandHomeBtn: $("brandHomeBtn"),
    searchInput: $("globalSearchInput"),
    clearSearchBtn: $("clearSearchBtn"),
    themeToggleBtn: $("themeToggleBtn"),
    mainNav: $("mainNav"),
    mobileMoreNavBtn: $("mobileMoreNavBtn"),
    navTabs: document.querySelectorAll(".nav-tab[data-view]"),
    navTotalCount: $("navTotalCount"),
    navPdfCount: $("navPdfCount"),
    navSavedCount: $("navSavedCount"),
    resumeBanner: $("resumeBanner"),

    views: {
      browse: $("viewBrowse"),
      catalog: $("viewCatalog"),
      seforim: $("viewSeforim"),
      saved: $("viewSaved"),
      portals: $("viewPortals"),
      submitArchive: $("viewSubmitArchive"),
      feedback: $("viewFeedback"),
    },

    // Browse Wizard
    browseTopbar: $("browseTopbar"),
    browseFiltersToggleBtn: $("browseFiltersToggleBtn"),
    browseFiltersSummary: $("browseFiltersSummary"),
    browseLangPills: $("browseLangPills"),
    browseFmtPills: $("browseFmtPills"),
    browseOpenInCatalogBtn: $("browseOpenInCatalogBtn"),
    breadcrumbBar: $("breadcrumbBar"),
    browseBreadcrumbs: $("browseBreadcrumbs"),
    browseBackBtn: $("browseBackBtn"),
    browseStepKicker: $("browseStepKicker"),
    browseStepTitle: $("browseStepTitle"),
    browseStepSub: $("browseStepSub"),
    browseStepTools: $("browseStepTools"),
    stageFilterInput: $("stageFilterInput"),
    browseStageContent: $("browseStageContent"),

    // Catalog
    filtersSidebar: $("filtersSidebar"),
    mobileFilterToggleBtn: $("mobileFilterToggleBtn"),
    closeMobileFilterBtn: $("closeMobileFilterBtn"),
    mobileDrawerDoneBtn: $("mobileDrawerDoneBtn"),
    clearAllFiltersBtn: $("clearAllFiltersBtn"),
    mobileResultsCount: $("mobileResultsCount"),
    filterLangList: $("filterLangList"),
    filterFormatList: $("filterFormatList"),
    filterCatList: $("filterCatList"),
    filterRebbeGroup: $("filterRebbeGroup"),
    filterRebbeList: $("filterRebbeList"),
    filterBookList: $("filterBookList"),
    filterVolGroup: $("filterVolGroup"),
    filterVolTitle: $("filterVolTitle"),
    filterVolList: $("filterVolList"),
    filterSecGroup: $("filterSecGroup"),
    filterSecTitle: $("filterSecTitle"),
    filterSecList: $("filterSecList"),
    filterYearList: $("filterYearList"),
    filterParshaList: $("filterParshaList"),
    filterSourceList: $("filterSourceList"),
    activeChipsBar: $("activeChipsBar"),
    catalogLoadingBar: $("catalogLoadingBar"),
    catalogLoadingText: $("catalogLoadingText"),
    resultsSummary: $("resultsSummary"),
    sortSelect: $("sortSelect"),
    resultsList: $("resultsList"),
    emptyState: $("emptyState"),
    emptyResetBtn: $("emptyResetBtn"),
    paginationBar: $("paginationBar"),

    // PDF / Saved
    seforimPdfGrid: $("seforimPdfGrid"),
    pdfLangFilterPills: $("pdfLangFilterPills"),
    bookmarksList: $("bookmarksList"),
    historyList: $("historyList"),
    clearHistoryBtn: $("clearHistoryBtn"),

    // Player
    audioPlayerBar: $("audioPlayerBar"),
    nativeAudio: $("nativeAudio"),
    playerSeferBadge: $("playerSeferBadge"),
    playerTitle: $("playerTitle"),
    playerSub: $("playerSub"),
    playerPlayPauseBtn: $("playerPlayPauseBtn"),
    playerPrevBtn: $("playerPrevBtn"),
    playerNextBtn: $("playerNextBtn"),
    playerBack30Btn: $("playerBack30Btn"),
    playerFwd30Btn: $("playerFwd30Btn"),
    playerSeek: $("playerSeek"),
    playerCurrentTime: $("playerCurrentTime"),
    playerDuration: $("playerDuration"),
    playerSpeedBtn: $("playerSpeedBtn"),
    playerAutoNext: $("playerAutoNext"),
    playerDownloadLink: $("playerDownloadLink"),
    playerCloseBtn: $("playerCloseBtn"),

    // Modal
    mediaModal: $("mediaModal"),
    playerSourceLink: $("playerSourceLink"),
    playerErrorBanner: $("playerErrorBanner"),
    playerErrorMsg: $("playerErrorMsg"),
    playerErrorSourceLink: $("playerErrorSourceLink"),
    playerErrorDownloadLink: $("playerErrorDownloadLink"),
    modalPills: $("modalPills"),
    modalTitle: $("modalTitle"),
    modalShareBtn: $("modalShareBtn"),
    modalExternalBtn: $("modalExternalBtn"),
    closeModalBtn: $("closeModalBtn"),
    modalBody: $("modalBody"),
    modalSeriesPlaylist: $("modalSeriesPlaylist"),
    modalFooter: $("modalFooter"),
    appToast: $("appToast"),
  };

  let _toastTimer = null;
  function showToast(msg) {
    if (!el.appToast) return;
    el.appToast.textContent = msg;
    el.appToast.classList.remove("hidden");
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => el.appToast?.classList.add("hidden"), 2300);
  }

  const IS_FILE_PROTOCOL = window.location.protocol === "file:";

  function buildShareUrl(paramStr) {
    const clean = (paramStr || "").replace(/^[?#]+/, "");
    const base = window.location.href.split("#")[0].split("?")[0];
    if (!clean) return base;
    return IS_FILE_PROTOCOL ? `${base}#${clean}` : `${base}?${clean}`;
  }

  async function shareLink({ title, text, hash }) {
    const url = buildShareUrl(hash);
    if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
      try {
        await navigator.share({ title: title || "אוצר שיעורי ר' יואל", text: text || "", url });
        return;
      } catch (e) {
        if (e && e.name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      showToast("✓ הקישור הועתק לשיתוף");
    } catch {
      const ta = document.createElement("textarea");
      ta.value = url;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); showToast("✓ הקישור הועתק לשיתוף"); } catch {}
      document.body.removeChild(ta);
    }
  }

  function escHtml(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function formatTime(secs) {
    if (!secs || !isFinite(secs) || secs <= 0) return "00:00";
    const s = Math.floor(secs);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    const mm = String(m).padStart(2, "0");
    const ss = String(sec).padStart(2, "0");
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  }
  function getFormatBadges(it) {
    const out = [];
    for (const fmt of it.f || []) {
      if (fmt === "video") out.push(`<span class="badge badge-vid">🎬 וידאו</span>`);
      else if (fmt === "pdf") out.push(`<span class="badge badge-pdf">📄 PDF / כתב</span>`);
      else if (fmt === "audio") out.push(`<span class="badge">🎧 שמע</span>`);
    }
    return out.join("");
  }
  function getLangBadges(it) {
    return (it.l || []).map((c) => {
      const m = LANG_META[c] || { label: c, cls: "" };
      return `<span class="badge ${m.cls}">${escHtml(m.label)}</span>`;
    }).join("");
  }
  function getDirectDownloadUrl(it) {
    if (it.au) return it.au;
    if (it.dl) return it.dl;
    const drv = it.dr || it.pd || "";
    if (drv.includes("drive.google.com/file/d/")) {
      const m = drv.match(/\/file\/d\/([^/?]+)(?:\/preview\?resourcekey=([^&]+))?/);
      if (m) return `https://drive.google.com/uc?export=download&id=${m[1]}${m[2] ? `&resourcekey=${m[2]}` : ""}`;
    }
    return (it.vi && !it.vi.startsWith("yt:") ? it.vi : "") || it.pd || it.pg || "";
  }
  function getSourceUrl(it) {
    return (it && (it.pg || SOURCES[it.src]?.url || getDirectDownloadUrl(it))) || "";
  }
  function showAudioError(it, customMsg = "") {
    if (!it || !el.playerErrorBanner) return;
    const srcName = SOURCES[it.src]?.name || it.src || "המקור";
    const srcUrl = getSourceUrl(it);
    const dlUrl = getDirectDownloadUrl(it);
    el.playerErrorMsg.textContent = customMsg || `⚠️ הדפדפן לא הצליח לטעון את השמע ישירות מ-${srcName}. ניתן לנגן בדף המקור או להוריד:`;
    if (el.playerErrorSourceLink) {
      el.playerErrorSourceLink.href = srcUrl || "#";
      el.playerErrorSourceLink.classList.toggle("hidden", !srcUrl);
    }
    if (el.playerErrorDownloadLink) {
      el.playerErrorDownloadLink.href = dlUrl || "#";
      el.playerErrorDownloadLink.classList.toggle("hidden", !dlUrl);
    }
    el.playerErrorBanner.classList.remove("hidden");
  }
  function buildTracksSeriesGroups(items) {
    const map = new Map();
    for (const it of items) {
      const gid = it.gid || it.id;
      if (!map.has(gid)) map.set(gid, []);
      map.get(gid).push(it);
    }
    const groups = [];
    map.forEach((tracks, gid) => {
      tracks.sort((a, b) => (a.ord || 0) - (b.ord || 0) || a.t.localeCompare(b.t, "he"));
      groups.push({ gid, first: tracks[0], tracks });
    });
    return groups;
  }

  // =========================================================================
  // Theme & View Navigation
  // =========================================================================
  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    saveJSON(LS_KEYS.theme, theme);
    const sun = el.themeToggleBtn.querySelector(".theme-icon-sun");
    const moon = el.themeToggleBtn.querySelector(".theme-icon-moon");
    const lbl = el.themeToggleBtn.querySelector(".theme-label");
    if (theme === "dark") {
      sun.classList.add("hidden");
      moon.classList.remove("hidden");
      lbl.textContent = "מצב יום";
    } else {
      sun.classList.remove("hidden");
      moon.classList.add("hidden");
      lbl.textContent = "מצב לילה";
    }
  }

  function scrollToRelevantContent(targetEl) {
    const node = targetEl || document.querySelector(".main-content");
    if (!node) return;
    const stickyHeader = document.getElementById("siteHeader");
    const isSticky = stickyHeader && getComputedStyle(stickyHeader).position === "sticky";
    const headerOffset = isSticky ? stickyHeader.getBoundingClientRect().height + 10 : 8;
    const targetY = Math.max(0, window.scrollY + node.getBoundingClientRect().top - headerOffset);
    if (window.scrollY > targetY + 12) {
      window.scrollTo({ top: targetY, behavior: "smooth" });
    }
  }

  let _suppressUrlSync = false;
  function buildStateParams() {
    const p = new URLSearchParams();
    if (state.view && state.view !== "browse") {
      p.set("view", state.view);
      if (state.view === "catalog") {
        const f = state.filters;
        if (f.q) p.set("q", f.q);
        if (f.lang !== "all") p.set("lang", f.lang);
        if (f.format !== "all") p.set("fmt", f.format);
        if (f.cat !== "all") p.set("cat", f.cat);
        if (f.rebbe !== "all") p.set("r", f.rebbe);
        if (f.book !== "all") p.set("b", f.book);
        if (f.vol !== "all") p.set("v", f.vol);
        if (f.sec !== "all") p.set("sec", f.sec);
        if (f.yearMode !== "decades") p.set("ym", f.yearMode);
        if (f.decade !== "all") p.set("dec", f.decade);
        if (f.year !== "all") p.set("yr", f.year);
        if (f.parsha !== "all") p.set("p", f.parsha);
        if (f.source !== "all") p.set("src", f.source);
        if (f.sort !== "default") p.set("sort", f.sort);
        if (state.catalogMode !== "series") p.set("mode", state.catalogMode);
        if (state.page > 1) p.set("page", String(state.page));
      } else if (state.view === "seforim" && state.pdfLang !== "all") {
        p.set("pdflang", state.pdfLang);
      }
    } else {
      const br = state.browse;
      if (br.lang !== "all") p.set("lang", br.lang);
      if (br.fmt !== "all") p.set("fmt", br.fmt);
      if (br.cat) p.set("cat", br.cat);
      if (br.r) p.set("r", br.r);
      if (br.b) p.set("b", br.b);
      if (br.tanyaMode === "cycle") p.set("tm", "cycle");
      if (br.bookMode === "maamar") p.set("bm", "maamar");
      if (br.ts) p.set("ts", br.ts);
      if (br.ma) p.set("ma", br.ma);
      if (br.v) p.set("v", br.v);
      if (br.sec) p.set("sec", br.sec);
      if (br.includeParshaBooks) p.set("cp", "1");
    }
    if (state.urlShiurId) p.set("shiur", state.urlShiurId);
    return p.toString();
  }

  function syncUrlState(push = true) {
    if (_suppressUrlSync) return;
    const qs = buildStateParams();
    if (IS_FILE_PROTOCOL) {
      const nextUrl = qs ? `#${qs}` : window.location.pathname;
      const curHash = window.location.hash.replace(/^#/, "");
      if (curHash === qs) return;
      try {
        if (push) history.pushState(null, "", nextUrl);
        else history.replaceState(null, "", nextUrl);
      } catch {
        if (qs) window.location.hash = qs;
      }
    } else {
      const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
      const curUrl = `${window.location.pathname}${window.location.search}`;
      if (curUrl === nextUrl && !window.location.hash) return;
      try {
        if (push) history.pushState(null, "", nextUrl);
        else history.replaceState(null, "", nextUrl);
      } catch {}
    }
  }

  function parseLocationParams() {
    const p = new URLSearchParams();
    const rawH = window.location.hash.replace(/^#/, "");
    if (rawH) {
      new URLSearchParams(rawH).forEach((v, k) => p.set(k, v));
    }
    if (window.location.search && window.location.search.length > 1) {
      new URLSearchParams(window.location.search).forEach((v, k) => p.set(k, v));
    }
    return p;
  }

  let _routeToken = 0;
  async function applyStateFromLocation() {
    const myRoute = ++_routeToken;
    const p = parseLocationParams();
    const shiurId = p.get("shiur");
    const hasExplicitBrowseCtx = p.has("cat") || p.has("r") || p.has("b") || p.has("v") || p.has("sec") || p.get("view") === "catalog";

    if (!shiurId && el.mediaModal && !el.mediaModal.classList.contains("hidden")) {
      closeMediaModal(true);
    }

    let resolvedItem = null;
    if (shiurId) {
      try { await ensureItemsByIds([shiurId]); } catch {}
      if (myRoute !== _routeToken) return;
      resolvedItem = ITEMS_BY_ID.get(shiurId) || null;
    }

    _suppressUrlSync = true;
    try {
      const view = p.get("view") || "browse";
      if (resolvedItem && !hasExplicitBrowseCtx) {
        Object.assign(state.browse, {
          lang: "all", fmt: "all",
          cat: resolvedItem.cat || null, r: resolvedItem.r || null, b: resolvedItem.b || null,
          tanyaMode: "perek", bookMode: "vol", ts: null, ma: null,
          v: resolvedItem.v || null, sec: resolvedItem.sec || null, stageFilter: "", includeParshaBooks: false,
        });
        syncBrowseFilterPills();
        switchView("browse");
      } else if (view === "browse") {
        Object.assign(state.browse, {
          lang: p.get("lang") || "all",
          fmt: p.get("fmt") || "all",
          cat: p.get("cat") || null,
          r: p.get("r") || null,
          b: p.get("b") || null,
          tanyaMode: p.get("tm") || "perek",
          bookMode: p.get("bm") || "vol",
          ts: p.get("ts") || null,
          ma: p.get("ma") || null,
          v: p.get("v") || null,
          sec: p.get("sec") || null,
          stageFilter: "",
          includeParshaBooks: p.get("cp") === "1",
        });
        syncBrowseFilterPills();
        switchView("browse");
      } else if (el.views[view]) {
        if (view === "catalog") {
          Object.assign(state.filters, {
            q: p.get("q") || "",
            lang: p.get("lang") || "all",
            format: p.get("fmt") || "all",
            cat: p.get("cat") || "all",
            rebbe: p.get("r") || "all",
            book: p.get("b") || "all",
            vol: p.get("v") || "all",
            sec: p.get("sec") || "all",
            yearMode: p.get("ym") || "decades",
            decade: p.get("dec") || "all",
            year: p.get("yr") || "all",
            parsha: p.get("p") || "all",
            source: p.get("src") || "all",
            sort: p.get("sort") || "default",
          });
          state.catalogMode = p.get("mode") === "flat" ? "flat" : "series";
          state.page = Math.max(1, Number(p.get("page") || 1) || 1);
          el.searchInput.value = state.filters.q;
          el.clearSearchBtn.classList.toggle("hidden", !state.filters.q);
          el.sortSelect.value = state.filters.sort;
          el.filtersSidebar.querySelectorAll(".ym-btn").forEach((b) => b.classList.toggle("active", b.dataset.ym === state.filters.yearMode));
          document.querySelectorAll(".vm-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === state.catalogMode));
          applyCatalogFilters(false, true);
        } else if (view === "seforim") {
          state.pdfLang = p.get("pdflang") || "all";
          el.pdfLangFilterPills.querySelectorAll(".pill-filter").forEach((b) => b.classList.toggle("active", b.dataset.pdflang === state.pdfLang));
        }
        switchView(view);
      }

      if (resolvedItem) {
        if (resolvedItem.au) startSeriesPlayback(resolvedItem.gid, resolvedItem.id, { fromUrl: true });
        else if (resolvedItem.dr) openMediaModal(resolvedItem, "drive", resolvedItem.gid, { fromUrl: true });
        else if (resolvedItem.vi) openMediaModal(resolvedItem, "video", resolvedItem.gid, { fromUrl: true });
        else if (resolvedItem.pd) openMediaModal(resolvedItem, "pdf", resolvedItem.gid, { fromUrl: true });
      }
    } finally {
      _suppressUrlSync = false;
    }
    if (!IS_FILE_PROTOCOL && window.location.hash && !window.location.search) {
      syncUrlState(false);
    }
  }

  function syncBrowseFilterPills() {
    el.browseLangPills.querySelectorAll(".mini-pill").forEach((b) => b.classList.toggle("active", b.dataset.blang === state.browse.lang));
    el.browseFmtPills.querySelectorAll(".mini-pill").forEach((b) => b.classList.toggle("active", b.dataset.bfmt === state.browse.fmt));
    const { lang, fmt } = state.browse;
    const isFiltered = lang !== "all" || fmt !== "all";
    const lTxt = lang === "all" ? "כל השפות" : (LANG_META[lang]?.label || lang);
    const fTxt = fmt === "all" ? "הכל" : (FMT_META[fmt]?.label || fmt);
    if (el.browseFiltersSummary) {
      el.browseFiltersSummary.textContent = `${isFiltered ? "סינון פעיל" : "סינון מהיר"}: ${lTxt} · ${fTxt}`;
    }
    el.browseTopbar?.classList.toggle("has-active", isFiltered);
  }

  function switchView(viewName) {
    state.view = viewName;
    el.filtersSidebar.classList.remove("open");
    document.body.classList.remove("lock-scroll");
    Object.entries(el.views).forEach(([k, sec]) => {
      sec.classList.toggle("hidden", k !== viewName);
      sec.classList.toggle("active", k === viewName);
    });
    el.navTabs.forEach((t) => t.classList.toggle("active", t.dataset.view === viewName));
    el.mainNav?.classList.remove("more-open");
    el.mobileMoreNavBtn?.setAttribute("aria-expanded", "false");
    el.mobileMoreNavBtn?.classList.toggle("active", ["portals", "submitArchive", "feedback"].includes(viewName));
    if (viewName === "browse") renderBrowse();
    if (viewName === "catalog") {
      applyCatalogFilters(false, true);
      startCatalogChunksStream();
    }
    if (viewName === "seforim") renderSeforimPdfView();
    if (viewName === "saved") renderSavedView();
    if (viewName === "submitArchive") renderSubmitArchiveView();
    if (viewName === "feedback") renderFeedbackView();
    syncUrlState(true);
    scrollToRelevantContent(el.views[viewName]);
  }

  // =========================================================================
  // VIEW 1: Clean 6-Step Chassidus-App Guided Browser
  // =========================================================================
  function getBrowsePool() {
    const { lang, fmt } = state.browse;
    return ITEMS.filter((it) => {
      if (lang !== "all" && !(it.l || []).includes(lang)) return false;
      if (fmt !== "all" && !(it.f || []).includes(fmt)) return false;
      return true;
    });
  }

  function renderBrowseBreadcrumbs() {
    const br = state.browse;
    const crumbs = [{ label: "🏠 ראשי", level: "root" }];
    if (br.cat) crumbs.push({ label: `${CAT_INFO[br.cat]?.icon || "📚"} ${br.cat}`, level: "cat" });
    if (br.r) crumbs.push({ label: br.r, level: "rebbe" });
    if (br.b) crumbs.push({ label: br.b, level: "book" });
    if (br.b && br.b.startsWith("תניא") && br.tanyaMode === "cycle" && br.ts) {
      crumbs.push({ label: br.ts, level: "ts" });
    } else if (br.b && !br.b.startsWith("תניא") && br.bookMode === "maamar" && br.ma) {
      crumbs.push({ label: `📑 ${br.ma}`, level: "ma" });
    } else {
      if (br.v) crumbs.push({ label: br.v, level: "vol" });
      if (br.sec) crumbs.push({ label: br.sec, level: "sec" });
    }

    el.browseBreadcrumbs.innerHTML = crumbs.map((c, idx) => {
      const isLast = idx === crumbs.length - 1;
      const sep = idx > 0 ? `<span class="crumb-sep">›</span>` : "";
      return `${sep}<button type="button" class="crumb-btn ${isLast ? "current" : ""}" data-crumb="${c.level}" ${isLast ? "disabled" : ""}>${escHtml(c.label)}</button>`;
    }).join("");

    const hasDepth = !!(br.cat || br.r || br.b || br.ts || br.ma || br.v || br.sec);
    el.breadcrumbBar?.classList.toggle("hidden", !hasDepth);
    el.browseBackBtn.classList.toggle("hidden", !hasDepth);
    el.browseOpenInCatalogBtn.classList.toggle("hidden", !br.cat);
  }

  function goBrowseBack() {
    const br = state.browse;
    br.stageFilter = "";
    if (br.sec) { br.sec = null; }
    else if (br.ma) { br.ma = null; }
    else if (br.v) { br.v = null; }
    else if (br.ts) { br.ts = null; }
    else if (br.b) { br.b = null; br.ma = null; br.bookMode = "vol"; br.includeParshaBooks = false; }
    else if (br.r) { br.r = null; }
    else if (br.cat) { br.cat = null; }
    renderBrowse();
    syncUrlState(true);
  }

  function jumpBrowseCrumb(level) {
    const br = state.browse;
    br.stageFilter = "";
    if (level === "root") {
      br.cat = br.r = br.b = br.ts = br.ma = br.v = br.sec = null;
      br.bookMode = "vol";
      br.includeParshaBooks = false;
    } else if (level === "cat") {
      br.r = br.b = br.ts = br.ma = br.v = br.sec = null;
      br.bookMode = "vol";
      br.includeParshaBooks = false;
    } else if (level === "rebbe") {
      br.b = br.ts = br.ma = br.v = br.sec = null;
      br.bookMode = "vol";
      br.includeParshaBooks = false;
    } else if (level === "book") {
      br.ts = br.ma = br.v = br.sec = null;
      br.includeParshaBooks = false;
    } else if (level === "ts" || level === "vol" || level === "ma") {
      br.sec = null;
    }
    renderBrowse();
    syncUrlState(true);
  }

  function renderStepGrid(cards, opts = {}) {
    if (!cards.length) {
      el.browseStageContent.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h3>אין שיעורים התואמים את סינון השפה/מדיה במדור זה</h3>
          <p>לחץ על "כל השפות" / "הכל" למעלה כדי לראות את כל השיעורים.</p>
          <button type="button" class="btn-primary" id="browseResetFiltersBtn">איפוס סינון</button>
        </div>`;
      return;
    }
    el.browseStageContent.innerHTML = `<div class="step-grid ${opts.compact ? "compact-grid" : ""}">${cards.map((c) => `
      <button type="button" class="step-card ${opts.rebbe ? "step-card-rebbe" : ""}" data-step-action="${c.action}" data-step-val="${escHtml(c.val)}">
        <div>
          <div class="step-card-top">
            <span class="step-card-icon">${c.icon || "📘"}</span>
            <span class="step-card-count">${c.badge || ""}</span>
          </div>
          <h3 class="step-card-title">${escHtml(c.title)}</h3>
          ${c.sub ? `<p class="step-card-sub">${escHtml(c.sub)}</p>` : ""}
          ${c.desc ? `<p class="step-card-desc">${escHtml(c.desc)}</p>` : ""}
        </div>
        <div class="step-card-foot">
          <span>${escHtml(c.foot || "")}</span>
          <span class="step-card-arrow">כניסה &larr;</span>
        </div>
      </button>
    `).join("")}</div>`;
  }

  function sumRollupStats(predFn, lang, fmt) {
    const key = `${lang}|${fmt}`;
    let cnt = 0;
    let ser = 0;
    for (let i = 0; i < STAGE_ROLLUPS.length; i++) {
      const row = STAGE_ROLLUPS[i];
      if (!predFn(row)) continue;
      const st = row.stats && row.stats[key];
      if (st) {
        cnt += st[0];
        ser += st[1];
      }
    }
    return [cnt, ser];
  }

  let _stageFilterNeeded = false;
  let _browseLoadToken = 0;
  function renderBrowse() {
    renderBrowseBreadcrumbs();
    const br = state.browse;
    el.browseStepTools.innerHTML = "";
    _stageFilterNeeded = false;
    if (el.stageFilterInput.value !== br.stageFilter) el.stageFilterInput.value = br.stageFilter;

    // Stages 1-3 render instantaneously from tiny boot.js STAGE_ROLLUPS; Stage 4+ loads only that book's chunk!
    const missingChunks = getMissingBrowseChunks(br);
    if (missingChunks.length) {
      const myToken = ++_browseLoadToken;
      el.stageFilterInput.classList.add("hidden");
      el.browseStepKicker.textContent = `טוען — ${br.b || br.cat || ""}`;
      el.browseStepTitle.textContent = br.b || br.cat || "טוען שיעורים...";
      el.browseStepSub.textContent = "טוען את שיעורי המדור...";
      el.browseStageContent.innerHTML = `
        <div class="chunk-loading-box">
          <div class="loading-spinner"></div>
          <div><strong>טוען את שיעורי ${escHtml(br.b || br.cat || "המדור")}...</strong></div>
        </div>`;
      Promise.all(missingChunks.map((cid) => loadChunk(cid)))
        .then(() => {
          if (myToken === _browseLoadToken && state.view === "browse") renderBrowse();
        })
        .catch(() => {
          if (myToken === _browseLoadToken) {
            el.browseStageContent.innerHTML = `<div class="empty-state"><h3>שגיאה בטעינת השיעורים</h3><p>אנא בדוק את החיבור ונסה לרענן.</p></div>`;
          }
        });
      return;
    }

    const pool = getBrowsePool();
    try {
      renderBrowseStage(pool, br);
    } finally {
      el.stageFilterInput.classList.toggle("hidden", !_stageFilterNeeded);
    }
  }

  function renderBrowseStage(pool, br) {
    const useRollup = STAGE_ROLLUPS.length > 0;

    // STAGE 1: Category Selection
    if (!br.cat) {
      el.browseStepKicker.textContent = "שלב 1 — ראשי";
      el.browseStepTitle.textContent = "בחר מדור לימוד";
      el.browseStepSub.textContent = "דפדף בקלות לפי מדור, ספר או נושא עד לסדרת השיעורים הרצויה";

      const cards = CAT_ORDER.map((cat) => {
        let count = 0;
        let seriesCnt = 0;
        if (useRollup) {
          [count, seriesCnt] = sumRollupStats((row) => row.cat === cat, br.lang, br.fmt);
        } else {
          const subset = pool.filter((x) => x.cat === cat);
          count = subset.length;
          seriesCnt = new Set(subset.map((x) => x.gid)).size;
        }
        const info = CAT_INFO[cat] || {};
        return {
          action: "pick-cat",
          val: cat,
          icon: info.icon || "📚",
          badge: `${count.toLocaleString("he-IL")} שיעורים`,
          title: info.title || cat,
          desc: info.desc || "",
          foot: `${seriesCnt.toLocaleString("he-IL")} סדרות ופריטים`,
        };
      }).filter((c) => !c.badge.startsWith("0 "));
      renderStepGrid(cards);
      return;
    }

    const catPool = pool.filter((x) => x.cat === br.cat);

    // STAGE 2 in ספרים: Pick Rebbe
    if (br.cat === "ספרים" && !br.r) {
      el.browseStepKicker.textContent = "שלב 2 — ספרי רבותינו נשיאינו";
      el.browseStepTitle.textContent = "ספרי איזה מרבותינו נשיאינו?";
      el.browseStepSub.textContent = "בחר מרבותינו נשיאינו (מכ\"ק אדמו\"ר הזקן עד כ\"ק אדמו\"ר)";

      const cards = REBBE_ORDER.map((rb) => {
        let count = 0;
        let seriesCnt = 0;
        if (useRollup) {
          [count, seriesCnt] = sumRollupStats((row) => row.cat === "ספרים" && row.r === rb, br.lang, br.fmt);
        } else {
          const sub = catPool.filter((x) => x.r === rb);
          count = sub.length;
          seriesCnt = new Set(sub.map((x) => x.gid)).size;
        }
        const info = REBBE_INFO[rb] || {};
        const bkCnt = (BOOKS_BY_REBBE[rb] || []).length;
        return {
          action: "pick-rebbe",
          val: rb,
          icon: "👑",
          badge: `${count.toLocaleString("he-IL")} שיעורים`,
          title: info.title || rb,
          sub: info.sub || "",
          desc: info.desc || "",
          foot: `${bkCnt === 1 ? "ספר 1" : bkCnt + " ספרים"} • ${seriesCnt.toLocaleString("he-IL")} סדרות`,
        };
      }).filter((c) => !c.badge.startsWith("0 "));
      renderStepGrid(cards, { rebbe: true });
      return;
    }

    // STAGE 3 (Pick Book inside Rebbe, or sub-domain inside other Cat)
    if (!br.b) {
      if (br.cat === "ספרים") {
        el.browseStepKicker.textContent = `שלב 3 — ${br.r}`;
        el.browseStepTitle.textContent = `איזה ספר של ${br.r}?`;
        el.browseStepSub.textContent = "בחר ספר לעבור לחלקים / פרקים ולסדרות השיעורים";

        const orderedBooks = BOOKS_BY_REBBE[br.r] || [];
        let cards = [];
        let chzCnt = 0;
        if (useRollup) {
          const bookStats = new Map();
          for (const row of STAGE_ROLLUPS) {
            if (row.cat !== "ספרים" || row.r !== br.r) continue;
            const st = row.stats && row.stats[`${br.lang}|${br.fmt}`];
            if (!st) continue;
            const prev = bookStats.get(row.b) || [0, 0];
            bookStats.set(row.b, [prev[0] + st[0], prev[1] + st[1]]);
          }
          const finalBooks = orderedBooks.filter((bk) => bookStats.has(bk));
          bookStats.forEach((_, bk) => { if (!finalBooks.includes(bk)) finalBooks.push(bk); });
          cards = finalBooks.map((bk) => {
            const [cnt, serCnt] = bookStats.get(bk);
            const info = BOOK_INFO[bk] || ["חלק", "מאמר", ""];
            return {
              action: "pick-book",
              val: bk,
              icon: bk.includes("שיחות") ? "📜" : (bk.includes("תניא") ? "📘" : "📕"),
              badge: `${cnt.toLocaleString("he-IL")} שיעורים`,
              title: bk,
              desc: info[2] || "",
              foot: `${serCnt.toLocaleString("he-IL")} סדרות שיעורים`,
            };
          });
          if (br.r === 'כ"ק אדמו"ר') {
            [chzCnt] = sumRollupStats((row) => row.b === 'חזרות על התוועדויות הרבי', br.lang, br.fmt);
          }
        } else {
          const rbPool = catPool.filter((x) => x.r === br.r);
          const presentBooks = new Set(rbPool.map((x) => x.b));
          const finalBooks = orderedBooks.filter((bk) => presentBooks.has(bk));
          presentBooks.forEach((bk) => { if (!finalBooks.includes(bk)) finalBooks.push(bk); });
          cards = finalBooks.map((bk) => {
            const sub = rbPool.filter((x) => x.b === bk);
            const serCnt = new Set(sub.map((x) => x.gid)).size;
            const info = BOOK_INFO[bk] || ["חלק", "מאמר", ""];
            return {
              action: "pick-book",
              val: bk,
              icon: bk.includes("שיחות") ? "📜" : (bk.includes("תניא") ? "📘" : "📕"),
              badge: `${sub.length.toLocaleString("he-IL")} שיעורים`,
              title: bk,
              desc: info[2] || "",
              foot: `${serCnt.toLocaleString("he-IL")} סדרות שיעורים`,
            };
          });
          if (br.r === 'כ"ק אדמו"ר') {
            chzCnt = pool.filter((x) => x.b === 'חזרות על התוועדויות הרבי').length;
          }
        }
        if (br.r === 'כ"ק אדמו"ר' && chzCnt) {
          cards.push({
            action: "jump-chazaros",
            val: "chazaros",
            icon: "🔄",
            badge: `${chzCnt.toLocaleString("he-IL")} הקלטות`,
            title: "חזרות על התוועדויות הרבי",
            sub: "מפי ה'חוזר' ר' יואל",
            desc: "מעבר ישיר להקלטות חזרה משבתות ומועדים לפי שנים",
            foot: "דפדוף לפי שנים",
          });
        }
        renderStepGrid(cards);
      } else {
        // Non-ספרים Category -> Step 2 (pick Chumash / Month / Chazaros vs Farbrengens / Topic Area / PDF group)
        el.browseStepKicker.textContent = `שלב 2 — ${br.cat}`;
        el.browseStepTitle.textContent = `בחר ${CAT_INFO[br.cat]?.nextLabel || "נושא"}`;
        el.browseStepSub.textContent = CAT_INFO[br.cat]?.desc || "";

        const counts = new Map();
        const serCounts = new Map();
        if (useRollup) {
          for (const row of STAGE_ROLLUPS) {
            if (row.cat !== br.cat) continue;
            const st = row.stats && row.stats[`${br.lang}|${br.fmt}`];
            if (!st) continue;
            const bk = row.b || "כללי";
            counts.set(bk, (counts.get(bk) || 0) + st[0]);
            serCounts.set(bk, (serCounts.get(bk) || 0) + st[1]);
          }
        } else {
          const serSets = new Map();
          catPool.forEach((x) => {
            const bk = x.b || "כללי";
            counts.set(bk, (counts.get(bk) || 0) + 1);
            if (!serSets.has(bk)) serSets.set(bk, new Set());
            serSets.get(bk).add(x.gid);
          });
          serSets.forEach((s, bk) => serCounts.set(bk, s.size));
        }
        const sortedBs = sortValuesClean([...counts.keys()]);
        const cards = sortedBs.map((bk) => ({
          action: "pick-book",
          val: bk,
          icon: br.cat === "ניגונים" ? "🎵" : (br.cat === "פרשיות השבוע" ? "📖" : "📂"),
          badge: `${counts.get(bk).toLocaleString("he-IL")} פריטים`,
          title: bk,
          foot: `${(serCounts.get(bk) || 0).toLocaleString("he-IL")} סדרות ושיעורים`,
        }));
        renderStepGrid(cards, { compact: sortedBs.length > 6 });
      }
      return;
    }

    // Active pool inside chosen book
    let bookPool = catPool.filter((x) => (!br.r || x.r === br.r) && x.b === br.b);

    // Special handling for Tanya dual mode (By Perek OR By Complete Series)
    const isTanya = br.b && br.b.startsWith("תניא");
    if (isTanya) {
      renderTanyaTools(!br.ts && !br.v);
      if (br.tanyaMode === "cycle") {
        if (!br.ts) {
          el.browseStepKicker.textContent = `שלב 4 — ${br.b}`;
          el.browseStepTitle.textContent = "בחר סדרת שיעורים שלמה (מתחילה ועד סוף)";
          el.browseStepSub.textContent = "כל כרטיס מאגד מחזור שיעורים שלם של התניא להאזנה ברצף";

          const tsMap = new Map();
          bookPool.forEach((x) => {
            const k = x.ts || x.ser || "כללי";
            if (!tsMap.has(k)) tsMap.set(k, []);
            tsMap.get(k).push(x);
          });
          const keys = sortValuesClean([...tsMap.keys()]).filter((k) => !br.stageFilter || k.toLowerCase().includes(br.stageFilter.toLowerCase()));
          const cards = keys.map((k) => {
            const arr = tsMap.get(k);
            const langs = [...new Set(arr.flatMap((a) => a.l || []))].map((c) => LANG_META[c]?.label || c).join(" • ");
            return {
              action: "pick-ts",
              val: k,
              icon: "🎬",
              badge: `${arr.length} שיעורים`,
              title: k,
              sub: langs,
              foot: "צפייה בסדרה והאזנה ברצף",
            };
          });
          renderStepGrid(cards, { compact: true });
          return;
        }
        // Inside selected Tanya Series Cycle (br.ts) -> show all lessons grouped in chapter/part order!
        const tsPool = bookPool.filter((x) => (x.ts || x.ser || "כללי") === br.ts);
        tsPool.sort((a, b) => {
          const ka = drillSortKey(a.v), kb = drillSortKey(b.v);
          return ka !== kb ? ka.localeCompare(kb, "en") : (a.ord || 0) - (b.ord || 0) || a.t.localeCompare(b.t, "he");
        });
        el.browseStepKicker.textContent = `סדרה שלמה — ${br.b}`;
        el.browseStepTitle.textContent = br.ts;
        el.browseStepSub.textContent = `${tsPool.length} שיעורים ברצף — לחץ "נגן סדרה מההתחלה" להאזנה רצופה`;
        renderSeriesList(el.browseStageContent, [{ gid: `ts_${br.b}_${br.ts}`, first: tsPool[0], tracks: tsPool, customTitle: br.ts }], { openAll: true, hidePath: true });
        return;
      }
      // Tanya by Perek mode: Step 4 picks Perek, Step 5 shows ALL series covering that Perek!
      if (!br.v) {
        el.browseStepKicker.textContent = `שלב 4 — ${br.b}`;
        el.browseStepTitle.textContent = "בחר פרק בתניא";
        el.browseStepSub.textContent = "לאחר בחירת הפרק תראה את כל סדרות השיעורים השונות על פרק זה";

        const vMap = new Map();
        bookPool.forEach((x) => {
          const v = x.v || "כללי";
          if (!vMap.has(v)) vMap.set(v, { cnt: 0, gids: new Set() });
          vMap.get(v).cnt++;
          vMap.get(v).gids.add(x.gid);
        });
        const vols = sortValuesClean([...vMap.keys()]).filter((k) => !br.stageFilter || k.includes(br.stageFilter));
        const cards = vols.map((v) => ({
          action: "pick-vol",
          val: v,
          icon: "📑",
          badge: `${vMap.get(v).gids.size} סדרות`,
          title: v,
          foot: `${vMap.get(v).cnt} שיעורים`,
        }));
        renderStepGrid(cards, { compact: true });
        return;
      }
      // Inside selected Tanya Perek -> show Series Cards for that Perek immediately!
      const pPool = bookPool.filter((x) => (x.v || "כללי") === br.v);
      const groups = buildTracksSeriesGroups(pPool);
      el.browseStepKicker.textContent = `שיעורים לסדרה — ${br.b}`;
      el.browseStepTitle.textContent = br.v;
      el.browseStepSub.textContent = `נמצאו ${groups.length} סדרות שיעורים שונות (${pPool.length} שיעורים סה"כ)`;
      renderSeriesList(el.browseStageContent, groups, { openAll: true, hidePath: true });
      return;
    }

    // Maamar-based Browse Mode for Hemshachim & Books with Multi-Maamar Series (e.g. המשך ס"ו)
    const hasMaamarMode = bookHasMultiMaamar(bookPool);
    if (hasMaamarMode && br.bookMode === "maamar") {
      if (!br.ma) {
        const maMap = new Map();
        bookPool.forEach((x) => {
          const ms = x.mas || [x.ma || x.v || "כללי"];
          ms.forEach((m) => {
            if (!maMap.has(m)) maMap.set(m, { cnt: 0, gids: new Set(), minOrd: 9999 });
            const info = maMap.get(m);
            info.cnt++;
            info.gids.add(x.gid);
            if (typeof x.mo === "number" && x.mo < info.minOrd) info.minOrd = x.mo;
          });
        });
        const maKeys = [...maMap.keys()].sort((a, b) => {
          const oa = maMap.get(a).minOrd, ob = maMap.get(b).minOrd;
          if (oa !== ob) return oa - ob;
          const ka = drillSortKey(a), kb = drillSortKey(b);
          return ka !== kb ? ka.localeCompare(kb, "en") : a.localeCompare(b, "he");
        });
        renderBookModeTools(maKeys.length > 6, "סנן לפי שם מאמר (לדוג' ביום השמיני, החודש, כי עמך)...");

        el.browseStepKicker.textContent = `שלב 4 — ${br.b} (לפי מאמר)`;
        el.browseStepTitle.textContent = "בחר מאמר לצפייה בכל הסדרות עליו";
        el.browseStepSub.textContent = `בחר מתוך ${maKeys.length} מאמרים — כל מאמר מאחד את כל הסדרות השיעורים העוסקות בו`;

        const filteredMas = maKeys.filter((m) => !br.stageFilter || normSearchText(m).includes(normSearchText(br.stageFilter)));
        const cards = filteredMas.map((m) => {
          const info = maMap.get(m);
          return {
            action: "pick-ma",
            val: m,
            icon: "📑",
            badge: `${info.gids.size} ${info.gids.size === 1 ? "סדרה" : "סדרות"}`,
            title: m,
            foot: `${info.cnt.toLocaleString("he-IL")} ${info.cnt === 1 ? "שיעור" : "שיעורים ברצף"}`,
          };
        });
        renderStepGrid(cards, { compact: filteredMas.length > 8 });
        return;
      }

      // Selected Maamar (`br.ma`): display every Series containing tracks for this Maamar cleanly numbered
      renderBookModeTools(false);
      const maPool = bookPool.filter((x) => (x.mas ? x.mas.includes(br.ma) : (x.ma || x.v || "כללי") === br.ma));
      const rawGroups = buildTracksSeriesGroups(maPool);
      const numberedGroups = rawGroups.map((g, i) => {
        const f = g.first;
        const baseSer = (f.ser && f.ser !== "היכל מנחם") ? f.ser : (SOURCES[f.src]?.name || "סדרה");
        const fromVol = f.v && f.v !== br.ma && !baseSer.includes(f.v) ? ` (מתוך: ${f.v})` : "";
        return {
          gid: `${g.gid}__ma__${br.ma}`,
          first: f,
          tracks: g.tracks,
          customTitle: rawGroups.length > 1
            ? `סדרה ${numToHebOrder(i + 1)}: ${baseSer}${fromVol}`
            : `${br.ma} — ${baseSer}${fromVol}`,
        };
      });

      el.browseStepKicker.textContent = `שיעורים לפי מאמר — ${br.b}`;
      el.browseStepTitle.textContent = br.ma;
      el.browseStepSub.textContent = `נמצאו ${numberedGroups.length} ${numberedGroups.length === 1 ? "סדרה" : "סדרות"} על מאמר זה (${maPool.length} שיעורים סה"כ) — לחץ להאזנה ברצף`;
      renderSeriesList(el.browseStageContent, numberedGroups, { openAll: numberedGroups.length <= 12, hidePath: true });
      return;
    }

    // STAGE 4 (Non-Tanya): Pick חלק / ספר המאמרים / פרשה / מועד / שנה / נושא
    if (!br.v) {
      const vMap = new Map();
      bookPool.forEach((x) => {
        const v = x.v || "כללי";
        if (!vMap.has(v)) vMap.set(v, { cnt: 0, gids: new Set(), minVo: 9999999 });
        const vi = vMap.get(v);
        vi.cnt++;
        vi.gids.add(x.gid);
        if (typeof x.vo === "number" && x.vo < vi.minVo) vi.minVo = x.vo;
      });
      const vols = [...vMap.keys()].sort((a, b) => {
        const oa = vMap.get(a).minVo, ob = vMap.get(b).minVo;
        if (oa !== ob) return oa - ob;
        const ka = drillSortKey(a), kb = drillSortKey(b);
        return ka !== kb ? ka.localeCompare(kb, "en") : a.localeCompare(b, "he");
      });

      // Auto-advance if only 1 trivial volume exists (like ניגוני חב"ד or ממשנת רבינו)
      if (vols.length === 1) {
        br.v = vols[0];
      } else {
        const lbls = BOOK_INFO[br.b] || ["חלק / פרק", "שיחה / מאמר"];
        el.browseStepKicker.textContent = `שלב 4 — ${br.b}`;
        el.browseStepTitle.textContent = `איזה ${lbls[0]}?`;
        el.browseStepSub.textContent = `בחר מתוך ${vols.length} חלקים וקבצים בתוך ${br.b}`;
        if (hasMaamarMode) renderBookModeTools(vols.length > 10, "סנן ברשימה זו...");
        else if (vols.length > 10) attachStageFilterInput("סנן ברשימה זו...");

        const filteredVols = vols.filter((v) => !br.stageFilter || normSearchText(v).includes(normSearchText(br.stageFilter)));
        const cards = filteredVols.map((v) => ({
          action: "pick-vol",
          val: v,
          icon: "📑",
          badge: `${vMap.get(v).cnt.toLocaleString("he-IL")} שיעורים`,
          title: v,
          foot: `${vMap.get(v).gids.size} סדרות`,
        }));
        renderStepGrid(cards, { compact: filteredVols.length > 8 });
        return;
      }
    }

    // Pool for selected Volume (`br.v`)
    let volPool = bookPool.filter((x) => (x.v || "כללי") === br.v);
    // Optional cross-book enrichment inside פרשיות השבוע / ענינא דיומא
    if ((br.cat === "פרשיות השבוע" || br.cat === "ענינא דיומא") && br.includeParshaBooks) {
      const extra = pool.filter((x) => x.cat !== br.cat && x.p === br.v);
      volPool = [...volPool, ...extra];
    }

    // STAGE 5: Check if there are multiple meaningful Maamarim / Sichos (`sec`) inside this `v`
    if (!br.sec) {
      const secMap = new Map();
      volPool.forEach((x) => {
        const s = x.sec || x.t;
        if (!secMap.has(s)) secMap.set(s, { cnt: 0, gids: new Set(), minMo: 9999999 });
        const si = secMap.get(s);
        si.cnt++;
        si.gids.add(x.gid);
        if (typeof x.mo === "number" && x.mo < si.minMo) si.minMo = x.mo;
      });
      const secs = [...secMap.keys()].sort((a, b) => {
        const oa = secMap.get(a).minMo, ob = secMap.get(b).minMo;
        if (oa !== ob) return oa - ob;
        const ka = drillSortKey(a), kb = drillSortKey(b);
        return ka !== kb ? ka.localeCompare(kb, "en") : a.localeCompare(b, "he");
      });

      // Skip Step 5 ONLY when sec === v OR when inside Chazaros / Nigunim / PDF singletons
      const isSingletonCollection =
        secs.length <= 1 ||
        br.cat === "חזרות והתוועדויות" ||
        br.cat === "ניגונים" ||
        br.cat === "ספרים וכתבים (PDF)";

      if (!isSingletonCollection) {
        const lbls = BOOK_INFO[br.b] || ["חלק", "שיחה / מאמר"];
        el.browseStepKicker.textContent = `שלב 5 — ${br.b} › ${br.v}`;
        el.browseStepTitle.textContent = `איזה ${lbls[1]}?`;
        el.browseStepSub.textContent = `בחר מתוך ${secs.length} נושאים/מאמרים כדי לראות את סדרות השיעורים ברצף`;

        const tools = [];
        if (secs.length > 10) tools.push("filter");
        if ((br.cat === "פרשיות השבוע" || br.cat === "ענינא דיומא")) tools.push("cross");
        if (hasMaamarMode) renderBookModeTools(secs.length > 10, "סנן מאמרים / שיחות...");
        else renderVolTools(tools);

        const filteredSecs = secs.filter((s) => !br.stageFilter || normSearchText(s).includes(normSearchText(br.stageFilter)));
        const cards = filteredSecs.map((s) => {
          const info = secMap.get(s);
          return {
            action: "pick-sec",
            val: s,
            icon: "📖",
            badge: `${info.gids.size} ${info.gids.size === 1 ? "סדרה" : "סדרות"}`,
            title: s,
            foot: `${info.cnt} ${info.cnt === 1 ? "שיעור" : "שיעורים ברצף"}`,
          };
        });
        renderStepGrid(cards, { compact: filteredSecs.length > 8 });
        return;
      }
    }

    // STAGE 6: Final Leaf View — Grouped Sequential Series!
    const leafPool = br.sec ? volPool.filter((x) => (x.sec || x.t) === br.sec) : volPool;
    const seriesGroups = buildTracksSeriesGroups(leafPool);
    const leafTitle = br.sec || br.v;

    if (hasMaamarMode) renderBookModeTools(false);
    else if (br.cat === "פרשיות השבוע" || br.cat === "ענינא דיומא") renderVolTools(["cross"]);
    el.browseStepKicker.textContent = `שלב אחרון — סדרות שיעורים ברצף`;
    el.browseStepTitle.textContent = leafTitle;
    el.browseStepSub.textContent = `${seriesGroups.length} ${seriesGroups.length === 1 ? "סדרת שיעורים" : "סדרות שיעורים"} (${leafPool.length} שיעורים סה"כ) — בחר סדרה והאזן ברצף`;

    renderSeriesList(el.browseStageContent, seriesGroups, { openAll: seriesGroups.length <= 12, hidePath: true });
  }

  function renderTanyaTools(showFilter) {
    const br = state.browse;
    el.browseStepTools.innerHTML = `
      <div class="tanya-mode-switch">
        <button type="button" class="tm-btn ${br.tanyaMode === "perek" ? "active" : ""}" data-tmode="perek">📑 לפי פרק בתניא</button>
        <button type="button" class="tm-btn ${br.tanyaMode === "cycle" ? "active" : ""}" data-tmode="cycle">🎬 לפי סדרה שלמה</button>
      </div>`;
    if (showFilter) attachStageFilterInput("סנן פרק או סדרה...");
  }

  function renderBookModeTools(showFilter, placeholder = "סנן מאמר...") {
    const br = state.browse;
    el.browseStepTools.innerHTML = `
      <div class="tanya-mode-switch">
        <button type="button" class="tm-btn ${br.bookMode === "vol" ? "active" : ""}" data-bmode="vol">📚 לפי סדרות / חבילות</button>
        <button type="button" class="tm-btn ${br.bookMode === "maamar" ? "active" : ""}" data-bmode="maamar">📑 לפי מאמר (מחולק לפי סדרות)</button>
      </div>`;
    if (showFilter) attachStageFilterInput(placeholder);
  }

  function attachStageFilterInput(placeholder) {
    _stageFilterNeeded = true;
    el.stageFilterInput.placeholder = placeholder || "סנן ברשימה זו...";
  }

  function renderVolTools(tools) {
    const br = state.browse;
    let html = "";
    if (tools.includes("cross")) {
      html += `<button type="button" class="mini-pill ${br.includeParshaBooks ? "active" : ""}" id="toggleCrossParshaBtn">📚 כלול גם שיחות ומאמרים משאר הספרים</button>`;
    }
    el.browseStepTools.innerHTML = html;
    if (tools.includes("filter")) attachStageFilterInput("סנן מאמרים / שיחות...");
  }

  // =========================================================================
  // Shared Renderer for Sequential Series Cards
  // =========================================================================
  function renderSeriesList(container, groups, opts = {}) {
    if (!groups.length) {
      container.innerHTML = `<div class="empty-state"><h3>לא נמצאו שיעורים תואמים</h3></div>`;
      return;
    }

    container.innerHTML = `<div class="series-stack">${groups.map((grp) => {
      if (grp.customTitle || !GROUPS_MAP.has(grp.gid)) GROUPS_MAP.set(grp.gid, grp.tracks);
      const f = grp.first;
      const tracks = grp.tracks;
      const isMulti = tracks.length >= 2;
      const isExpanded = opts.openAll || state.expandedSeries.has(grp.gid) || tracks.length <= 5;
      const visibleTracks = isExpanded ? tracks : tracks.slice(0, 3);
      const hiddenCnt = tracks.length - visibleTracks.length;

      const seriesTitle = grp.customTitle || (isMulti ? (f.ser || f.sec || f.t) : f.t);
      const pathParts = [f.cat, f.r, f.b, f.v, (f.sec && f.sec !== f.v ? f.sec : "")].filter(Boolean);
      const totalDur = tracks.reduce((acc, t) => acc + (t.d || 0), 0);
      const hasAu = tracks.some((t) => !!t.au);
      const hasDr = tracks.some((t) => !!t.dr);
      const hasVi = tracks.some((t) => !!t.vi);
      const srcName = SOURCES[f.src]?.name || f.src;
      const cardSrcUrl = getSourceUrl(f);
      const yrBadge = f.y?.length ? `<span class="badge badge-year">${escHtml(f.y[0])}</span>` : "";

      // Action button for playing entire series cleanly
      let playAllBtn = "";
      if (isMulti) {
        if (hasAu) {
          playAllBtn = `<button type="button" class="series-play-all-btn" data-action="play-series" data-gid="${escHtml(grp.gid)}">▶ נגן סדרה מההתחלה (${tracks.length})</button>`;
        } else if (hasDr || hasVi) {
          playAllBtn = `<button type="button" class="series-play-all-btn" data-action="play-series-modal" data-gid="${escHtml(grp.gid)}">▶ פתח סדרה מתחילה (${tracks.length})</button>`;
        }
      }

      return `
        <article class="series-card" data-gid="${escHtml(grp.gid)}">
          <div class="series-card-head">
            <div class="series-meta-col">
              ${opts.hidePath ? "" : `<div class="series-path-line">${escHtml(pathParts.join(" › "))}</div>`}
              <div class="series-title-row">
                <h3 class="series-title">${escHtml(seriesTitle)}</h3>
                ${isMulti ? `<span class="badge badge-series badge-series-count">📚 סדרה — ${tracks.length} שיעורים ברצף</span>` : ""}
              </div>
              <div class="series-badges">
                ${getLangBadges(f)}
                ${yrBadge}
                ${!isMulti && f.ser && f.ser !== (SOURCES[f.src]?.name) && f.ser !== seriesTitle ? `<span class="badge badge-series">${escHtml(f.ser)}</span>` : ""}
                ${cardSrcUrl
                  ? `<a class="badge badge-link ${f.src === "gdrive" ? "badge-gdrive" : ""}" href="${escHtml(cardSrcUrl)}" target="_blank" rel="noopener" title="עבור לדף המקור של השיעור">🔗 מקור: ${escHtml(srcName)} ↗</a>`
                  : `<span class="badge ${f.src === "gdrive" ? "badge-gdrive" : ""}">${escHtml(srcName)}</span>`}
                ${totalDur > 0 ? `<span class="badge">⏱️ ${formatTime(totalDur)}</span>` : ""}
              </div>
            </div>
            <div class="series-head-actions">
              ${playAllBtn}
              <button type="button" class="btn-ghost btn-sm" data-action="share-series" data-id="${escHtml(f.id)}" title="העתק קישור ישיר לסדרה">📤 שתף</button>
            </div>
          </div>

          <div class="series-tracks-list">
            ${visibleTracks.map((tr, i) => renderSeriesTrackRow(tr, i + 1, grp.gid)).join("")}
          </div>

          ${hiddenCnt > 0 ? `<button type="button" class="series-expand-btn" data-action="expand-series" data-gid="${escHtml(grp.gid)}">הצג את כל ${tracks.length} שיעורי הסדרה (+${hiddenCnt} נוספים) ⌄</button>` : ""}
        </article>`;
    }).join("")}</div>`;
  }

  function renderSeriesTrackRow(it, num, gid) {
    const isPlaying = state.currentTrackId === it.id;
    const isSaved = state.bookmarks.has(it.id);
    const dlUrl = getDirectDownloadUrl(it);
    const srcUrl = getSourceUrl(it);
    const prog = state.progress[it.id];
    const resumeHint = prog && prog.t > 15 && (!prog.d || prog.t < prog.d - 20) ? `המשך מ-${formatTime(prog.t)}` : "";

    const btns = [];
    if (it.au) btns.push(`<button type="button" class="play-chip-btn" data-action="play-audio" data-id="${escHtml(it.id)}" data-gid="${escHtml(gid || it.gid)}">▶ האזן</button>`);
    if (it.dr) btns.push(`<button type="button" class="play-chip-btn" data-action="play-drive" data-id="${escHtml(it.id)}" data-gid="${escHtml(gid || it.gid)}">☁️ האזן (Drive)</button>`);
    if (it.vi) btns.push(`<button type="button" class="play-chip-btn gold" data-action="play-video" data-id="${escHtml(it.id)}" data-gid="${escHtml(gid || it.gid)}">🎬 וידאו</button>`);
    if (it.pd) btns.push(`<button type="button" class="play-chip-btn" data-action="open-pdf" data-id="${escHtml(it.id)}">📄 PDF / מסמך</button>`);
    if (srcUrl) btns.push(`<a class="btn-ghost btn-sm" href="${escHtml(srcUrl)}" target="_blank" rel="noopener" title="פתח דף מקור השיעור">🔗 מקור ↗</a>`);
    if (dlUrl) btns.push(`<a class="btn-ghost btn-sm" href="${escHtml(dlUrl)}" target="_blank" rel="noopener" title="פתח / הורד קובץ">⬇</a>`);
    btns.push(`<button type="button" class="bookmark-btn ${isSaved ? "saved" : ""}" data-action="bookmark" data-id="${escHtml(it.id)}" title="שמור בסימניות">${isSaved ? "🔖" : "☆"}</button>`);

    return `
      <div class="series-track-row ${isPlaying ? "playing-now" : ""}">
        <div class="track-main-info">
          <span class="track-num-badge">${num}</span>
          <div class="track-title-col">
            <div class="track-title">${escHtml(it.t)}</div>
            <div class="track-sub-meta">
              ${it.d > 0 ? `<span>⏱️ ${formatTime(it.d)}</span>` : ""}
              ${it.p ? `<span>📖 ${escHtml(it.p)}</span>` : ""}
              ${it.ts && !(it.ser || "").includes(it.ts) ? `<span>${escHtml(it.ts)}</span>` : ""}
              ${resumeHint ? `<span style="color:var(--gold);font-weight:700">${escHtml(resumeHint)}</span>` : ""}
            </div>
          </div>
        </div>
        <div class="track-actions">${btns.join("")}</div>
      </div>`;
  }

  function renderFlatCards(container, items) {
    if (!items.length) {
      container.innerHTML = `<div class="empty-state"><h3>לא נמצאו פריטים להצגה</h3></div>`;
      return;
    }
    container.innerHTML = items.map((it) => {
      const isSaved = state.bookmarks.has(it.id);
      const dlUrl = getDirectDownloadUrl(it);
      const srcUrl = getSourceUrl(it);
      const srcName = SOURCES[it.src]?.name || it.src;
      const btns = [];
      if (it.au) btns.push(`<button type="button" class="play-chip-btn" data-action="play-audio" data-id="${escHtml(it.id)}">▶ האזן</button>`);
      if (it.dr) btns.push(`<button type="button" class="play-chip-btn" data-action="play-drive" data-id="${escHtml(it.id)}">☁️ האזן (Drive)</button>`);
      if (it.vi) btns.push(`<button type="button" class="play-chip-btn gold" data-action="play-video" data-id="${escHtml(it.id)}">🎬 וידאו</button>`);
      if (it.pd) btns.push(`<button type="button" class="play-chip-btn" data-action="open-pdf" data-id="${escHtml(it.id)}">📄 פתח</button>`);
      if (srcUrl) btns.push(`<a class="btn-ghost btn-sm" href="${escHtml(srcUrl)}" target="_blank" rel="noopener">🔗 מקור ↗</a>`);
      if (dlUrl) btns.push(`<a class="btn-ghost btn-sm" href="${escHtml(dlUrl)}" target="_blank" rel="noopener">⬇ הורד</a>`);

      return `
        <article class="track-flat-card">
          <div>
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;">
              <h3 class="flat-card-title">${escHtml(it.t)}</h3>
              <button type="button" class="bookmark-btn ${isSaved ? "saved" : ""}" data-action="bookmark" data-id="${escHtml(it.id)}">${isSaved ? "🔖" : "☆"}</button>
            </div>
            <p class="flat-card-sub">${escHtml([it.r, it.b, it.v, it.sec].filter(Boolean).join(" › "))}</p>
            <div class="series-badges" style="margin-top:8px;">
              ${getFormatBadges(it)} ${getLangBadges(it)}
              ${srcUrl
                ? `<a class="badge badge-link ${it.src === "gdrive" ? "badge-gdrive" : ""}" href="${escHtml(srcUrl)}" target="_blank" rel="noopener">🔗 ${escHtml(srcName)} ↗</a>`
                : `<span class="badge">${escHtml(srcName)}</span>`}
            </div>
          </div>
          <div class="track-actions">${btns.join("")}</div>
        </article>`;
    }).join("");
  }

  // =========================================================================
  // VIEW 2: Search & Faceted Catalog (with Series Grouping)
  // =========================================================================
  let _catalogStreamActive = false;
  function startCatalogChunksStream() {
    if (allDataChunksLoaded()) {
      el.catalogLoadingBar?.classList.add("hidden");
      return;
    }
    if (_catalogStreamActive) return;
    _catalogStreamActive = true;
    const total = ALL_DATA_CHUNKS.length;
    const loadedNow = ALL_DATA_CHUNKS.filter((c) => _loadedChunks.has(c)).length;
    el.catalogLoadingBar?.classList.remove("hidden");
    if (el.catalogLoadingText) {
      el.catalogLoadingText.textContent = `טוען את כל מאגר החיפוש (${loadedNow} מתוך ${total})...`;
    }
    ensureAllChunks((done, tot) => {
      if (el.catalogLoadingText) {
        el.catalogLoadingText.textContent = `טוען את כל מאגר החיפוש (${done} מתוך ${tot})...`;
      }
      if (state.view === "catalog") applyCatalogFilters(false, "none");
    }).then(() => {
      _catalogStreamActive = false;
      el.catalogLoadingBar?.classList.add("hidden");
      if (state.view === "catalog") applyCatalogFilters(false, "none");
    }).catch(() => {
      _catalogStreamActive = false;
      el.catalogLoadingBar?.classList.add("hidden");
    });
  }

  function applyCatalogFilters(resetPage = true, urlMode = "push") {
    const f = state.filters;
    const qNorm = normSearchText(f.q);
    const terms = qNorm ? qNorm.split(" ").filter(Boolean) : [];

    const out = [];
    for (let i = 0; i < ITEMS.length; i++) {
      const it = ITEMS[i];
      if (f.lang !== "all" && !(it.l || []).includes(f.lang)) continue;
      if (f.format !== "all" && !(it.f || []).includes(f.format)) continue;
      if (f.cat !== "all" && it.cat !== f.cat) continue;
      if (f.rebbe !== "all" && it.r !== f.rebbe) continue;
      if (f.book !== "all" && it.b !== f.book) continue;
      if (f.vol !== "all" && it.v !== f.vol) continue;
      if (f.sec !== "all" && it.sec !== f.sec) continue;
      if (f.yearMode === "decades" && f.decade !== "all" && !(it.decs || []).includes(f.decade)) continue;
      if (f.yearMode === "years" && f.year !== "all" && !(it.y || []).includes(f.year)) continue;
      if (f.parsha !== "all" && it.p !== f.parsha) continue;
      if (f.source !== "all" && it.src !== f.source) continue;
      if (terms.length) {
        const hay = SEARCH_INDEX[i];
        let ok = true;
        for (const t of terms) {
          if (!hay.includes(t)) { ok = false; break; }
        }
        if (!ok) continue;
      }
      out.push(it);
    }

    if (f.sort === "year_asc") out.sort((a, b) => (a.yn || 99999) - (b.yn || 99999) || (a.ord || 0) - (b.ord || 0));
    else if (f.sort === "year_desc") out.sort((a, b) => (b.yn || 0) - (a.yn || 0) || (a.ord || 0) - (b.ord || 0));
    else if (f.sort === "title_asc") out.sort((a, b) => a.t.localeCompare(b.t, "he"));
    else if (f.sort === "dur_desc") out.sort((a, b) => (b.d || 0) - (a.d || 0));

    state.filtered = out;
    state.groupedSeries = buildTracksSeriesGroups(out);
    if (resetPage) state.page = 1;
    if (state.view === "catalog") {
      renderCatalog();
      if (urlMode !== "none" && urlMode !== true) syncUrlState(urlMode === "push");
    }
  }

  function renderSidebarFacets() {
    const f = state.filters;
    const baseFor = (excludeKey) => ITEMS.filter((it, idx) => {
      if (excludeKey !== "lang" && f.lang !== "all" && !(it.l || []).includes(f.lang)) return false;
      if (excludeKey !== "format" && f.format !== "all" && !(it.f || []).includes(f.format)) return false;
      if (excludeKey !== "cat" && f.cat !== "all" && it.cat !== f.cat) return false;
      if (excludeKey !== "rebbe" && f.rebbe !== "all" && it.r !== f.rebbe) return false;
      if (excludeKey !== "book" && f.book !== "all" && it.b !== f.book) return false;
      if (excludeKey !== "vol" && f.vol !== "all" && it.v !== f.vol) return false;
      if (excludeKey !== "sec" && f.sec !== "all" && it.sec !== f.sec) return false;
      if (excludeKey !== "year" && f.yearMode === "decades" && f.decade !== "all" && !(it.decs || []).includes(f.decade)) return false;
      if (excludeKey !== "year" && f.yearMode === "years" && f.year !== "all" && !(it.y || []).includes(f.year)) return false;
      if (excludeKey !== "parsha" && f.parsha !== "all" && it.p !== f.parsha) return false;
      if (excludeKey !== "source" && f.source !== "all" && it.src !== f.source) return false;
      if (f.q) {
        const hay = SEARCH_INDEX[idx];
        for (const t of normSearchText(f.q).split(" ").filter(Boolean)) if (!hay.includes(t)) return false;
      }
      return true;
    });

    const optBtn = (filterName, val, label, count, curVal) => `
      <button type="button" class="filter-opt-btn ${curVal === val ? "active" : ""}" data-filter="${filterName}" data-val="${escHtml(val)}">
        <span>${escHtml(label)}</span>
        <span class="opt-count">${count.toLocaleString("he-IL")}</span>
      </button>`;

    const lPool = baseFor("lang");
    el.filterLangList.innerHTML =
      optBtn("lang", "all", "כל השפות", lPool.length, f.lang) +
      ["yi", "he", "en"].map((k) => optBtn("lang", k, LANG_META[k].label, lPool.filter((x) => (x.l || []).includes(k)).length, f.lang)).join("");

    const fPool = baseFor("format");
    el.filterFormatList.innerHTML =
      optBtn("format", "all", "הכל", fPool.length, f.format) +
      ["audio", "video", "pdf"].map((k) => optBtn("format", k, `${FMT_META[k].icon} ${FMT_META[k].label}`, fPool.filter((x) => (x.f || []).includes(k)).length, f.format)).join("");

    const cPool = baseFor("cat");
    el.filterCatList.innerHTML =
      optBtn("cat", "all", "כל המדורים", cPool.length, f.cat) +
      CAT_ORDER.map((c) => {
        const cnt = cPool.filter((x) => x.cat === c).length;
        return cnt ? optBtn("cat", c, c, cnt, f.cat) : "";
      }).join("");

    const rPool = baseFor("rebbe");
    const showRebbe = f.cat === "all" || f.cat === "ספרים";
    el.filterRebbeGroup.classList.toggle("hidden", !showRebbe);
    el.filterRebbeList.innerHTML =
      optBtn("rebbe", "all", "כל רבותינו נשיאינו", rPool.length, f.rebbe) +
      REBBE_ORDER.map((rb) => {
        const cnt = rPool.filter((x) => x.r === rb).length;
        return cnt ? optBtn("rebbe", rb, rb, cnt, f.rebbe) : "";
      }).join("");

    const bPool = baseFor("book");
    const bCnt = new Map();
    bPool.forEach((x) => bCnt.set(x.b, (bCnt.get(x.b) || 0) + 1));
    const bKeys = sortValuesClean([...bCnt.keys()]);
    el.filterBookList.innerHTML =
      optBtn("book", "all", "כל הספרים", bPool.length, f.book) +
      bKeys.map((bk) => optBtn("book", bk, bk, bCnt.get(bk), f.book)).join("");

    if (f.book !== "all") {
      const vPool = baseFor("vol");
      const vCnt = new Map();
      vPool.forEach((x) => { if (x.v) vCnt.set(x.v, (vCnt.get(x.v) || 0) + 1); });
      const vKeys = sortValuesClean([...vCnt.keys()]);
      el.filterVolGroup.classList.toggle("hidden", vKeys.length < 2);
      el.filterVolTitle.textContent = (BOOK_INFO[f.book]?.[0]) || "חלק / פרק";
      el.filterVolList.innerHTML =
        optBtn("vol", "all", "הכל", vPool.length, f.vol) +
        vKeys.map((vk) => optBtn("vol", vk, vk, vCnt.get(vk), f.vol)).join("");
    } else {
      el.filterVolGroup.classList.add("hidden");
      el.filterSecGroup.classList.add("hidden");
    }

    if (f.book !== "all" && f.vol !== "all") {
      const sPool = baseFor("sec");
      const sCnt = new Map();
      sPool.forEach((x) => { if (x.sec) sCnt.set(x.sec, (sCnt.get(x.sec) || 0) + 1); });
      const sKeys = sortValuesClean([...sCnt.keys()]);
      el.filterSecGroup.classList.toggle("hidden", sKeys.length < 2);
      el.filterSecTitle.textContent = (BOOK_INFO[f.book]?.[1]) || "שיחה / מאמר";
      el.filterSecList.innerHTML =
        optBtn("sec", "all", "הכל", sPool.length, f.sec) +
        sKeys.map((sk) => optBtn("sec", sk, sk, sCnt.get(sk), f.sec)).join("");
    } else {
      el.filterSecGroup.classList.add("hidden");
    }

    const yPool = baseFor("year");
    const yCnt = new Map();
    yPool.forEach((x) => (f.yearMode === "decades" ? x.decs : x.y).forEach((v) => yCnt.set(v, (yCnt.get(v) || 0) + 1)));
    const yKeys = sortValuesClean([...yCnt.keys()]);
    el.filterYearList.innerHTML =
      optBtn(f.yearMode === "decades" ? "decade" : "year", "all", "כל השנים", yPool.length, f.yearMode === "decades" ? f.decade : f.year) +
      yKeys.map((yk) => optBtn(f.yearMode === "decades" ? "decade" : "year", yk, yk, yCnt.get(yk), f.yearMode === "decades" ? f.decade : f.year)).join("");

    const pPool = baseFor("parsha");
    const pCnt = new Map();
    pPool.forEach((x) => { if (x.p) pCnt.set(x.p, (pCnt.get(x.p) || 0) + 1); });
    const pKeys = sortValuesClean([...pCnt.keys()]);
    el.filterParshaList.innerHTML =
      optBtn("parsha", "all", "כל הפרשיות והמועדים", pPool.length, f.parsha) +
      pKeys.map((pk) => optBtn("parsha", pk, pk, pCnt.get(pk), f.parsha)).join("");

    const sPool = baseFor("source");
    const sCnt = new Map();
    sPool.forEach((x) => sCnt.set(x.src, (sCnt.get(x.src) || 0) + 1));
    el.filterSourceList.innerHTML =
      optBtn("source", "all", "כל המקורות", sPool.length, f.source) +
      [...sCnt.entries()].sort((a, b) => b[1] - a[1]).map(([k, cnt]) => optBtn("source", k, SOURCES[k]?.name || k, cnt, f.source)).join("");
  }

  function renderActiveChips() {
    const f = state.filters;
    const chips = [];
    if (f.q) chips.push(["q", `חיפוש: "${f.q}"`]);
    if (f.lang !== "all") chips.push(["lang", `שפה: ${LANG_META[f.lang]?.label || f.lang}`]);
    if (f.format !== "all") chips.push(["format", `מדיה: ${FMT_META[f.format]?.label || f.format}`]);
    if (f.cat !== "all") chips.push(["cat", `מדור: ${f.cat}`]);
    if (f.rebbe !== "all") chips.push(["rebbe", `אדמו"ר: ${f.rebbe}`]);
    if (f.book !== "all") chips.push(["book", `ספר: ${f.book}`]);
    if (f.vol !== "all") chips.push(["vol", `חלק: ${f.vol}`]);
    if (f.sec !== "all") chips.push(["sec", `מאמר: ${f.sec}`]);
    if (f.yearMode === "decades" && f.decade !== "all") chips.push(["decade", `תקופה: ${f.decade}`]);
    if (f.yearMode === "years" && f.year !== "all") chips.push(["year", `שנה: ${f.year}`]);
    if (f.parsha !== "all") chips.push(["parsha", `פרשה/מועד: ${f.parsha}`]);
    if (f.source !== "all") chips.push(["source", `מקור: ${SOURCES[f.source]?.name || f.source}`]);

    if (!chips.length) {
      el.activeChipsBar.classList.add("hidden");
      el.activeChipsBar.innerHTML = "";
      return;
    }
    el.activeChipsBar.classList.remove("hidden");
    el.activeChipsBar.innerHTML = chips.map(([k, lbl]) => `
      <span class="active-chip">${escHtml(lbl)} <button type="button" data-clear-chip="${k}" title="הסר">&times;</button></span>
    `).join("") + `<button type="button" class="text-link-btn" id="chipsClearAll">נקה הכל</button>`;
  }

  function renderCatalog() {
    renderSidebarFacets();
    renderActiveChips();

    const listSource = state.catalogMode === "series" ? state.groupedSeries : state.filtered;
    const totalItems = state.filtered.length;
    const totalGroups = state.groupedSeries.length;
    const pageCount = Math.max(1, Math.ceil(listSource.length / state.pageSize));
    if (state.page > pageCount) state.page = pageCount;

    const start = (state.page - 1) * state.pageSize;
    const slice = listSource.slice(start, start + state.pageSize);

    if (totalItems === 0) {
      el.resultsSummary.textContent = "0 תוצאות";
      el.mobileResultsCount.textContent = "0 תוצאות";
      if (el.mobileDrawerDoneBtn) el.mobileDrawerDoneBtn.textContent = "אין תוצאות — חזרה ✕";
      el.resultsList.innerHTML = "";
      el.emptyState.classList.remove("hidden");
      el.paginationBar.innerHTML = "";
      return;
    }

    el.emptyState.classList.add("hidden");
    const summaryText = state.catalogMode === "series"
      ? `מציג ${start + 1}–${start + slice.length} מתוך ${totalGroups.toLocaleString("he-IL")} סדרות ופריטים (${totalItems.toLocaleString("he-IL")} שיעורים סה"כ)`
      : `מציג ${start + 1}–${start + slice.length} מתוך ${totalItems.toLocaleString("he-IL")} שיעורים`;
    el.resultsSummary.textContent = summaryText;
    el.mobileResultsCount.textContent = `${totalItems.toLocaleString("he-IL")} שיעורים`;
    if (el.mobileDrawerDoneBtn) el.mobileDrawerDoneBtn.textContent = `הצג ${totalItems.toLocaleString("he-IL")} שיעורים ✓`;

    if (state.catalogMode === "series") {
      el.resultsList.className = "results-flow";
      renderSeriesList(el.resultsList, slice);
    } else {
      el.resultsList.className = "results-flat-grid";
      renderFlatCards(el.resultsList, slice);
    }

    // Pagination
    if (pageCount <= 1) { el.paginationBar.innerHTML = ""; return; }
    let html = `<button type="button" class="page-btn" data-page="${state.page - 1}" ${state.page === 1 ? "disabled" : ""}>הקודם</button>`;
    const pages = new Set([1, pageCount]);
    for (let p = Math.max(1, state.page - 2); p <= Math.min(pageCount, state.page + 2); p++) pages.add(p);
    let prev = 0;
    [...pages].sort((a, b) => a - b).forEach((p) => {
      if (prev && p - prev > 1) html += `<span style="padding:0 4px;color:var(--text-light)">...</span>`;
      html += `<button type="button" class="page-btn ${p === state.page ? "active" : ""}" data-page="${p}">${p}</button>`;
      prev = p;
    });
    html += `<button type="button" class="page-btn" data-page="${state.page + 1}" ${state.page === pageCount ? "disabled" : ""}>הבא</button>`;
    el.paginationBar.innerHTML = html;
  }

  // =========================================================================
  // VIEW 3 & 4: PDF Seforim & Saved
  // =========================================================================
  let _pdfLoadStarted = false;
  function renderSeforimPdfView() {
    if (CHUNKS_META["_pdf_all"] && !_loadedChunks.has("_pdf_all")) {
      el.seforimPdfGrid.innerHTML = `<div class="chunk-loading-box"><div class="loading-spinner"></div><div><strong>טוען ספרים וכתבי יד...</strong></div></div>`;
      if (!_pdfLoadStarted) {
        _pdfLoadStarted = true;
        ensureSeforimPdfChunk().then(() => {
          _pdfLoadStarted = false;
          if (state.view === "seforim") renderSeforimPdfView();
        }).catch(() => { _pdfLoadStarted = false; });
      }
      return;
    }
    const pdfs = ITEMS.filter((it) => (it.f || []).includes("pdf") && (state.pdfLang === "all" || (it.l || []).includes(state.pdfLang)));
    renderFlatCards(el.seforimPdfGrid, pdfs);
  }

  function renderSavedView() {
    el.navSavedCount.textContent = state.bookmarks.size.toLocaleString("he-IL");
    const neededIds = [...new Set([...state.bookmarks, ...state.history])].filter((id) => id && !ITEMS_BY_ID.has(id));
    if (neededIds.length && ALL_DATA_CHUNKS.length) {
      el.bookmarksList.innerHTML = `<div class="chunk-loading-box"><div class="loading-spinner"></div><div><strong>טוען פריטים שמורים...</strong></div></div>`;
      ensureItemsByIds(neededIds).then(() => {
        if (state.view === "saved") renderSavedView();
      }).catch(() => {});
      return;
    }
    const bmItems = [...state.bookmarks].map((id) => ITEMS_BY_ID.get(id)).filter(Boolean);
    renderFlatCards(el.bookmarksList, bmItems);
    const histItems = state.history.map((id) => ITEMS_BY_ID.get(id)).filter(Boolean);
    renderFlatCards(el.historyList, histItems);
  }

  function renderResumeBanner() {
    if (!state.history.length) { el.resumeBanner.classList.add("hidden"); return; }
    const lastId = state.history[0];
    if (!ITEMS_BY_ID.has(lastId)) {
      if (ALL_DATA_CHUNKS.length) {
        ensureItemsByIds([lastId]).then(() => {
          if (ITEMS_BY_ID.has(lastId)) renderResumeBanner();
        }).catch(() => {});
      }
      return;
    }
    const last = ITEMS_BY_ID.get(lastId);
    if (!last || (!last.au && !last.dr)) { el.resumeBanner.classList.add("hidden"); return; }
    const prog = state.progress[last.id];
    const timeStr = prog && prog.t > 10 ? ` (עצרת ב-${formatTime(prog.t)})` : "";
    el.resumeBanner.classList.remove("hidden");
    el.resumeBanner.innerHTML = `
      <div>
        <strong>🕒 המשך לימוד מאיפה שעצרת:</strong>
        <span>${escHtml(last.t)}${escHtml(timeStr)}</span>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button type="button" class="btn-primary btn-sm" id="resumePlayBtn">▶ המשך עכשיו</button>
        <button type="button" class="btn-ghost btn-sm" id="dismissResumeBtn">סגור</button>
      </div>`;
    $("resumePlayBtn")?.addEventListener("click", () => {
      if (last.au) startAudioQueue([last], 0, last.ser || "");
      else if (last.dr) openMediaModal(last, "drive");
    });
    $("dismissResumeBtn")?.addEventListener("click", () => el.resumeBanner.classList.add("hidden"));
  }

  // =========================================================================
  // Audio Player & Series Queue
  // =========================================================================
  function pushHistory(id) {
    state.history = [id, ...state.history.filter((x) => x !== id)].slice(0, 40);
    saveJSON(LS_KEYS.history, state.history);
  }

  function startSeriesPlayback(gid, startTrackId = null, opts = {}) {
    const rawTracks = GROUPS_MAP.get(gid) || [];
    const audioTracks = rawTracks.filter((t) => !!t.au);
    if (!audioTracks.length) {
      // Fallback: Drive / Video series modal
      const target = (startTrackId && ITEMS_BY_ID.get(startTrackId)) || rawTracks[0];
      if (target) openMediaModal(target, target.dr ? "drive" : (target.vi ? "video" : "pdf"), gid, opts);
      return;
    }
    let idx = startTrackId ? audioTracks.findIndex((t) => t.id === startTrackId) : 0;
    if (idx < 0) idx = 0;
    const serLabel = audioTracks[0].ser || audioTracks[0].sec || audioTracks[0].b;
    startAudioQueue(audioTracks, idx, serLabel, opts);
  }

  function startAudioQueue(tracks, idx, seriesLabel = "", opts = {}) {
    if (!tracks.length || !tracks[idx]?.au) return;
    state.queue = tracks;
    state.queueIndex = idx;
    state.queueSeriesName = seriesLabel;
    const it = tracks[idx];
    state.currentTrackId = it.id;
    state.urlShiurId = it.id;
    if (!opts.fromUrl) syncUrlState(!opts.replaceUrl);

    el.audioPlayerBar.classList.remove("hidden");
    document.body.classList.add("has-player");
    el.playerErrorBanner?.classList.add("hidden");
    el.playerSeferBadge.textContent = it.b || it.cat;
    el.playerTitle.textContent = it.t;
    const qNote = tracks.length > 1 ? ` • שיעור ${idx + 1} מתוך ${tracks.length} בסדרה${seriesLabel ? ` (${seriesLabel})` : ""}` : "";
    el.playerSub.textContent = (SOURCES[it.src]?.name || it.src) + qNote;
    const srcUrl = getSourceUrl(it);
    const dlUrl = getDirectDownloadUrl(it);
    if (el.playerSourceLink) {
      el.playerSourceLink.href = srcUrl || "#";
      el.playerSourceLink.classList.toggle("hidden", !srcUrl);
    }
    el.playerDownloadLink.href = dlUrl || "#";
    el.playerDownloadLink.classList.toggle("hidden", !dlUrl);

    el.playerSeek.value = 0;
    el.playerCurrentTime.textContent = "00:00";
    el.playerDuration.textContent = formatTime(it.d);
    el.nativeAudio.src = it.au;
    el.nativeAudio.playbackRate = state.speeds[state.speedIdx];
    const saved = state.progress[it.id];
    const startAt = saved && saved.t > 12 && (!saved.d || saved.t < saved.d - 20) ? saved.t : 0;
    el.nativeAudio.onloadedmetadata = () => {
      try {
        if (startAt && el.nativeAudio.duration && startAt < el.nativeAudio.duration - 10) {
          el.nativeAudio.currentTime = startAt;
        }
      } catch {}
      el.playerDuration.textContent = formatTime(el.nativeAudio.duration || it.d);
    };
    el.playerPlayPauseBtn.textContent = "⏳";
    const playPromise = el.nativeAudio.play();
    if (playPromise && typeof playPromise.then === "function") {
      playPromise.then(() => {
        el.playerErrorBanner?.classList.add("hidden");
        if (!el.nativeAudio.paused) el.playerPlayPauseBtn.textContent = "⏸";
      }).catch((err) => {
        if (err && err.name === "AbortError") return;
        el.playerPlayPauseBtn.textContent = "▶";
        if (el.nativeAudio.error || (err && err.name === "NotSupportedError")) {
          showAudioError(it);
        }
      });
    }
    pushHistory(it.id);

    // Register Smartphone Lock-Screen / Media Key Controls
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: it.t,
          artist: 'הגה"ח רבי יואל כהן ע"ה',
          album: [it.b, it.sec || it.v].filter(Boolean).join(" › "),
        });
        navigator.mediaSession.setActionHandler("play", () => { el.nativeAudio.play().catch(() => {}); });
        navigator.mediaSession.setActionHandler("pause", () => { el.nativeAudio.pause(); });
        navigator.mediaSession.setActionHandler("previoustrack", state.queueIndex > 0 ? () => startAudioQueue(state.queue, state.queueIndex - 1, state.queueSeriesName) : null);
        navigator.mediaSession.setActionHandler("nexttrack", state.queueIndex + 1 < state.queue.length ? () => startAudioQueue(state.queue, state.queueIndex + 1, state.queueSeriesName) : null);
        navigator.mediaSession.setActionHandler("seekbackward", (d) => { el.nativeAudio.currentTime = Math.max(0, (el.nativeAudio.currentTime || 0) - (d.seekOffset || 15)); });
        navigator.mediaSession.setActionHandler("seekforward", (d) => { el.nativeAudio.currentTime = (el.nativeAudio.currentTime || 0) + (d.seekOffset || 30); });
      } catch {}
    }

    // Highlight active track in DOM without full re-render flicker
    document.querySelectorAll(".series-track-row.playing-now").forEach((r) => r.classList.remove("playing-now"));
    document.querySelectorAll(`.series-track-row [data-id="${CSS.escape(it.id)}"]`).forEach((btn) => btn.closest(".series-track-row")?.classList.add("playing-now"));
  }

  function bindAudioEvents() {
    el.nativeAudio.addEventListener("timeupdate", () => {
      const cur = el.nativeAudio.currentTime || 0;
      const dur = isFinite(el.nativeAudio.duration) ? el.nativeAudio.duration : 0;
      el.playerCurrentTime.textContent = formatTime(cur);
      el.playerDuration.textContent = formatTime(dur);
      el.playerSeek.value = dur > 0 ? (cur / dur) * 100 : 0;
      if (state.currentTrackId && Math.floor(cur) % 5 === 0 && cur > 5) {
        state.progress[state.currentTrackId] = { t: Math.floor(cur), d: Math.floor(dur) };
        saveJSON(LS_KEYS.progress, state.progress);
      }
    });
    el.nativeAudio.addEventListener("playing", () => {
      el.playerErrorBanner?.classList.add("hidden");
      el.playerPlayPauseBtn.textContent = "⏸";
    });
    el.nativeAudio.addEventListener("pause", () => {
      el.playerPlayPauseBtn.textContent = "▶";
    });
    el.nativeAudio.addEventListener("waiting", () => {
      if (!el.nativeAudio.paused) el.playerPlayPauseBtn.textContent = "⏳";
    });
    el.nativeAudio.addEventListener("error", () => {
      if (!el.nativeAudio.getAttribute("src")) return;
      el.playerPlayPauseBtn.textContent = "▶";
      const curItem = state.queue[state.queueIndex];
      if (curItem) showAudioError(curItem);
    });
    el.nativeAudio.addEventListener("ended", () => {
      if (el.playerAutoNext.checked && state.queueIndex + 1 < state.queue.length) {
        startAudioQueue(state.queue, state.queueIndex + 1, state.queueSeriesName, { replaceUrl: true });
      } else {
        el.playerPlayPauseBtn.textContent = "▶";
      }
    });
    el.playerPlayPauseBtn.addEventListener("click", () => {
      if (el.nativeAudio.paused) {
        el.playerErrorBanner?.classList.add("hidden");
        if (el.nativeAudio.error) {
          el.nativeAudio.load();
        }
        el.playerPlayPauseBtn.textContent = "⏳";
        const p = el.nativeAudio.play();
        if (p && typeof p.then === "function") {
          p.then(() => {
            el.playerErrorBanner?.classList.add("hidden");
            if (!el.nativeAudio.paused) el.playerPlayPauseBtn.textContent = "⏸";
          }).catch((err) => {
            if (err && err.name === "AbortError") return;
            el.playerPlayPauseBtn.textContent = "▶";
            const curItem = state.queue[state.queueIndex];
            if (curItem && (el.nativeAudio.error || err?.name === "NotSupportedError")) showAudioError(curItem);
          });
        }
      } else {
        el.nativeAudio.pause();
        el.playerPlayPauseBtn.textContent = "▶";
      }
    });
    el.playerNextBtn.addEventListener("click", () => {
      if (state.queueIndex + 1 < state.queue.length) startAudioQueue(state.queue, state.queueIndex + 1, state.queueSeriesName, { replaceUrl: true });
    });
    el.playerPrevBtn.addEventListener("click", () => {
      if (state.queueIndex > 0) startAudioQueue(state.queue, state.queueIndex - 1, state.queueSeriesName, { replaceUrl: true });
    });
    el.playerBack30Btn.addEventListener("click", () => {
      try { el.nativeAudio.currentTime = Math.max(0, (el.nativeAudio.currentTime || 0) - 15); } catch {}
    });
    el.playerFwd30Btn.addEventListener("click", () => {
      try { el.nativeAudio.currentTime = (el.nativeAudio.currentTime || 0) + 30; } catch {}
    });
    el.playerSeek.addEventListener("input", () => {
      if (isFinite(el.nativeAudio.duration) && el.nativeAudio.duration > 0) {
        el.nativeAudio.currentTime = (el.playerSeek.value / 100) * el.nativeAudio.duration;
      }
    });
    el.playerSpeedBtn.addEventListener("click", () => {
      state.speedIdx = (state.speedIdx + 1) % state.speeds.length;
      const spd = state.speeds[state.speedIdx];
      el.nativeAudio.playbackRate = spd;
      el.playerSpeedBtn.textContent = `${spd}x`;
      saveJSON(LS_KEYS.speed, state.speedIdx);
    });
    el.playerAutoNext.addEventListener("change", () => {
      saveJSON(LS_KEYS.autoNext, !!el.playerAutoNext.checked);
    });
    el.playerCloseBtn.addEventListener("click", () => {
      el.nativeAudio.pause();
      el.playerErrorBanner?.classList.add("hidden");
      el.audioPlayerBar.classList.add("hidden");
      document.body.classList.remove("has-player");
      state.currentTrackId = null;
      state.urlShiurId = null;
      syncUrlState(false);
    });
  }

  // =========================================================================
  // Media / Drive / Video Modal WITH Built-in Series Playlist!
  // =========================================================================
  function openMediaModal(it, mode, gidOverride = null, opts = {}) {
    if (!it) return;
    if (!el.nativeAudio.paused && mode !== "pdf") {
      el.nativeAudio.pause();
      el.playerPlayPauseBtn.textContent = "▶";
    }
    pushHistory(it.id);
    const wasOpen = !el.mediaModal.classList.contains("hidden");
    state.activeModalShiurId = it.id;
    state.urlShiurId = it.id;
    if (!opts.fromUrl) syncUrlState(!wasOpen);

    el.modalTitle.textContent = it.t;
    el.modalPills.innerHTML = `${getLangBadges(it)} <span class="badge">${escHtml(it.b || it.cat)}</span>` + (it.y?.[0] ? `<span class="badge badge-year">${escHtml(it.y[0])}</span>` : "");
    el.modalBody.classList.toggle("is-light", mode === "drive" || mode === "pdf");

    const srcUrl = getSourceUrl(it);
    const dlUrl = getDirectDownloadUrl(it);
    let extUrl = srcUrl || "";
    if (mode === "video") {
      if (it.vi && it.vi.startsWith("yt:")) {
        const yid = it.vi.slice(3);
        extUrl = `https://www.youtube.com/watch?v=${yid}`;
        el.modalBody.innerHTML = `<iframe src="https://www.youtube.com/embed/${escHtml(yid)}?autoplay=1&rel=0" allow="autoplay; encrypted-media; fullscreen" allowfullscreen></iframe>`;
      } else if (it.vi) {
        extUrl = it.vi;
        const isMixedHttp = window.location.protocol === "https:" && it.vi.startsWith("http://");
        if (isMixedHttp) {
          el.modalBody.innerHTML = `
            <div style="padding:32px;text-align:center;color:#E2E8F0">
              <p>סרטון זה מאוחסן בשרת HTTP חיצוני (<code>video.chasidut.net</code>). לחץ לפתיחה בחלון חדש:</p>
              <a class="btn-primary" href="${escHtml(it.vi)}" target="_blank" rel="noopener">▶ צפה בסרטון בחלון חדש ↗</a>
            </div>`;
        } else {
          el.modalBody.innerHTML = `<video id="modalVideoEl" controls autoplay preload="metadata" playsinline><source src="${escHtml(it.vi)}" type="video/mp4" /></video>`;
        }
      }
    } else if (mode === "drive") {
      const driveViewUrl = it.dr ? it.dr.replace(/\/preview(\?|$)/, "/view$1") : srcUrl;
      const sameDriveFile = !!(srcUrl && driveViewUrl && srcUrl.split("?")[0] === driveViewUrl.split("?")[0]);
      const isWma = (it.sub || "").includes("WMA");
      extUrl = driveViewUrl || srcUrl || it.dr || "";
      el.modalBody.innerHTML = `
        <div class="drive-audio-sheet">
          <div class="drive-sheet-top">
            <div class="drive-sheet-icon">☁️</div>
            <div>
              <h4 class="drive-sheet-title">שמע מתוך Google Drive</h4>
              <p class="drive-sheet-desc">
                ${isWma
                  ? "קובץ זה הוא בפורמט WMA ישן שאינו מופעל ישירות בדפדפן. ניתן לפתוח אותו ב-Google Drive או להוריד למכשיר."
                  : "Google חוסמת הטמעה ישירה של קבצי Drive בתוך נגן האודיו של האתר (מדיניות אבטחה של הדפדפן). בלחיצה על הכפתור תיפתח תצוגת הנגן הרשמית של Google Drive או שתוכלו להוריד את הקובץ ישירות:"}
              </p>
            </div>
          </div>
          <div class="drive-sheet-actions">
            ${driveViewUrl ? `<a class="btn-primary" href="${escHtml(driveViewUrl)}" target="_blank" rel="noopener">▶ נגן ב-Google Drive (חלון חדש) ↗</a>` : ""}
            ${dlUrl ? `<a class="btn-outline" href="${escHtml(dlUrl)}" target="_blank" rel="noopener">⬇ הורד קובץ שמע</a>` : ""}
            ${srcUrl && !sameDriveFile ? `<a class="btn-outline" href="${escHtml(srcUrl)}" target="_blank" rel="noopener">🔗 עמוד המקור ↗</a>` : ""}
          </div>
          ${!isWma && it.dr ? `
            <div class="drive-embed-toggle-row">
              <button type="button" class="btn-ghost btn-sm" id="loadDriveEmbedBtn">▶ נסה תצוגה מקדימה של Drive בדף זה (בכפוף להגדרות הדפדפן)</button>
            </div>
            <div id="driveEmbedSlot" class="drive-embed-slot hidden"></div>
          ` : ""}
        </div>`;
      $("loadDriveEmbedBtn")?.addEventListener("click", () => {
        const slot = $("driveEmbedSlot");
        const btn = $("loadDriveEmbedBtn");
        if (!slot) return;
        slot.classList.remove("hidden");
        slot.innerHTML = `<iframe class="drive-embed-frame" src="${escHtml(it.dr)}" allow="autoplay; fullscreen" allowfullscreen></iframe>`;
        if (btn) btn.classList.add("hidden");
      });
    } else if (mode === "pdf") {
      extUrl = it.pd || srcUrl || "";
      if (it.pd && it.pd.includes("hebrewbooks.org")) {
        el.modalBody.innerHTML = `
          <div style="padding:28px;text-align:center;">
            <h4 style="margin:0 0 10px;color:var(--primary);font-family:var(--font-serif);font-size:1.2rem;">${escHtml(it.t)}</h4>
            <p style="color:var(--text-muted);">${escHtml(it.sub)}</p>
            <a class="btn-primary" href="${escHtml(it.pd)}" target="_blank" rel="noopener" style="text-decoration:none;display:inline-block;">📖 פתח וצפה בספר באתר HebrewBooks ↗</a>
          </div>`;
      } else {
        el.modalBody.innerHTML = `<iframe src="${escHtml(it.pd)}" allowfullscreen></iframe>`;
      }
    }

    el.modalExternalBtn.textContent = "🔗 פתח במקור ↗";
    el.modalExternalBtn.href = srcUrl || extUrl || "#";
    if (el.modalShareBtn) {
      el.modalShareBtn.onclick = () => shareLink({ title: it.t, text: `${it.t} — אוצר שיעורי ר' יואל`, hash: `shiur=${encodeURIComponent(it.id)}` });
    }
    const footerParts = [`<span>מקור: ${escHtml(SOURCES[it.src]?.name || it.src)}</span>`];
    if (srcUrl) footerParts.push(`<a href="${escHtml(srcUrl)}" target="_blank" rel="noopener" class="btn-outline btn-sm">🔗 עמוד המקור ↗</a>`);
    if (dlUrl) footerParts.push(`<a href="${escHtml(dlUrl)}" target="_blank" rel="noopener" class="btn-outline btn-sm">⬇ הורד קובץ ↗</a>`);
    el.modalFooter.innerHTML = footerParts.join(" ");

    // Series Playlist Drawer inside Modal if multi-part series!
    const gid = gidOverride || it.gid;
    const seriesTracks = (GROUPS_MAP.get(gid) || []).filter((x) => (mode === "drive" ? x.dr : (mode === "video" ? x.vi : (mode === "pdf" ? x.pd : true))));
    if (seriesTracks.length >= 2) {
      const curPos = seriesTracks.findIndex((x) => x.id === it.id);
      const nextTrack = curPos >= 0 && curPos + 1 < seriesTracks.length ? seriesTracks[curPos + 1] : null;
      el.modalSeriesPlaylist.classList.remove("hidden");
      el.modalSeriesPlaylist.innerHTML = `
        <div class="modal-pl-head">
          <span>📚 חלקי הסדרה (${curPos + 1} מתוך ${seriesTracks.length})</span>
          ${nextTrack ? `<button type="button" class="btn-primary btn-sm" id="modalNextPartBtn">לשיעור הבא בסדרה ←</button>` : ""}
        </div>
        <div class="modal-pl-items">
          ${seriesTracks.map((tr, i) => `
            <button type="button" class="modal-pl-btn ${tr.id === it.id ? "active" : ""}" data-mpl-id="${escHtml(tr.id)}" data-mpl-mode="${mode}" data-mpl-gid="${escHtml(gid)}">${i + 1}. ${escHtml(tr.t.length > 42 ? tr.t.slice(0, 40) + "..." : tr.t)}</button>
          `).join("")}
        </div>`;
      $("modalNextPartBtn")?.addEventListener("click", () => openMediaModal(nextTrack, mode, gid));
    } else {
      el.modalSeriesPlaylist.classList.add("hidden");
      el.modalSeriesPlaylist.innerHTML = "";
    }

    el.mediaModal.classList.remove("hidden");
    document.body.classList.add("lock-scroll");
  }

  function closeMediaModal(silent = false) {
    el.mediaModal.classList.add("hidden");
    document.body.classList.remove("lock-scroll");
    const vid = $("modalVideoEl");
    if (vid) {
      vid.pause();
      vid.querySelectorAll("source").forEach((s) => s.removeAttribute("src"));
      vid.load();
    }
    el.modalBody.querySelectorAll("iframe").forEach((fr) => { fr.src = "about:blank"; });
    el.modalBody.innerHTML = "";
    el.modalSeriesPlaylist.innerHTML = "";
    if (state.activeModalShiurId || state.urlShiurId) {
      state.activeModalShiurId = null;
      if (state.urlShiurId && !state.currentTrackId) state.urlShiurId = null;
      else if (el.audioPlayerBar.classList.contains("hidden") || el.nativeAudio.paused) state.urlShiurId = null;
      if (!silent) syncUrlState(false);
    }
  }

  // =========================================================================
  // Event Binding
  // =========================================================================
  function bindEvents() {
    el.themeToggleBtn.addEventListener("click", () => applyTheme(state.theme === "light" ? "dark" : "light"));

    el.brandHomeBtn.addEventListener("click", () => {
      jumpBrowseCrumb("root");
      switchView("browse");
    });
    el.brandHomeBtn.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        jumpBrowseCrumb("root");
        switchView("browse");
      }
    });

    el.navTabs.forEach((t) => t.addEventListener("click", () => switchView(t.dataset.view)));
    el.mobileMoreNavBtn?.addEventListener("click", () => {
      const isOpen = el.mainNav.classList.toggle("more-open");
      el.mobileMoreNavBtn.setAttribute("aria-expanded", String(isOpen));
    });

    // Global Search -> switches cleanly to Catalog (Grouped Series view!) and streams chunks
    let searchTimer = null;
    el.searchInput.addEventListener("input", () => {
      const val = el.searchInput.value.trim();
      el.clearSearchBtn.classList.toggle("hidden", !val);
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        state.filters.q = val;
        state.page = 1;
        if (val && state.view !== "catalog") switchView("catalog");
        else {
          applyCatalogFilters(true, "replace");
          if (state.view === "catalog") startCatalogChunksStream();
        }
      }, 220);
    });
    el.searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        clearTimeout(searchTimer);
        state.filters.q = el.searchInput.value.trim();
        state.page = 1;
        if (state.view !== "catalog") switchView("catalog");
        else {
          applyCatalogFilters(true, "push");
          startCatalogChunksStream();
        }
      }
    });
    el.clearSearchBtn.addEventListener("click", () => {
      el.searchInput.value = "";
      el.clearSearchBtn.classList.add("hidden");
      state.filters.q = "";
      applyCatalogFilters(true, "push");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
        e.preventDefault();
        el.searchInput.focus();
      } else if (e.key === "Escape" && !el.mediaModal.classList.contains("hidden")) {
        closeMediaModal();
      }
    });

    // Browse Top Filter Strip & Breadcrumbs
    const updateBrowseFiltersSummary = () => syncBrowseFilterPills();
    el.browseFiltersToggleBtn?.addEventListener("click", () => {
      const open = el.browseTopbar.classList.toggle("open");
      el.browseFiltersToggleBtn.setAttribute("aria-expanded", String(open));
    });
    el.browseLangPills.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-blang]");
      if (!btn) return;
      state.browse.lang = btn.dataset.blang;
      updateBrowseFiltersSummary();
      renderBrowse();
      syncUrlState(true);
    });
    el.browseFmtPills.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-bfmt]");
      if (!btn) return;
      state.browse.fmt = btn.dataset.bfmt;
      updateBrowseFiltersSummary();
      renderBrowse();
      syncUrlState(true);
    });
    el.browseBreadcrumbs.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-crumb]");
      if (btn && !btn.disabled) jumpBrowseCrumb(btn.dataset.crumb);
    });
    el.browseBackBtn.addEventListener("click", goBrowseBack);
    el.browseOpenInCatalogBtn.addEventListener("click", () => {
      const br = state.browse;
      state.filters.lang = br.lang;
      state.filters.format = br.fmt;
      state.filters.cat = br.cat || "all";
      state.filters.rebbe = br.r || "all";
      state.filters.book = br.b || "all";
      state.filters.vol = br.v || "all";
      state.filters.sec = br.sec || "all";
      state.page = 1;
      switchView("catalog");
    });

    // Browse Step Tools (Tanya Mode, Book Maamar Mode, Stage Search Filter, Cross-Parsha)
    el.browseStepTools.addEventListener("click", (e) => {
      const tbtn = e.target.closest("[data-tmode]");
      if (tbtn) {
        state.browse.tanyaMode = tbtn.dataset.tmode;
        state.browse.v = null;
        state.browse.ts = null;
        state.browse.stageFilter = "";
        renderBrowse();
        syncUrlState(true);
        return;
      }
      const bbtn = e.target.closest("[data-bmode]");
      if (bbtn) {
        state.browse.bookMode = bbtn.dataset.bmode;
        state.browse.v = null;
        state.browse.sec = null;
        state.browse.ma = null;
        state.browse.stageFilter = "";
        renderBrowse();
        syncUrlState(true);
        return;
      }
      if (e.target.id === "toggleCrossParshaBtn") {
        state.browse.includeParshaBooks = !state.browse.includeParshaBooks;
        renderBrowse();
        syncUrlState(true);
      }
    });
    el.stageFilterInput.addEventListener("input", () => {
      state.browse.stageFilter = el.stageFilterInput.value;
      renderBrowse();
    });

    // Browse Stage Card Clicks
    el.browseStageContent.addEventListener("click", (e) => {
      const targetEl = e.target instanceof Element ? e.target : e.target.parentElement;
      const card = targetEl?.closest("[data-step-action]");
      if (card) {
        const act = card.dataset.stepAction;
        const val = card.dataset.stepVal;
        state.browse.stageFilter = "";
        if (act === "pick-cat") state.browse.cat = val;
        else if (act === "pick-rebbe") state.browse.r = val;
        else if (act === "pick-book") state.browse.b = val;
        else if (act === "pick-ts") state.browse.ts = val;
        else if (act === "pick-ma") state.browse.ma = val;
        else if (act === "pick-vol") state.browse.v = val;
        else if (act === "pick-sec") state.browse.sec = val;
        else if (act === "jump-chazaros") {
          state.browse.cat = "חזרות והתוועדויות";
          state.browse.r = null;
          state.browse.b = 'חזרות על התוועדויות הרבי';
          state.browse.v = null;
          state.browse.sec = null;
        }
        renderBrowse();
        syncUrlState(true);
        const browseFocusNode = el.breadcrumbBar && !el.breadcrumbBar.classList.contains("hidden")
          ? el.breadcrumbBar
          : el.browseStepTitle;
        scrollToRelevantContent(browseFocusNode);
        return;
      }
      if (e.target.id === "browseResetFiltersBtn") {
        state.browse.lang = "all";
        state.browse.fmt = "all";
        updateBrowseFiltersSummary();
        renderBrowse();
        syncUrlState(true);
      }
    });

    // Catalog Sidebar & Controls
    el.filtersSidebar.addEventListener("click", (e) => {
      const ym = e.target.closest(".ym-btn");
      if (ym) {
        state.filters.yearMode = ym.dataset.ym;
        el.filtersSidebar.querySelectorAll(".ym-btn").forEach((b) => b.classList.toggle("active", b === ym));
        renderSidebarFacets();
        syncUrlState(false);
        return;
      }
      const opt = e.target.closest(".filter-opt-btn");
      if (!opt) return;
      const k = opt.dataset.filter;
      const v = opt.dataset.val;
      if (k === "cat") { state.filters.cat = v; state.filters.rebbe = "all"; state.filters.book = "all"; state.filters.vol = "all"; state.filters.sec = "all"; }
      else if (k === "rebbe") { state.filters.rebbe = v; state.filters.book = "all"; state.filters.vol = "all"; state.filters.sec = "all"; }
      else if (k === "book") { state.filters.book = v; state.filters.vol = "all"; state.filters.sec = "all"; }
      else if (k === "vol") { state.filters.vol = v; state.filters.sec = "all"; }
      else state.filters[k] = v;
      applyCatalogFilters(true, "push");
    });

    const resetCatalogAll = () => {
      state.filters = { q: "", lang: "all", format: "all", cat: "all", rebbe: "all", book: "all", vol: "all", sec: "all", yearMode: "decades", decade: "all", year: "all", parsha: "all", source: "all", sort: "default" };
      el.searchInput.value = "";
      el.clearSearchBtn.classList.add("hidden");
      el.sortSelect.value = "default";
      applyCatalogFilters(true, "push");
    };
    el.clearAllFiltersBtn.addEventListener("click", resetCatalogAll);
    el.emptyResetBtn.addEventListener("click", resetCatalogAll);

    el.activeChipsBar.addEventListener("click", (e) => {
      if (e.target.id === "chipsClearAll") { resetCatalogAll(); return; }
      const btn = e.target.closest("[data-clear-chip]");
      if (!btn) return;
      const k = btn.dataset.clearChip;
      if (k === "q") { state.filters.q = ""; el.searchInput.value = ""; el.clearSearchBtn.classList.add("hidden"); }
      else if (k === "cat") { state.filters.cat = "all"; state.filters.rebbe = "all"; state.filters.book = "all"; state.filters.vol = "all"; state.filters.sec = "all"; }
      else if (k === "rebbe") { state.filters.rebbe = "all"; state.filters.book = "all"; state.filters.vol = "all"; state.filters.sec = "all"; }
      else if (k === "book") { state.filters.book = "all"; state.filters.vol = "all"; state.filters.sec = "all"; }
      else if (k === "vol") { state.filters.vol = "all"; state.filters.sec = "all"; }
      else state.filters[k] = "all";
      applyCatalogFilters(true, "push");
    });

    document.querySelectorAll(".vm-btn").forEach((btn) => btn.addEventListener("click", () => {
      state.catalogMode = btn.dataset.mode;
      document.querySelectorAll(".vm-btn").forEach((b) => b.classList.toggle("active", b === btn));
      state.page = 1;
      renderCatalog();
      syncUrlState(true);
    }));

    el.sortSelect.addEventListener("change", () => {
      state.filters.sort = el.sortSelect.value;
      applyCatalogFilters(true, "push");
    });

    el.paginationBar.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-page]");
      if (!btn || btn.disabled) return;
      state.page = Number(btn.dataset.page);
      renderCatalog();
      syncUrlState(true);
      scrollToRelevantContent(el.resultsList);
    });

    const closeMobileFilters = () => {
      el.filtersSidebar.classList.remove("open");
      document.body.classList.remove("lock-scroll");
    };
    el.mobileFilterToggleBtn.addEventListener("click", () => {
      el.filtersSidebar.classList.add("open");
      document.body.classList.add("lock-scroll");
    });
    el.closeMobileFilterBtn.addEventListener("click", closeMobileFilters);
    el.mobileDrawerDoneBtn?.addEventListener("click", closeMobileFilters);

    // PDF Filter & History Clear
    el.pdfLangFilterPills.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-pdflang]");
      if (!btn) return;
      state.pdfLang = btn.dataset.pdflang;
      el.pdfLangFilterPills.querySelectorAll(".pill-filter").forEach((b) => b.classList.toggle("active", b === btn));
      renderSeforimPdfView();
      syncUrlState(true);
    });
    el.clearHistoryBtn.addEventListener("click", () => {
      state.history = [];
      saveJSON(LS_KEYS.history, []);
      renderSavedView();
      renderResumeBanner();
    });

    // Global Delegated Card Actions (Series Play, Track Play, Drive, Video, PDF, Expand, Bookmark)
    document.addEventListener("click", (e) => {
      const actBtn = e.target.closest("[data-action]");
      if (!actBtn) return;
      const act = actBtn.dataset.action;
      const id = actBtn.dataset.id;
      const gid = actBtn.dataset.gid;

      if (act === "play-series") { startSeriesPlayback(gid); return; }
      if (act === "play-series-modal") { startSeriesPlayback(gid); return; }
      if (act === "expand-series") {
        state.expandedSeries.add(gid);
        if (state.view === "browse") renderBrowse();
        else if (state.view === "catalog") renderCatalog();
        return;
      }
      const it = id ? ITEMS_BY_ID.get(id) : null;
      if (!it) return;
      if (act === "play-audio") startSeriesPlayback(gid || it.gid, it.id);
      else if (act === "play-drive") openMediaModal(it, "drive", gid || it.gid);
      else if (act === "play-video") openMediaModal(it, "video", gid || it.gid);
      else if (act === "open-pdf") openMediaModal(it, "pdf", gid || it.gid);
      else if (act === "share-series") {
        shareLink({ title: it.t, text: `${it.t} — אוצר שיעורי ר' יואל`, hash: `shiur=${encodeURIComponent(it.id)}` });
      } else if (act === "bookmark") {
        if (state.bookmarks.has(id)) state.bookmarks.delete(id);
        else state.bookmarks.add(id);
        saveJSON(LS_KEYS.bookmarks, [...state.bookmarks]);
        el.navSavedCount.textContent = state.bookmarks.size.toLocaleString("he-IL");
        actBtn.classList.toggle("saved", state.bookmarks.has(id));
        actBtn.textContent = state.bookmarks.has(id) ? "🔖" : "☆";
        showToast(state.bookmarks.has(id) ? "🔖 נשמר בסימניות" : "הוסר מהסימניות");
        if (state.view === "saved") renderSavedView();
      }
    });

    // Modal Playlist Clicks & Close
    el.modalSeriesPlaylist.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-mpl-id]");
      if (!btn) return;
      const tr = ITEMS_BY_ID.get(btn.dataset.mplId);
      if (tr) openMediaModal(tr, btn.dataset.mplMode, btn.dataset.mplGid);
    });
    el.closeModalBtn.addEventListener("click", () => closeMediaModal(false));
    el.mediaModal.addEventListener("click", (e) => { if (e.target === el.mediaModal) closeMediaModal(false); });
  }

  // =========================================================================
  // VIEW 6 & 7: Submit Archive & Feedback (Google Forms Only)
  // =========================================================================
  function renderGoogleFormMount(mountEl, gfUrl, label) {
    if (!mountEl) return;
    if (!gfUrl) {
      mountEl.innerHTML = `<div class="empty-state"><p>טופס ${escHtml(label)} אינו מוגדר כעת.</p></div>`;
      return;
    }
    const base = gfUrl.split("?")[0];
    const embedSrc = base.includes("viewform") ? `${base}?embedded=true` : gfUrl;
    mountEl.innerHTML = `
      <div class="google-form-head">
        <strong>📝 ${escHtml(label)}</strong>
        <a href="${escHtml(base)}" target="_blank" rel="noopener" class="btn-outline btn-sm">פתח טופס בחלון חדש ↗</a>
      </div>
      <iframe class="google-form-iframe" src="${escHtml(embedSrc)}" title="${escHtml(label)}">טוען טופס...</iframe>`;
  }

  function renderSubmitArchiveView() {
    renderGoogleFormMount($("archGoogleFormMount"), SITE_CFG.googleFormArchiveUrl, "טופס הוספת מאגר שיעורים");
  }

  function renderFeedbackView() {
    renderGoogleFormMount($("fbGoogleFormMount"), SITE_CFG.googleFormFeedbackUrl, "טופס יצירת קשר ומשוב");
  }

  function bindCommunityEvents() {
    // Google Forms handles submission natively inside the embedded forms
  }

  // =========================================================================
  // Boot
  // =========================================================================
  function init() {
    applyTheme(state.theme);
    const totalCount = META.totalCount || ITEMS.length;
    const pdfCount = META.pdfCount || ITEMS.filter((it) => (it.f || []).includes("pdf")).length;
    el.headerSubStats.textContent = `הגה"ח רבי יואל כהן ע"ה • ${totalCount.toLocaleString("he-IL")} שיעורים • ${(META.multiSeriesCount || 0).toLocaleString("he-IL")} סדרות ברצף`;
    el.navTotalCount.textContent = totalCount.toLocaleString("he-IL");
    el.navPdfCount.textContent = pdfCount.toLocaleString("he-IL");
    el.navSavedCount.textContent = state.bookmarks.size.toLocaleString("he-IL");
    el.playerSpeedBtn.textContent = `${state.speeds[state.speedIdx]}x`;
    const savedAuto = loadJSON(LS_KEYS.autoNext, true);
    if (typeof savedAuto === "boolean") el.playerAutoNext.checked = savedAuto;

    state.filtered = ITEMS;
    state.groupedSeries = buildTracksSeriesGroups(ITEMS);
    bindAudioEvents();
    bindEvents();
    bindCommunityEvents();
    renderResumeBanner();
    if ((window.location.search && window.location.search.length > 1) || (window.location.hash && window.location.hash.length > 1)) {
      applyStateFromLocation();
    } else {
      renderBrowse();
    }
    window.addEventListener("popstate", applyStateFromLocation);
    window.addEventListener("hashchange", applyStateFromLocation);
  }

  init();
})();
